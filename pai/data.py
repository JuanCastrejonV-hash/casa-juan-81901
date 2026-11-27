"""Únicamente GET de mercado público; ninguna ruta de órdenes de MEXC."""
from pathlib import Path
from datetime import datetime,timezone
import time, json, hashlib
import httpx
import numpy as np
import pandas as pd
from .config import ROOT, PaiError, project, symbols, save_json, digest

DAY_MS=86400000
KLINE_MAX=500
ALLOWED_PATHS={'/api/v3/time','/api/v3/exchangeInfo','/api/v3/klines',
               '/api/v3/ticker/bookTicker','/api/v3/ticker/price'}

class MexcPublic:
    def __init__(self, transport=None, retries=3, backoff=0.3):
        self.client=httpx.Client(base_url='https://api.mexc.com',timeout=12,
                                  transport=transport,follow_redirects=False)
        self.retries=retries;self.backoff=backoff

    def close(self):self.client.close()

    def get(self,path,params=None):
        if path not in ALLOWED_PATHS:
            raise PaiError('Ruta bloqueada: solo se permiten consultas públicas de mercado.')
        for attempt in range(self.retries):
            try:
                r=self.client.get(path,params=params)
                if r.status_code==429 or r.status_code>=500:
                    if attempt+1<self.retries:
                        time.sleep(min(self.backoff*2**attempt,2));continue
                r.raise_for_status()
                data=r.json()
                if isinstance(data,dict) and 'code' in data and data['code'] not in (0,200):
                    raise PaiError(f'MEXC devolvió código {data["code"]}; revisar disponibilidad del par.')
                return data
            except (httpx.TimeoutException,httpx.NetworkError) as exc:
                if attempt+1==self.retries:raise PaiError('MEXC sin respuesta tras reintentos limitados.') from exc
                time.sleep(min(self.backoff*2**attempt,2))
            except httpx.HTTPStatusError as exc:
                raise PaiError(f'MEXC HTTP {exc.response.status_code}; no se reemplazan datos por valores simulados.') from exc
            except (json.JSONDecodeError,UnicodeDecodeError) as exc:
                raise PaiError('MEXC respondió con un formato no válido.') from exc
        raise PaiError('MEXC no pudo completar la consulta.')

    def server_time(self):return int(self.get('/api/v3/time')['serverTime'])

    def info(self,symbol):
        if symbol not in symbols():raise PaiError('Símbolo no autorizado.')
        response=self.get('/api/v3/exchangeInfo',{'symbol':symbol})
        rows=response.get('symbols',[]) if isinstance(response,dict) else []
        if not rows and isinstance(response,dict) and response.get('symbol')==symbol:rows=[response]
        item=next((r for r in rows if r.get('symbol')==symbol),None)
        if not item:raise PaiError(f'{symbol}: sin metadatos actuales de MEXC.')
        if str(item.get('status')) not in ('1','ENABLED','TRADING'):
            raise PaiError(f'{symbol}: par no disponible, estado {item.get("status")}.')
        if item.get('quoteAsset')!='USDT':raise PaiError('Moneda cotizada inesperada.')
        return item

    def candles(self,symbol,limit=120,start=None,end=None,*,allow_empty=False):
        if symbol not in symbols():raise PaiError('Símbolo no autorizado.')
        params={'symbol':symbol,'interval':'1d','limit':min(int(limit),KLINE_MAX)}
        if start is not None:params['startTime']=int(start)
        if end is not None:params['endTime']=int(end)
        rows=self.get('/api/v3/klines',params)
        if not isinstance(rows,list) or (not rows and not allow_empty):
            raise PaiError(f'{symbol}: respuesta de velas vacía o de formato incorrecto.')
        if not all(isinstance(x,list) and len(x)>=8 for x in rows):raise PaiError('Formato de velas MEXC incorrecto.')
        return rows

    def book(self,symbol):
        row=self.get('/api/v3/ticker/bookTicker',{'symbol':symbol})
        if isinstance(row,list):row=next((x for x in row if x.get('symbol')==symbol),{})
        try:bid,ask=float(row['bidPrice']),float(row['askPrice'])
        except (KeyError,TypeError,ValueError) as exc:raise PaiError('Cotización de ejecución incompleta.') from exc
        if not np.isfinite([bid,ask]).all() or not 0<bid<=ask:raise PaiError('Cotización de ejecución no válida.')
        return {'bid':bid,'ask':ask,'observed_at_ms':self.server_time()}

def rows_frame(rows):
    if not rows:raise PaiError('Conjunto vacío: no se construyen ventanas.')
    cols=['open_time','open','high','low','close','volume','close_time','quote_volume']
    if not all(len(row)>=8 for row in rows):raise PaiError('Dimensiones de velas: se esperan al menos ocho campos.')
    frame=pd.DataFrame([r[:8] for r in rows],columns=cols)
    for col in cols:frame[col]=pd.to_numeric(frame[col],errors='coerce')
    frame['date']=pd.to_datetime(frame['open_time'],unit='ms',utc=True)
    return frame

def audit(frame,now_ms,min_rows=1500,repair_duplicates=True):
    if frame is None or frame.empty:raise PaiError('Conjunto vacío: descarga o archivo sin observaciones.')
    need={'date','open_time','close_time','open','high','low','close','volume','quote_volume'}
    if not need.issubset(frame.columns):raise PaiError('Faltan columnas del contrato OHLCV diario.')
    f=frame.copy();f['date']=pd.to_datetime(f['date'],utc=True,errors='coerce')
    report={'filas_originales':len(f),'fuera_de_orden':not f['date'].is_monotonic_increasing,
            'duplicadas':int(f['open_time'].duplicated().sum()),'regla_duplicados':'Conservar última respuesta por apertura; ordenar.'}
    if report['duplicadas'] and not repair_duplicates:raise PaiError('Fecha duplicada: se detuvo la copia de prueba.')
    f=f.drop_duplicates('open_time',keep='last').sort_values('open_time').reset_index(drop=True)
    nums=['open_time','close_time','open','high','low','close','volume','quote_volume']
    for c in nums:f[c]=pd.to_numeric(f[c],errors='coerce')
    if f['date'].isna().any() or not np.isfinite(f[nums].to_numpy(dtype=float)).all():
        raise PaiError('Dato no válido: fecha, faltante, infinito o columna no numérica; corregir la fuente.')
    if (f[['open','high','low','close']]<=0).any().any() or (f[['volume','quote_volume']]<0).any().any():
        raise PaiError('Dato no válido: precio no positivo o volumen negativo.')
    if ((f.high<f[['open','close','low']].max(axis=1))|(f.low>f[['open','close','high']].min(axis=1))).any():
        raise PaiError('OHLC inconsistente: el máximo o mínimo no contiene apertura y cierre.')
    durations=f['close_time']-f['open_time']
    if not durations.between(DAY_MS-1,DAY_MS).all():raise PaiError('Frecuencia incorrecta: se requieren velas diarias completas.')
    report['velas_abiertas_descartadas']=int((f['close_time']>now_ms).sum())
    f=f.loc[f['close_time']<=now_ms].copy().reset_index(drop=True)
    if len(f)<min_rows:raise PaiError(f'Historia insuficiente: {len(f)} observaciones válidas; se requieren {min_rows}.')
    if not (f['open_time'].diff().dropna()==DAY_MS).all():
        raise PaiError('Hay días faltantes en el calendario continuo: no se rellenan; revisar la fuente.')
    if not (f['date'].astype('int64')//10**6==f['open_time'].astype('int64')).all():
        raise PaiError('Fecha no alineada con la apertura de la vela.')
    report.update(filas_validas=len(f),inicio=f['date'].iloc[0].isoformat(),fin=f['date'].iloc[-1].isoformat(),
                  timezone='UTC',ajustes='Sin dividendos ni particiones bursátiles. No se rellenan huecos.')
    return f,report

def download(symbol,root=ROOT):
    """Paginar por fecha hacia atrás, conservar respuesta original y auditar."""
    root=Path(root);api=MexcPublic()
    try:
        info=api.info(symbol);now=api.server_time();end=now
        all_rows=[]
        closed_opens=set()
        for _ in range(12):
            start=end-KLINE_MAX*DAY_MS+1
            rows=api.candles(symbol,KLINE_MAX,start=start,end=end,allow_empty=True)
            if not rows:break
            try:
                opens=[int(row[0]) for row in rows]
                closes=[int(row[6]) for row in rows]
            except (TypeError,ValueError,OverflowError) as exc:
                raise PaiError(f'{symbol}: marca de tiempo no válida en las velas MEXC.') from exc
            earliest=min(opens)
            if earliest<start or max(opens)>end:
                raise PaiError(f'{symbol}: MEXC devolvió velas fuera del intervalo solicitado.')
            all_rows.extend(rows)
            closed_opens.update(opened for opened,closed in zip(opens,closes) if closed<=now)
            if len(closed_opens)>=2200:break
            end=earliest-1
            time.sleep(0.15)
        stamp=datetime.now(timezone.utc).isoformat()
        raw=root/'data/raw'/f'{symbol}.json'
        save_json(raw,{'symbol':symbol,'interval':'1d','downloaded_at':stamp,'server_time':now,
                       'source':'https://api.mexc.com/api/v3/klines','exchange_info':info,'rows':all_rows})
        f,report=audit(rows_frame(all_rows),now,project()['minimum_observations'])
        dest=root/'data/processed'/f'{symbol}.csv';dest.parent.mkdir(parents=True,exist_ok=True);f.to_csv(dest,index=False)
        report.update(symbol=symbol,source='MEXC Spot',downloaded_at=stamp,quote='USDT',
                      sha256_raw=digest(raw),sha256_processed=digest(dest))
        save_json(root/'data/processed'/f'{symbol}_auditoria.json',report)
        return report
    finally:api.close()
