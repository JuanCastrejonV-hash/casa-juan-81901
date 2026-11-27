import numpy as np
import pandas as pd
import httpx,pytest
from pai.config import PaiError
from pai.data import audit,rows_frame,MexcPublic
from pai.features import samples,validate_shape,fit_scaler,transform
from pai.backtest import simulate,choose_rule

def test_empty_data_stops():
    with pytest.raises(PaiError,match='vacío'):rows_frame([])

def test_duplicate_date_stops_and_documented_repair(frame):
    repeated=pd.concat([frame,frame.iloc[[20]]],ignore_index=True)
    with pytest.raises(PaiError,match='duplicada'):audit(repeated,int(frame.close_time.iloc[-1])+1,repair_duplicates=False)
    result,report=audit(repeated,int(frame.close_time.iloc[-1])+1)
    assert len(result)==1600 and report['duplicadas']==1 and result.date.is_unique
    assert len(repeated)==1601  # La prueba no corrompe la fuente.

def test_invalid_price_stops(frame):
    bad=frame.copy();bad.loc[100,'close']=np.nan
    with pytest.raises(PaiError,match='no válido'):audit(bad,int(frame.close_time.iloc[-1])+1)

def test_dimensions_stop():
    with pytest.raises(PaiError,match='Dimensiones'):validate_shape(np.ones((7,20)),20,1)

def test_calendar_gap_not_filled(frame):
    with pytest.raises(PaiError,match='faltantes'):audit(frame.drop(index=100),int(frame.close_time.iloc[-1])+1)

def test_open_candle_excluded(frame):
    x,r=audit(frame,int(frame.close_time.iloc[-2]),min_rows=1500)
    assert len(x)==1599 and r['velas_abiertas_descartadas']==1

def test_target_splits_and_context_are_causal(frame):
    b=samples(frame);tr,va,te=[b['parts'][x] for x in ['TR','VA','TE']]
    assert b['meta'].target_date.iloc[tr.stop-1]<b['meta'].target_date.iloc[va.start]
    assert b['meta'].target_date.iloc[va.stop-1]<b['meta'].target_date.iloc[te.start]
    i=100;t=b['meta'].origin_index.iloc[i]
    assert pd.Timestamp(b['meta'].issue_date.iloc[i]).value//10**6==frame.close_time.iloc[t]
    assert pd.Timestamp(b['meta'].execution_date.iloc[i]).value//10**6==frame.open_time.iloc[t+1]
    assert b['y'][i]==pytest.approx(frame.close.iloc[t+1]/frame.close.iloc[t]-1)
    changed=frame.copy();changed.loc[t+1:,'close']*=5
    c=samples(changed)
    assert np.array_equal(b['indicadores'][:i+1],c['indicadores'][:i+1])

def test_scaler_uses_only_TR(frame):
    b=samples(frame);tr=b['parts']['TR'];sc=fit_scaler(b['indicadores'][tr])
    assert np.allclose(sc.mean_,b['indicadores'][tr].reshape(-1,3).mean(axis=0),rtol=1e-5,atol=1e-6)
    baseline=sc.mean_.copy();changed=b['indicadores'].copy();changed[tr.stop:]*=1000
    assert np.array_equal(fit_scaler(changed[tr]).mean_,baseline)

def test_mexc_rate_limit_is_bounded():
    calls=[]
    def respond(req):calls.append(req);return httpx.Response(429,json={'code':429})
    api=MexcPublic(httpx.MockTransport(respond),retries=3,backoff=0)
    with pytest.raises(PaiError,match='HTTP 429'):api.server_time()
    assert len(calls)==3;api.close()

def test_mexc_timeout_is_bounded():
    calls=[]
    def respond(req):calls.append(req);raise httpx.ReadTimeout('Prueba',request=req)
    api=MexcPublic(httpx.MockTransport(respond),retries=3,backoff=0)
    with pytest.raises(PaiError,match='sin respuesta'):api.server_time()
    assert len(calls)==3;api.close()

def test_real_order_route_cannot_be_requested():
    api=MexcPublic(httpx.MockTransport(lambda r:pytest.fail('Nunca debe consultar una orden real.')))
    with pytest.raises(PaiError,match='Ruta bloqueada'):api.get('/api/v3/order')
    api.close()

def test_backtest_next_open_and_both_fees():
    m=pd.DataFrame([{'issue_date':'2025-01-01','target_date':'2025-01-02','close_t':100.,'sma20':99.,'open_next':110.,'close_next':120.}])
    curve,stat=simulate(m,[.01],.001,fee=.001)
    expected=(100000/(110*1.001))*120*.999
    assert stat['patrimonio_final']==pytest.approx(expected)
    assert stat['operaciones_cerradas']==1 and stat['win_rate']==1
    assert curve.iloc[0].liquidacion_final and stat['costos_totales']>0

def test_no_trade_winrate_is_undefined():
    m=pd.DataFrame([{'issue_date':'2025-01-01','target_date':'2025-01-02','close_t':100.,'sma20':99.,'open_next':110.,'close_next':120.}])
    _,stat=simulate(m,[-.01],.001)
    assert stat['win_rate'] is None and stat['costos_totales']==0
