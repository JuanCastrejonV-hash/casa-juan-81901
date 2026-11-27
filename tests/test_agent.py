import asyncio,json
from pathlib import Path
import httpx,pytest
from fastapi.testclient import TestClient
from pai.config import PaiError
from pai.data import DAY_MS
from backend.store import Store
from backend.paper import Paper
from backend.app import create_app,Settings
from backend.llm import OllamaLocal
from backend.engine import Engine

def test_insufficient_balance_no_order(store,paper,snap,proposal,book,info):
    with store.transaction() as c:store.set('cash','0',c)
    result=paper.apply(snap,proposal,book,info)
    assert result['risk']=='INSUFFICIENT_BALANCE' and not store.rows('SELECT * FROM orders')

def test_duplicate_event_is_idempotent(store,paper,snap,proposal,book,info):
    first=paper.apply(snap,proposal,book,info);balance=store.account()['cash']
    second=paper.apply(snap,proposal,book,info)
    assert first['executed'] and second['duplicate'] and store.account()['cash']==balance
    assert len(store.rows('SELECT * FROM orders'))==1

def test_restart_recovers_and_does_not_duplicate(tmp_path,risk,snap,proposal,book,info):
    path=tmp_path/'restart.sqlite';s=Store(path);s.status('running');p=Paper(s,risk)
    p.apply(snap,proposal,book,info);old=s.account();s.close()
    s=Store(path);assert s.status()=='paused';s.status('running')
    result=Paper(s,risk).apply(snap,proposal,book,info)
    assert result['duplicate'] and s.account()['cash']==old['cash']
    assert len(s.rows('SELECT * FROM orders'))==1;s.close()

def test_stop_preserves_position_and_blocks_inflight(store,paper,snap,proposal,book,info):
    paper.apply(snap,proposal,book,info);qty=store.account()['positions'][0]['qty'];store.status('stopped')
    nxt={**snap,'close_ms':snap['close_ms']+DAY_MS}
    prop={**proposal,'action':'SELL','candle_close_ms':nxt['close_ms']}
    result=paper.apply(nxt,prop,{**book,'observed_at_ms':book['observed_at_ms']+DAY_MS},info)
    assert result['risk']=='STOPPED' and store.account()['positions'][0]['qty']==qty
    assert len(store.rows('SELECT * FROM orders'))==1

def test_daily_loss_pauses(store,paper,snap,proposal,book,info):
    paper.apply(snap,proposal,book,info)
    paper.mark('BTCUSDT',50,book['observed_at_ms']+5000)
    assert store.status()=='paused' and store.rows('SELECT * FROM events WHERE code="DAILY_LOSS"')

def test_exposure_limit(store,risk,snap,proposal,book,info):
    risk['max_total_exposure']=.15;p=Paper(store,risk);p.apply(snap,proposal,book,info)
    s={**snap,'symbol':'ETHUSDT'};q={**proposal,'symbol':'ETHUSDT'}
    result=p.apply(s,q,book,{**info,'symbol':'ETHUSDT'})
    assert result['risk']=='EXPOSURE_LIMIT' and len(store.rows('SELECT * FROM orders'))==1

def test_stale_data_blocks_order(store,paper,snap,proposal,book,info):
    with pytest.raises(PaiError,match='atrasado'):paper.apply(snap,proposal,{**book,'observed_at_ms':book['observed_at_ms']+2*DAY_MS},info)
    assert not store.rows('SELECT * FROM orders')

def test_wrong_symbol_is_rejected(store,paper,snap,proposal,book,info):
    with pytest.raises(PaiError,match='símbolo'):paper.apply(snap,{**proposal,'symbol':'ETHUSDT'},book,info)
    assert not store.rows('SELECT * FROM orders')

def test_no_short_sales(store,paper,snap,proposal,book,info):
    result=paper.apply(snap,{**proposal,'action':'SELL'},book,info)
    assert result['risk']=='NO_POSITION' and not store.rows('SELECT * FROM orders')

def test_llm_cannot_bypass_frozen_model_signal(store,paper,snap,proposal,book,info):
    result=paper.apply({**snap,'forecast':-.01},proposal,book,info)
    assert result['risk']=='MODEL_SIGNAL' and not store.rows('SELECT * FROM orders')

def test_liquidate_requires_explicit_method(store,paper,snap,proposal,book,info):
    paper.apply(snap,proposal,book,info);store.status('stopped')
    paper.liquidate('BTCUSDT',book,info)
    assert store.account()['positions'][0]['qty']==0 and len(store.rows('SELECT * FROM orders'))==2
    assert store.status()=='stopped'

def test_api_key_and_gateway_reject_missing_or_wrong(tmp_path):
    s=Settings('a'*40,'g'*40,'s'*40,root=tmp_path)
    app=create_app(s,store=Store(tmp_path/'auth.sqlite'))
    with TestClient(app) as c:
        assert c.get('/api/state').status_code==401
        assert c.get('/api/state',headers={'X-API-Key':'wrong'}).status_code==401
        assert c.post('/api/control/stop',headers={'X-API-Key':'wrong'},json={}).status_code==401
        assert c.post('/api/llm/propose',json={'snapshot':{},'portfolio':{}}).status_code==401
        assert c.get('/api/state',headers={'X-API-Key':'a'*40}).status_code==200
        assert c.post('/api/orders/real',headers={'X-API-Key':'a'*40},json={}).status_code==404
        assert c.get('/api/health').json()['real_orders_enabled'] is False
    app.state.store.close()

def test_cookie_session_httponly_and_write_guard(tmp_path):
    s=Settings('a'*40,'g'*40,'s'*40,root=tmp_path);app=create_app(s,store=Store(tmp_path/'cookie.sqlite'))
    with TestClient(app) as c:
        r=c.post('/api/login',json={'api_key':'a'*40});assert 'HttpOnly' in r.headers['set-cookie']
        assert c.get('/api/state').status_code==200
        assert c.post('/api/control/stop',json={}).status_code==403
        assert c.post('/api/control/stop',headers={'X-Requested-With':'PAI'},json={}).status_code==200
    app.state.store.close()

def test_ollama_down_stops():
    def fail(req):raise httpx.ConnectError('Controlado: servicio detenido',request=req)
    llm=OllamaLocal(transport=httpx.MockTransport(fail))
    with pytest.raises(PaiError,match='detenido'):llm.health()

def test_llm_invalid_json_is_rejected(snap,store):
    def respond(req):
        if req.url.path=='/api/version':return httpx.Response(200,json={'version':'test'})
        if req.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'qwen3:0.6b','digest':'test'}]})
        if req.url.path=='/api/show':return httpx.Response(200,json={})
        return httpx.Response(200,json={'message':{'role':'assistant','content':'no es JSON'}})
    llm=OllamaLocal(transport=httpx.MockTransport(respond))
    with pytest.raises(PaiError,match='JSON inválido'):llm.propose(snap,store.account())
    assert not store.rows('SELECT * FROM orders')

def test_llm_cannot_call_write_tools(snap,store):
    def respond(req):
        if req.url.path=='/api/version':return httpx.Response(200,json={'version':'test'})
        if req.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'qwen3:0.6b'}]})
        if req.url.path=='/api/show':return httpx.Response(200,json={})
        return httpx.Response(200,json={'message':{'role':'assistant','tool_calls':[{'function':{'name':'cambiar_riesgo','arguments':{}}}]}})
    llm=OllamaLocal(transport=httpx.MockTransport(respond))
    with pytest.raises(PaiError,match='no autorizada'):llm.propose(snap,store.account())

def test_cloud_llm_is_not_allowed():
    with pytest.raises(PaiError,match='loopback'):OllamaLocal(url='https://ollama.com')
    with pytest.raises(PaiError,match='cloud'):OllamaLocal(model='model-cloud')

def test_engine_dependency_failure_pauses_without_orders(store):
    class Registry:
        def contract(self,s):return {}
    class Market:
        def server_time(self):raise PaiError('API sin respuesta: fallo controlado.')
    engine=Engine(store,Registry(),object(),Market())
    with pytest.raises(PaiError,match='sin respuesta'):asyncio.run(engine.once('BTCUSDT'))
    assert store.status()=='paused' and not store.rows('SELECT * FROM orders')
    assert store.rows('SELECT * FROM events WHERE code="DEPENDENCY_ERROR"')

def test_t4_guard_does_not_fallback_to_cpu(tmp_path,monkeypatch):
    import importlib.util
    original=importlib.util.find_spec
    monkeypatch.setattr(importlib.util,'find_spec',lambda name,*a,**kw: None if name=='google.colab' else original(name,*a,**kw))
    from pai.training import require_t4
    with pytest.raises(PaiError):require_t4(tmp_path)
    assert (tmp_path/'evidencia/bitacora.jsonl').is_file()
    assert not (tmp_path/'evidencia/t4.json').exists()
