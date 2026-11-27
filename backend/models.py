from pathlib import Path
import json,joblib
import numpy as np
from pai.config import ROOT,PaiError,digest,symbols
from pai.features import indicators,transform

class Registry:
    def __init__(self,root=ROOT):self.root=Path(root);self.cache={}

    def contract(self,symbol):
        if symbol not in symbols():raise PaiError('Activo fuera del catálogo de 15 pares.')
        folder=self.root/'artifacts'/symbol;path=folder/'manifest.json'
        if not path.is_file():raise PaiError('Modelo pendiente: entrenar y exportar desde el cuaderno T4.')
        m=json.loads(path.read_text())
        if m.get('symbol')!=symbol or m.get('interval')!='1d' or m.get('source')!='MEXC Spot':raise PaiError('Contrato de activo, fuente o frecuencia no coincide.')
        if not m.get('t4_verified'):raise PaiError('Falta evidencia verificable de T4.')
        for key,hashkey in [('model','model_sha256'),('scalers','scalers_sha256')]:
            p=(folder/m[key]).resolve()
            if not p.is_relative_to(folder.resolve()) or not p.is_file() or digest(p)!=m[hashkey]:raise PaiError('Modelo o escalador alterado o ausente.')
        evidence=(self.root/m.get('gpu_evidence_file','evidencia/t4.json')).resolve()
        if not evidence.is_relative_to(self.root.resolve()):raise PaiError('Ruta de evidencia no permitida.')
        if not evidence.is_file() or digest(evidence)!=m['gpu_evidence_sha256']:raise PaiError('No coincide la evidencia T4 del modelo.')
        lock=folder/'evaluacion_TE.lock.json'
        if not lock.is_file() or not json.loads(lock.read_text()).get('completado',False):raise PaiError('La evaluación final del protocolo aún no está completa.')
        return m

    def forecast(self,symbol,frame):
        m=self.contract(symbol);folder=self.root/'artifacts'/symbol
        if symbol not in self.cache:
            try:
                import tensorflow as tf
                self.cache[symbol]=(tf.keras.models.load_model(folder/m['model']),joblib.load(folder/m['scalers']))
            except (ImportError,ValueError,OSError) as exc:raise PaiError('No se pudo cargar el modelo final; revisar versión de TensorFlow y exportación.') from exc
        model,sc=self.cache[symbol];f=indicators(frame);x=f[m['features']].iloc[-m['lookback']:].to_numpy(dtype='float32')
        if x.shape!=(m['lookback'],len(m['features'])) or not np.isfinite(x).all():raise PaiError('Variables insuficientes o no finitas para inferencia.')
        out=model.predict(transform(x[None,...],sc['x']),verbose=0)
        p=float(sc['y'].inverse_transform(out).ravel()[0])
        if not np.isfinite(p):raise PaiError('Pronóstico no finito; se bloqueó la decisión.')
        last=f.iloc[-1]
        return {'symbol':symbol,'close_ms':int(last.close_time),'forecast':p,'close':float(last.close),
                'open_ms':int(last.open_time),'open':float(last.open),'high':float(last.high),
                'low':float(last.low),'volume':float(last.volume),
                'vol20':float(last.vol20),'dist_sma20':float(last.dist_sma20),'sma20':float(last.sma20),
                'threshold':m['threshold'],'technical_filter':m['technical_filter'],'model_version':m['version'],
                'issue_date':str(__import__('pandas').to_datetime(last.close_time,unit='ms',utc=True)),
                'target_period':str(__import__('pandas').to_datetime(last.close_time,unit='ms',utc=True)+__import__('pandas').Timedelta(days=1))}
