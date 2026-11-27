"""Entrenamiento científico: se detiene si no se demuestra una T4 de Colab."""
from pathlib import Path
from datetime import datetime,timezone
from importlib.metadata import version
import subprocess,sys,time,json,hashlib,platform,traceback
import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from .config import ROOT,PaiError,project,save_json,digest
from .data import audit
from .features import samples,fit_scaler,transform,metrics,indicators,FEATURES
from .backtest import choose_rule,simulate

def incident(root,stage,error,action,result='DETENIDO'):
    path=Path(root)/'evidencia/bitacora.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
    row={'fecha':datetime.now(timezone.utc).isoformat(),'etapa':stage,'error':type(error).__name__,
         'causa':str(error),'accion_correctiva':action,'verificacion':result}
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    return row

def require_t4(root=ROOT):
    root=Path(root)
    try:
        import importlib.util
        if importlib.util.find_spec('google.colab') is None:
            raise PaiError('Se requiere una sesión Google Colab con NVIDIA T4. Este entorno no es Colab.')
        import tensorflow as tf
        nvidia=subprocess.run(['nvidia-smi'],capture_output=True,text=True,check=True).stdout
        gpus=tf.config.list_physical_devices('GPU')
        if 'T4' not in nvidia or not gpus:raise PaiError('T4 ausente o TensorFlow no reconoce la GPU.')
        details=tf.config.experimental.get_device_details(gpus[0])
        if 'T4' not in details.get('device_name',''):raise PaiError('La GPU elegida por TensorFlow no es T4.')
        tf.config.set_soft_device_placement(False)
        tf.config.experimental.set_memory_growth(gpus[0],True)
        with tf.device('/GPU:0'):
            a=tf.linalg.matmul(tf.ones((128,128)),tf.ones((128,128)))
        if 'GPU:0' not in a.device:raise PaiError('La operación no se ejecutó en GPU:0.')
        # Lectura de datos y callbacks pueden usar kernels de CPU. El cómputo
        # del modelo y sus gradientes se comprueba aparte durante el ajuste.
        tf.config.set_soft_device_placement(True)
        report={'timestamp':datetime.now(timezone.utc).isoformat(),'nvidia_smi':nvidia,
                'gpu':details,'operation_device':a.device,'operation_sum':float(tf.reduce_sum(a).numpy()),
                'tensorflow':tf.__version__,'python':sys.version,'colab':True,
                'versiones':{m:version(m) for m in ['numpy','pandas','scikit-learn','keras','tensorflow']}}
        import uuid
        evidence_file='evidencia/t4_sessions/'+uuid.uuid4().hex+'.json'
        report['evidence_file']=evidence_file
        save_json(root/evidence_file,report)
        save_json(root/'evidencia/t4.json',report)
        (root/'evidencia/nvidia-smi.txt').write_text(nvidia)
        return tf,report
    except (PaiError,FileNotFoundError,subprocess.CalledProcessError,ModuleNotFoundError,RuntimeError) as exc:
        incident(root,'T4',exc,'Elegir T4 en Colab y reejecutar desde sesión limpia; no entrenar en CPU.')
        raise PaiError(str(exc)) from exc

def _dataset(tf,x,y=None,batch=64):
    with tf.device('/CPU:0'):
        ds=tf.data.Dataset.from_tensor_slices(x if y is None else (x,y)).batch(batch)
    options=tf.data.Options();options.threading.private_threadpool_size=1
    return ds.with_options(options).prefetch(1)

def _network(tf,family,shape,neurons,lr,seed):
    tf.keras.backend.clear_session();tf.keras.utils.set_random_seed(seed)
    with tf.device('/GPU:0'):
        net=tf.keras.Sequential([tf.keras.Input(shape=shape)])
        if family=='MLP':net.add(tf.keras.layers.Flatten());net.add(tf.keras.layers.Dense(neurons,activation='relu'))
        else:net.add(tf.keras.layers.LSTM(neurons))
        net.add(tf.keras.layers.Dense(8,activation='relu'));net.add(tf.keras.layers.Dense(1))
        net.compile(optimizer=tf.keras.optimizers.Adam(lr),loss='mse')
    return net

def _fit(tf,x,y,xval,yval,family,neurons,seed,config,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    scaler=fit_scaler(x);ys=StandardScaler().fit(y.reshape(-1,1))
    xx=transform(x,scaler);vv=transform(xval,scaler)
    yy=ys.transform(y.reshape(-1,1)).astype('float32');yv=ys.transform(yval.reshape(-1,1)).astype('float32')
    batch=int(config['batch_size'])
    # Solo un reintento por memoria: se registra el cambio de lote.
    for attempt in range(2):
        model=_network(tf,family,x.shape[1:],neurons,config['learning_rate'],seed)
        stop=tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=config['patience'],restore_best_weights=True)
        check=tf.keras.callbacks.ModelCheckpoint(str(folder/'checkpoint.keras'),save_best_only=True,monitor='val_loss')
        terminate=tf.keras.callbacks.TerminateOnNaN()
        start=time.perf_counter()
        try:
            with tf.device('/GPU:0'):
                h=model.fit(_dataset(tf,xx,yy,batch),validation_data=_dataset(tf,vv,yv,batch),
                            epochs=config['max_epochs'],shuffle=False,verbose=0,callbacks=[stop,check,terminate])
            if not np.isfinite(np.r_[h.history['loss'],h.history['val_loss']]).all():raise PaiError('Pérdida no finita; experimento invalidado.')
            break
        except tf.errors.ResourceExhaustedError as exc:
            incident(ROOT,'memoria',exc,'Reducir lote a la mitad y reconstruir el modelo con la misma semilla.')
            if attempt or batch<=8:raise PaiError('Memoria insuficiente después del reintento.') from exc
            batch=max(8,batch//2)
    variables=[v.value if hasattr(v,'value') else v for v in model.trainable_variables]
    devices=[getattr(v,'device','') for v in variables]
    if not devices or not all('GPU:0' in d for d in devices):raise PaiError('Los pesos no están en GPU:0; entrenamiento no acreditable.')
    with tf.device('/GPU:0'):
        with tf.GradientTape() as tape:
            check_loss=tf.reduce_mean(tf.square(model(xx[:8],training=True)-yy[:8]))
        gradients=tape.gradient(check_loss,model.trainable_variables)
    gradient_devices=[g.device for g in gradients if g is not None]
    if len(gradient_devices)!=len(variables) or not all('GPU:0' in d for d in gradient_devices):
        raise PaiError('No se comprobó el cálculo de gradientes en GPU:0.')
    elapsed=time.perf_counter()-start
    model.save(folder/'modelo.keras');joblib.dump({'x':scaler,'y':ys},folder/'escaladores.joblib')
    hist=pd.DataFrame(h.history);hist.index.name='epoca';hist.to_csv(folder/'historial.csv')
    detail={'familia':family,'neuronas':neurons,'seed':seed,'variables':x.shape[-1],
            'input_shape':list(x.shape[1:]),'parametros_entrenables':int(sum(np.prod(v.shape) for v in variables)),
            'capas':json.loads(model.to_json()),'loss':'mse','optimizer':'Adam','learning_rate':config['learning_rate'],
            'batch_size':batch,'max_epochs':config['max_epochs'],'epochs':len(hist),
            'best_epoch':int(np.argmin(hist.val_loss)+1),'seconds':elapsed,'device':'/GPU:0',
            'variable_devices':devices,'gradient_devices':gradient_devices,'training_scope':'/GPU:0',
            'versions':{m:version(m) for m in ['numpy','pandas','scikit-learn','keras','tensorflow']},
            'model_sha256':digest(folder/'modelo.keras'),
            'scalers_sha256':digest(folder/'escaladores.joblib')}
    save_json(folder/'entrenamiento.json',detail)
    return model,{'x':scaler,'y':ys},detail

def predict_model(model,scalers,x):
    xx=transform(x,scalers['x'])
    pred=model.predict(xx,batch_size=128,verbose=0)
    p=scalers['y'].inverse_transform(pred).ravel()
    if not np.isfinite(p).all():raise PaiError('Predicción no finita; no se genera señal.')
    return p

def classical(symbol,root=ROOT):
    root=Path(root);path=root/'data/processed'/f'{symbol}.csv'
    if not path.is_file():raise PaiError(f'{symbol}: faltan datos auditados; ejecutar la descarga.')
    frame=pd.read_csv(path);raw=json.loads((root/'data/raw'/f'{symbol}.json').read_text())
    frame,report=audit(frame,int(raw['server_time']),1500)
    b=samples(frame);folder=root/'artifacts'/symbol;folder.mkdir(parents=True,exist_ok=True)
    tr,va=b['parts']['TR'],b['parts']['VA'];rows=[]
    models={}
    for variant in ['base','indicadores']:
        x=b[variant];sc=fit_scaler(x[tr]);linear=LinearRegression().fit(transform(x[tr],sc).reshape(len(x[tr]),-1),b['y'][tr])
        models[variant]=(linear,sc)
        joblib.dump({'model':linear,'scaler':sc},folder/f'lineal_{variant}.joblib')
        for part in ['TR','VA']:
            sl=b['parts'][part];p=linear.predict(transform(x[sl],sc).reshape(len(x[sl]),-1))
            rows.append({'modelo':'Lineal','variables':variant,'conjunto':part,**metrics(b['y'][sl],p)})
    for part in ['TR','VA']:
        sl=b['parts'][part];rows.append({'modelo':'Cero','variables':'base','conjunto':part,**metrics(b['y'][sl],np.zeros(len(b['y'][sl])))})
    pd.DataFrame(rows).to_csv(folder/'referencias_TR_VA.csv',index=False)
    parts=[]
    for part,sl in b['parts'].items():
        m=b['meta'].iloc[sl]
        parts.append({'conjunto':part,'n':len(m),'primer_objetivo':m.target_date.iloc[0],'ultimo_objetivo':m.target_date.iloc[-1]})
    pd.DataFrame(parts).to_csv(folder/'particiones.csv',index=False)
    dictionary=[]
    for name,formula,window,unit in [('return','close_t / close_t_minus_1 - 1',1,'Fracción diaria'),
             ('dist_sma20','close_t / promedio(20 cierres) - 1',20,'Fracción'),
             ('vol20','std(20 rendimientos, ddof=1)',20,'Fracción diaria sin anualizar')]:
        valid=b['frame'][name].first_valid_index()
        dictionary.append({'variable':name,'formula':formula,'ventana':window,'unidad':unit,
                           'primera_fecha_valida':str(b['frame'].date.loc[valid])})
    pd.DataFrame(dictionary).to_csv(folder/'diccionario_indicadores.csv',index=False)
    pd.DataFrame(b['indicadores'][tr,-1,:],columns=FEATURES).corr().to_csv(folder/'correlaciones_TR.csv')
    b['meta'].iloc[[tr.stop-1,va.start,va.stop-1,b['parts']['TE'].start]].to_csv(folder/'ejemplos_alineacion.csv',index=False)
    return b,models,pd.DataFrame(rows)

def train_asset(symbol,tf,gpu_report,root=ROOT):
    root=Path(root);config=project();b,linear,base_results=classical(symbol,root)
    folder=root/'artifacts'/symbol;tr,va,te=(b['parts'][k] for k in ['TR','VA','TE'])
    if (folder/'evaluacion_TE.lock.json').exists():
        raise PaiError(f'{symbol}: TE ya fue evaluado. No se permite volver a seleccionar usando ese TE; reservar un periodo nuevo.')
    experiments=[];candidates={};configs=[]
    def register(name,family,variant,seed,neurons,m,sc,detail):
        for part in ['TR','VA']:
            sl=b['parts'][part];p=predict_model(m,sc,b[variant][sl])
            experiments.append({'id':name,'capitulo':8 if variant=='base' else 11,'modelo':family,
                                'variables':variant,'conjunto':part,'seed':seed,'neuronas':neurons,
                                'device':detail['device'],'seconds':detail['seconds'],'learning_rate':detail['learning_rate'],
                                'batch_size':detail['batch_size'],'epochs':detail['epochs'],'max_epochs':detail['max_epochs'],
                                'best_epoch':detail['best_epoch'],'parametros_entrenables':detail['parametros_entrenables'],
                                'model_sha256':detail['model_sha256'],'transformaciones':'StandardScaler X e y; ajuste solo TR',
                                **metrics(b['y'][sl],p)})
        candidates[name]=(m,sc,detail,variant)
    for family in ['MLP','LSTM']:
        trial=[]
        for neurons in config['neurons']:
            name=f'{family}_base_n{neurons}_s123'
            m,sc,d=_fit(tf,b['base'][tr],b['y'][tr],b['base'][va],b['y'][va],family,neurons,123,config,folder/name)
            register(name,family,'base',123,neurons,m,sc,d)
            trial.append((metrics(b['y'][va],predict_model(m,sc,b['base'][va]))['rmse'],neurons,name))
        _,best_n,best_name=min(trial)
        for seed in config['seeds'][1:]:
            name=f'{family}_base_n{best_n}_s{seed}'
            m,sc,d=_fit(tf,b['base'][tr],b['y'][tr],b['base'][va],b['y'][va],family,best_n,seed,config,folder/name)
            register(name,family,'base',seed,best_n,m,sc,d)
        # Se usa la semilla 123 predefinida; no se elige la mejor semilla.
        configs.append(best_name)
        name=f'{family}_indicadores_n{best_n}_s123'
        m,sc,d=_fit(tf,b['indicadores'][tr],b['y'][tr],b['indicadores'][va],b['y'][va],family,best_n,123,config,folder/name)
        register(name,family,'indicadores',123,best_n,m,sc,d);configs.append(name)
    exp=pd.DataFrame(experiments);exp.to_csv(folder/'experimentos.csv',index=False)
    # Resumen de tres semillas por mejor arquitectura base, sin escoger semilla.
    repeated=[]
    for family in ['MLP','LSTM']:
        base_name=next(n for n in configs if n.startswith(family+'_base'))
        n=candidates[base_name][2]['neuronas']
        group=exp[(exp.modelo==family)&(exp.variables=='base')&(exp.neuronas==n)&(exp.conjunto=='VA')]
        repeated.append({'modelo':family,'neuronas':n,'n_semillas':len(group),'rmse_media':group.rmse.mean(),
                         'rmse_sd':group.rmse.std(ddof=1),'mae_media':group.mae.mean(),'mae_sd':group.mae.std(ddof=1)})
    pd.DataFrame(repeated).to_csv(folder/'resumen_semillas.csv',index=False)
    ranked=exp[(exp.conjunto=='VA')&exp.id.isin(configs)].sort_values(['rmse','id'])
    winner=ranked.iloc[0]['id'];model,scalers,detail,variant=candidates[winner]
    predva=predict_model(model,scalers,b[variant][va])
    rule,threshold_table=choose_rule(b['meta'].iloc[va].reset_index(drop=True),predva,config['thresholds'])
    threshold_table.to_csv(folder/'umbrales_VA.csv',index=False)
    # Validación expansiva: tres bloques dentro de TR, con ES interno anterior al bloque evaluado.
    folds=[]
    for fold,(a,z) in enumerate(TimeSeriesSplit(n_splits=3).split(b[variant][tr]),1):
        inner=int(len(a)*.85);fit_ids=a[:inner];es_ids=a[inner:]
        m,s,d=_fit(tf,b[variant][fit_ids],b['y'][fit_ids],b[variant][es_ids],b['y'][es_ids],
                   detail['familia'],detail['neuronas'],123,config,folder/f'fold_{fold}')
        p=predict_model(m,s,b[variant][z]);folds.append({'fold':fold,'n_ajuste':len(fit_ids),
          'ultimo_entrenamiento':b['meta'].target_date.iloc[fit_ids[-1]],
          'primer_evaluado':b['meta'].target_date.iloc[z[0]],'ultimo_evaluado':b['meta'].target_date.iloc[z[-1]],
          **metrics(b['y'][z],p)})
    pd.DataFrame(folds).to_csv(folder/'ventanas_expansivas_TR.csv',index=False)
    # Recargar el modelo elegido: las llamadas de folds no alteran los pesos guardados.
    model=tf.keras.models.load_model(folder/winner/'modelo.keras')
    scalers=joblib.load(folder/winner/'escaladores.joblib')
    manifest={'version':'1.0.0','symbol':symbol,'source':'MEXC Spot','interval':'1d','timezone':'UTC',
      'target':'close_t_plus_1 / close_t - 1','lookback':20,'feature_variant':variant,
      'features':['return'] if variant=='base' else FEATURES,'selected_experiment':winner,'seed':123,
      'model':f'{winner}/modelo.keras','scalers':f'{winner}/escaladores.joblib',
      'model_sha256':digest(folder/winner/'modelo.keras'),'scalers_sha256':digest(folder/winner/'escaladores.joblib'),
      'data_sha256':digest(root/'data/processed'/f'{symbol}.csv'),'training_device':'NVIDIA T4 /GPU:0',
      'gpu_evidence_file':gpu_report['evidence_file'],'gpu_evidence_sha256':digest(root/gpu_report['evidence_file']),'t4_verified':True,
      'training':detail,'selection':'RMSE de VA; semilla 123 fijada; umbral y filtro por rendimiento y drawdown VA.',
      'frozen_at':datetime.now(timezone.utc).isoformat(),**rule}
    save_json(folder/'manifest.json',manifest)
    freeze=digest(folder/'manifest.json')
    save_json(folder/'evaluacion_TE.lock.json',{'manifest_sha256':freeze,'evaluated_at':datetime.now(timezone.utc).isoformat(),
              'TE_una_vez':True,'completado':False,'nota':'Evaluación iniciada; no volver a seleccionar con este TE.'})
    # TE se consulta después de serializar y congelar el sistema completo.
    final_rows=[];predictions=[]
    final_names=[('DL',None),('Lineal',linear[variant]),('Cero',None)]
    for label,obj in final_names:
        for part in ['TR','VA','TE']:
            sl=b['parts'][part]
            if label=='DL':p=predict_model(model,scalers,b[variant][sl])
            elif label=='Cero':p=np.zeros(len(b['y'][sl]))
            else:
                lm,sx=obj;p=lm.predict(transform(b[variant][sl],sx).reshape(len(b[variant][sl]),-1))
            final_rows.append({'modelo':label,'conjunto':part,'variables':variant,**metrics(b['y'][sl],p)})
            if part=='TE':
                q=b['meta'].iloc[sl].copy().reset_index(drop=True)
                q['modelo']=label;q['real']=b['y'][sl];q['estimado']=p;q['error']=p-q.real
                q['senal']=(p>rule['threshold'])&((q.close_t>q.sma20) if rule['technical_filter'] else True)
                predictions.append(q)
    final=pd.DataFrame(final_rows);final.to_csv(folder/'metricas_finales.csv',index=False)
    predte=pd.concat(predictions,ignore_index=True);predte.to_csv(folder/'predicciones_TE.csv',index=False)
    dl=predte[predte.modelo=='DL'].reset_index(drop=True)
    sims=[]
    for name,kwargs in [('Modelo',rule),('Comprar y mantener',{'passive':True}),('Efectivo',{'cash_only':True})]:
        curve,stat=simulate(dl,dl.estimado.to_numpy(),**kwargs)
        curve['estrategia']=name;sims.append(curve)
        save_json(folder/f'simulacion_{name.replace(" ","_")}.json',stat)
    pd.concat(sims,ignore_index=True).to_csv(folder/'simulacion.csv',index=False)
    eval_te=final[final.conjunto=='TE'].set_index('modelo')
    model_stat=json.loads((folder/'simulacion_Modelo.json').read_text())
    save_json(folder/'criterios_empiricos.json',{'dl_supera_lineal_rmse_TE':bool(eval_te.loc['DL','rmse']<eval_te.loc['Lineal','rmse']),
        'rentabilidad_superior_20pct_TE':bool(model_stat['rendimiento_neto']>.20),
        'nota':'Resultados observados, sin ajustar con TE. Pág. 1 exige estas mejoras; pág. 13 no exige rentabilidad positiva para candidatura. El profesor resuelve la contradicción.'})
    # El próximo objetivo no observado nunca recibe un valor real inventado.
    last=indicators(b['frame']).iloc[-20:]
    xx=last[manifest['features']].to_numpy(dtype='float32')[None,...]
    future=float(predict_model(model,scalers,xx)[0]);last_date=pd.to_datetime(last.close_time.iloc[-1],unit='ms',utc=True)
    pd.DataFrame([{'symbol':symbol,'fecha_corte':str(last_date),'proximo_periodo':str(last_date+pd.Timedelta(days=1)),
                   'estimado':future,'real':None,'senal':bool(future>rule['threshold'] and
                    (not rule['technical_filter'] or last.close.iloc[-1]>last.sma20.iloc[-1]))}]).to_csv(folder/'prediccion_futura.csv',index=False)
    reload_pred=predict_model(tf.keras.models.load_model(folder/winner/'modelo.keras'),
                              joblib.load(folder/winner/'escaladores.joblib'),b[variant][va][:5])
    assert np.allclose(reload_pred,predva[:5],rtol=1e-5,atol=1e-7)
    save_json(folder/'evaluacion_TE.lock.json',{'manifest_sha256':freeze,'evaluated_at':datetime.now(timezone.utc).isoformat(),
              'TE_una_vez':True,'completado':True,'nota':'Cambiar después la selección exige otro periodo de prueba.'})
    return manifest
