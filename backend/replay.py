"""Histórico identificado: tres políticas, mismos días, riesgo, costos y fills."""
from pathlib import Path
import json,time
import pandas as pd
import numpy as np
from pai.config import project,PaiError,save_json,digest
from pai.features import samples
from .store import Store
from .paper import Paper

def summarize(store):
    rows=store.rows('SELECT * FROM equity ORDER BY id')
    initial=store.account()['initial'];path=np.r_[initial,[r['equity'] for r in rows]]
    drawdown=float(np.max(1-path/np.maximum.accumulate(path)))
    orders=store.rows('SELECT * FROM orders');closed=[float(o['pnl']) for o in orders if o['pnl'] is not None]
    decisions=store.rows('SELECT * FROM decisions')
    return {'rendimiento_neto':store.account()['equity']/initial-1,'max_drawdown':drawdown,
            'operaciones_cerradas':len(closed),'win_rate':float(np.mean(np.asarray(closed)>0)) if closed else None,
            'costos':sum(float(o['fee']) for o in orders),'latencia_llm_ms_media':float(np.mean([d['llm_ms'] for d in decisions])) if decisions else None,
            'acciones_rechazadas':sum(d['risk']!='OK' for d in decisions),'ciclos':len(decisions),
            'patrimonio_final':store.account()['equity']}

def run_replay(root,symbol,cycles,registry,llm):
    root=Path(root);manifest=registry.contract(symbol);llm_info=llm.health()
    data=root/'data/processed'/f'{symbol}.csv'
    if not data.is_file() or digest(data)!=manifest['data_sha256']:raise PaiError('Replay: no coincide la muestra congelada del entrenamiento.')
    frame=pd.read_csv(data);frame['date']=pd.to_datetime(frame['date'],utc=True)
    b=samples(frame);ids=b['meta'].iloc[b['parts']['TE']].origin_index.to_numpy()
    if len(ids)<cycles:raise PaiError('No hay suficientes orígenes de TE para el replay solicitado.')
    ids=ids[-cycles:];folder=root/'evidencia'/f'replay_{symbol}';folder.mkdir(parents=True,exist_ok=True)
    result_file=folder/'resumen.json'
    if result_file.exists():return json.loads(result_file.read_text())
    if (folder/'replay_iniciado.json').exists():raise PaiError('Replay previo interrumpido. Conservar evidencia y usar otro periodo independiente; no sobrescribir.')
    save_json(folder/'replay_iniciado.json',{'symbol':symbol,'cycles':cycles,'llm':llm_info,'manifest_sha256':digest(root/'artifacts'/symbol/'manifest.json'),
               'mode':'replay','first_issue':str(pd.to_datetime(frame.close_time.iloc[ids[0]],unit='ms',utc=True)),
               'last_target':str(pd.to_datetime(frame.close_time.iloc[ids[-1]+1],unit='ms',utc=True))})
    info=json.loads((root/'data/raw'/f'{symbol}.json').read_text())['exchange_info']
    stores={};papers={};risk=project()['paper'];messages=[]
    for name in ['modelo_sin_llm','agente_con_llm','comprar_y_mantener']:
        stores[name]=Store(folder/f'{name}.sqlite',str(risk['initial_cash']));stores[name].status('running')
        papers[name]=Paper(stores[name],risk)
    try:
        for index in ids:
            snapshot=registry.forecast(symbol,frame.iloc[:index+1].copy())
            nxt=frame.iloc[index+1];quote={'bid':float(nxt.open),'ask':float(nxt.open),'observed_at_ms':int(nxt.open_time)}
            for name,store in stores.items():
                account=store.account();held=any(p['symbol']==symbol and p['qty']>0 for p in account['positions'])
                threshold=manifest['threshold'];signal=snapshot['forecast']>threshold and (not manifest['technical_filter'] or snapshot['dist_sma20']>0)
                latency=0.;tools=[]
                if name=='agente_con_llm':
                    proposal,latency,tools=llm.propose(snapshot,account)
                    messages.append({'close_ms':snapshot['close_ms'],'evidence':llm.evidence})
                else:
                    buy=(not held) if name=='comprar_y_mantener' else signal
                    action='BUY' if buy and not held else 'SELL' if name=='modelo_sin_llm' and not signal and held else 'HOLD'
                    proposal={'symbol':symbol,'candle_close_ms':snapshot['close_ms'],'action':action,
                              'reason':'Política de referencia congelada antes de la evaluación.'}
                papers[name].apply(snapshot,proposal,quote,info,latency,'replay_passive' if name=='comprar_y_mantener' else 'replay',tools)
                # El cierre futuro solo valora la cartera después de ejecutar en la apertura.
                papers[name].mark(symbol,float(nxt.close),int(nxt.close_time)-1)
        last=frame.iloc[ids[-1]+1]
        end_quote={'bid':float(last.close),'ask':float(last.close),'observed_at_ms':int(last.close_time)}
        comparison=[]
        for name,store in stores.items():
            if any(p['symbol']==symbol and p['qty']>0 for p in store.account()['positions']):papers[name].liquidate(symbol,end_quote,info)
            stat=summarize(store);stat.update(estrategia=name);comparison.append(stat)
            for table in ['decisions','orders','equity','events']:
                pd.DataFrame(store.rows('SELECT * FROM '+table)).to_csv(folder/f'{name}_{table}.csv',index=False)
        result={'symbol':symbol,'mode':'replay','cycles':cycles,'comparison':comparison,
                'first_issue':str(pd.to_datetime(frame.close_time.iloc[ids[0]],unit='ms',utc=True)),
                'last_target':str(pd.to_datetime(last.close_time,unit='ms',utc=True)),
                'initial_cash':risk['initial_cash'],'fee':risk['fee'],'slippage_bps':risk['slippage_bps'],
                'same_risk_limits':True,'passive_allocation':risk['max_asset_exposure'],
                'note':'Replay histórico; supuesto de ejecución en apertura siguiente, con deslizamiento idéntico. No es conexión actual ni prueba estadística.'}
        pd.DataFrame(comparison).to_csv(folder/'comparacion.csv',index=False)
        save_json(folder/'ollama_ciclos.json',messages);save_json(result_file,result)
        save_json(root/'evidencia/replay_resumen.json',result)
        if messages:save_json(root/'evidencia/ollama_local.json',messages[-1]['evidence'])
        return result
    finally:
        for store in stores.values():store.close()
