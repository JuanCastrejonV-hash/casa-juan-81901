import json
from pathlib import Path
from pai.config import digest
from backend.replay import run_replay

def test_replay_30_cycles_is_separate_and_reproducible(tmp_path,frame,info):
    # Integración con FIXTURES SINTÉTICOS. No acredita 30 ciclos de mercado.
    raw=tmp_path/'data/raw';processed=tmp_path/'data/processed';artifact=tmp_path/'artifacts/BTCUSDT'
    for p in [raw,processed,artifact]:p.mkdir(parents=True)
    source=processed/'BTCUSDT.csv';frame.to_csv(source,index=False)
    (raw/'BTCUSDT.json').write_text(json.dumps({'exchange_info':info}))
    manifest={'symbol':'BTCUSDT','threshold':.001,'technical_filter':False,'data_sha256':digest(source)}
    (artifact/'manifest.json').write_text(json.dumps(manifest))
    class Registry:
        def contract(self,symbol):return manifest
        def forecast(self,symbol,f):
            r=f.iloc[-1]
            return {'symbol':symbol,'close_ms':int(r.close_time),'forecast':.002,'close':float(r.close),
                    'sma20':float(r.close)-1,'dist_sma20':.01,'vol20':.01,'threshold':.001}
    class LLM:
        evidence={'mode':'TEST_FIXTURE_NOT_MARKET'}
        def health(self):return {'local':True,'mode':'TEST_FIXTURE_NOT_MARKET'}
        def propose(self,snapshot,account):
            held=any(p['qty']>0 for p in account['positions'])
            return {'symbol':snapshot['symbol'],'candle_close_ms':snapshot['close_ms'],
                    'action':'HOLD' if held else 'BUY','reason':'Fixture controlado de prueba.'},1.0,[]
    result=run_replay(tmp_path,'BTCUSDT',30,Registry(),LLM())
    assert result['mode']=='replay' and result['cycles']==30
    assert len(result['comparison'])==3 and all(x['ciclos']==30 for x in result['comparison'])
    assert result['same_risk_limits'] and result['fee']==0
    again=run_replay(tmp_path,'BTCUSDT',30,Registry(),LLM())
    assert again==result
