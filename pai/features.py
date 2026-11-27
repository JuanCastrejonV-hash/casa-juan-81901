import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from .config import PaiError

FEATURES=['return','dist_sma20','vol20']

def indicators(frame):
    f=frame.copy();p=f['close'].astype(float)
    f['return']=p.pct_change(fill_method=None)
    f['sma20']=p.rolling(20,min_periods=20).mean()
    f['dist_sma20']=p/f['sma20']-1
    f['vol20']=f['return'].rolling(20,min_periods=20).std(ddof=1)
    # Los primeros valores no se rellenan hacia atrás.
    return f

def samples(frame,lookback=20):
    f=indicators(frame).reset_index(drop=True)
    xb=[];xi=[];y=[];rows=[]
    for t in range(lookback-1,len(f)-1):
        a=f.iloc[t-lookback+1:t+1][FEATURES].to_numpy(dtype=float)
        if not np.isfinite(a).all():continue
        target=float(f.close.iloc[t+1]/f.close.iloc[t]-1)
        xb.append(a[:,0:1]);xi.append(a);y.append(target)
        rows.append({'origin_index':t,
                     'issue_date':str(pd.to_datetime(f.close_time.iloc[t],unit='ms',utc=True)),
                     'target_date':str(pd.to_datetime(f.close_time.iloc[t+1],unit='ms',utc=True)),
                     'execution_date':str(pd.to_datetime(f.open_time.iloc[t+1],unit='ms',utc=True)),
                     'input_first_date':str(pd.to_datetime(f.close_time.iloc[t-lookback+1],unit='ms',utc=True)),
                     'input_last_date':str(pd.to_datetime(f.close_time.iloc[t],unit='ms',utc=True)),
                     'close_t':float(f.close.iloc[t]),'open_next':float(f.open.iloc[t+1]),
                     'close_next':float(f.close.iloc[t+1]),'sma20':float(f.sma20.iloc[t]),
                     'vol20':float(f.vol20.iloc[t]),'dist_sma20':float(f.dist_sma20.iloc[t])})
    if not xb:raise PaiError('Ventanas insuficientes: no hay historia válida con rezagos e indicadores.')
    xb=np.asarray(xb,dtype='float32');xi=np.asarray(xi,dtype='float32');y=np.asarray(y,dtype=float)
    validate_shape(xb,lookback,1);validate_shape(xi,lookback,3)
    n=len(y);a=int(n*.70);b=int(n*.85)
    if min(a,b-a,n-b)<3:raise PaiError('Particiones insuficientes para TR, VA y TE.')
    parts={'TR':slice(0,a),'VA':slice(a,b),'TE':slice(b,n)}
    meta=pd.DataFrame(rows)
    assert (pd.to_datetime(meta.input_last_date)<=pd.to_datetime(meta.issue_date)).all()
    assert (pd.to_datetime(meta.issue_date)<pd.to_datetime(meta.target_date)).all()
    assert pd.Timestamp(meta.target_date.iloc[a-1])<pd.Timestamp(meta.target_date.iloc[a])
    assert pd.Timestamp(meta.target_date.iloc[b-1])<pd.Timestamp(meta.target_date.iloc[b])
    return {'base':xb,'indicadores':xi,'y':y,'meta':meta,'parts':parts,'frame':f}

def validate_shape(x,steps=20,variables=1):
    if x.ndim!=3 or x.shape[1:]!=(steps,variables) or len(x)==0:
        raise PaiError(f'Dimensiones incorrectas: esperado (ejemplos,{steps},{variables}); recibido {x.shape}.')
    if not np.isfinite(x).all():raise PaiError('Ventana con datos no finitos.')

def fit_scaler(x):
    return StandardScaler().fit(x.reshape(-1,x.shape[-1]))

def transform(x,scaler):
    return scaler.transform(x.reshape(-1,x.shape[-1])).reshape(x.shape).astype('float32')

def metrics(real,pred):
    y,p=np.asarray(real,dtype=float).ravel(),np.asarray(pred,dtype=float).ravel()
    if y.shape!=p.shape or not len(y) or not np.isfinite(np.r_[y,p]).all():raise PaiError('Métricas: formas o valores no válidos.')
    e=p-y
    return {'n':len(y),'mae':float(np.mean(np.abs(e))),'rmse':float(np.sqrt(np.mean(e**2))),
            'acierto_direccional':float(np.mean(np.sign(y)==np.sign(p))),
            'pred_std':float(np.std(p)),'real_std':float(np.std(y))}
