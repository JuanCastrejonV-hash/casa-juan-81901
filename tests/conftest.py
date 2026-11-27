from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pai.data import DAY_MS
from pai.config import project
from backend.store import Store
from backend.paper import Paper

@pytest.fixture
def frame():
    # DATOS SINTÉTICOS EXCLUSIVAMENTE PARA PRUEBAS; nunca se presentan como mercado.
    n=1600;dates=pd.date_range('2021-01-01',periods=n,freq='D',tz='UTC')
    t=np.arange(n);close=100+0.02*t+2*np.sin(t/17)
    stamp=dates.astype('int64')//10**6
    return pd.DataFrame({'date':dates,'open_time':stamp,'close_time':stamp+DAY_MS-1,
                         'open':close-.1,'high':close+1,'low':close-1,'close':close,
                         'volume':np.ones(n)*100,'quote_volume':np.ones(n)*10000})

@pytest.fixture
def info():
    return {'symbol':'BTCUSDT','status':'1','baseAsset':'BTC','quoteAsset':'USDT',
            'baseAssetPrecision':5,'quotePrecision':2,'quoteAssetPrecision':2,
            'baseSizePrecision':'0.00001','quoteAmountPrecision':'5','maxQuoteAmount':'10000000'}

@pytest.fixture
def snap():
    return {'symbol':'BTCUSDT','close_ms':1763510399999,'forecast':.01,'close':100.,
            'sma20':99.,'vol20':.01,'dist_sma20':.0101,'threshold':.001,'technical_filter':False}

@pytest.fixture
def book(snap):return {'bid':100.,'ask':100.,'observed_at_ms':snap['close_ms']+1}

@pytest.fixture
def proposal(snap):return {'symbol':'BTCUSDT','candle_close_ms':snap['close_ms'],'action':'BUY','reason':'Propuesta de prueba controlada.'}

@pytest.fixture
def risk():
    r=project()['paper'].copy();r['slippage_bps']=0;return r

@pytest.fixture
def store(tmp_path):
    s=Store(tmp_path/'unit.sqlite');s.status('running');yield s;s.close()

@pytest.fixture
def paper(store,risk):return Paper(store,risk)
