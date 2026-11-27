from pathlib import Path
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal
from datetime import datetime,timezone
import os,secrets,hmac,hashlib,time,json,asyncio
from fastapi import FastAPI,Request,HTTPException,Depends,Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,ConfigDict
from pai.config import ROOT,PaiError,project,symbols
from pai.data import MexcPublic
from pai.features import indicators
from .store import Store
from .models import Registry
from .llm import OllamaLocal
from .engine import Engine
from .lab import laboratory_router, live_candles

@dataclass
class Settings:
    api_key:str
    gateway_key:str
    session_key:str
    root:Path=ROOT
    ollama_url:str='http://127.0.0.1:11434'
    ollama_model:str='qwen3:1.7b'

def settings_from_env():
    path=ROOT/'.env'
    if path.is_file():
        allowed={'PAI_API_KEY','PAI_GATEWAY_KEY','PAI_SESSION_KEY','OLLAMA_URL','OLLAMA_MODEL'}
        for line in path.read_text().splitlines():
            key,sep,value=line.partition('=')
            if sep and key.strip() in allowed:os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
    vals=[os.environ.get(k,'') for k in ['PAI_API_KEY','PAI_GATEWAY_KEY','PAI_SESSION_KEY']]
    if any(len(k)<32 for k in vals):raise RuntimeError('Faltan secretos privados. Ejecuta python scripts/configurar.py; no uses .env.example como claves.')
    return Settings(*vals,ollama_url=os.environ.get('OLLAMA_URL','http://127.0.0.1:11434'),ollama_model=os.environ.get('OLLAMA_MODEL','qwen3:1.7b'))

class Login(BaseModel):
    api_key:str=Field(min_length=1,max_length=256)
class Start(BaseModel):
    symbols:list[str]=Field(min_length=1,max_length=15)
class ReplayStart(BaseModel):
    symbol:str
    cycles:int=Field(default=30,ge=20,le=365)
class GatewayBody(BaseModel):
    snapshot:dict
    portfolio:dict

def create_app(settings=None,store=None,registry=None,market=None,llm=None):
    settings=settings or settings_from_env()
    store=store or Store(settings.root/'var/paper.sqlite',str(project()['paper']['initial_cash']))
    registry=registry or Registry(settings.root);market=market or MexcPublic()
    llm=llm or OllamaLocal(settings.ollama_url,settings.ollama_model)
    engine=Engine(store,registry,llm,market,settings.root);attempts={};jobs={}
    @asynccontextmanager
    async def lifespan(app):
        engine.start_scheduler()
        yield
        if engine.task:
            engine.task.cancel()
            try:await engine.task
            except asyncio.CancelledError:pass
    app=FastAPI(title='PAI Finanzas · Solo Paper',version='1.0.0',lifespan=lifespan)
    app.state.store=store;app.state.engine=engine

    def sign(value):return hmac.new(settings.session_key.encode(),value.encode(),hashlib.sha256).hexdigest()
    def authorized(request:Request):
        key=request.headers.get('x-api-key')
        if key is not None:
            if secrets.compare_digest(key,settings.api_key):return True
        else:
            cookie=request.cookies.get('pai_session','');value,sep,signature=cookie.rpartition('.')
            if sep and secrets.compare_digest(sign(value),signature):
                try:valid=0<=time.time()-int(value.split(':')[0])<=28800
                except ValueError:valid=False
                if valid:
                    if request.method not in ('GET','HEAD'):
                        origin=request.headers.get('origin')
                        if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                            # Vite solo durante desarrollo local; no hay CORS público.
                            if origin not in ('http://127.0.0.1:5173','http://localhost:5173'):raise HTTPException(403,'Origen no permitido.')
                        if request.headers.get('x-requested-with')!='PAI':raise HTTPException(403,'Falta la protección de solicitud de la UI.')
                    return True
        store.event('auth','AUTH_DENIED','Acceso rechazado: clave ausente o incorrecta.')
        raise HTTPException(401,'Acceso privado: falta una clave válida.')
    access=[Depends(authorized)]
    app.include_router(laboratory_router(settings.root, registry, market, access, llm))

    @app.exception_handler(PaiError)
    async def handled(request,exc):return JSONResponse(status_code=412,content={'detail':str(exc)})

    @app.get('/api/health')
    def health():return {'service':'PAI','mode':'paper','real_orders_enabled':False,'version':'1.0.0'}

    @app.post('/api/login')
    def login(body:Login,request:Request,response:Response):
        ip=request.client.host if request.client else 'local';now=time.time()
        attempts[ip]=[v for v in attempts.get(ip,[]) if now-v<60]
        if len(attempts[ip])>=6:raise HTTPException(429,'Espera un minuto antes de volver a intentar.')
        attempts[ip].append(now)
        if not secrets.compare_digest(body.api_key,settings.api_key):
            store.event('auth','AUTH_DENIED','Clave de acceso incorrecta.');raise HTTPException(401,'Clave incorrecta.')
        value=f'{int(now)}:{secrets.token_hex(16)}'
        response.set_cookie('pai_session',value+'.'+sign(value),httponly=True,samesite='strict',max_age=28800,
                            secure=request.url.scheme=='https')
        return {'ok':True}

    @app.post('/api/logout',dependencies=access)
    def logout(response:Response):response.delete_cookie('pai_session');return {'ok':True}

    @app.get('/api/config',dependencies=access)
    def config():return {'assets':project()['assets'],'risk':project()['paper'],'interval':'1d',
                        'ollama_model':settings.ollama_model,'stop_liquidates':False}

    @app.get('/api/state',dependencies=access)
    def state():
        with store.lock:
            return {'account':store.account(),'active_symbols':json.loads(store.get('active_symbols') or '[]'),
                    'daily_equity':float(store.get('daily_equity') or 0),'daily_day':store.get('daily_day'),
                    'decisions':store.rows('SELECT * FROM decisions ORDER BY id DESC LIMIT 80'),
                    'orders':store.rows('SELECT * FROM orders ORDER BY id DESC LIMIT 80'),
                    'equity':store.rows('SELECT * FROM equity ORDER BY id DESC LIMIT 400')[::-1],
                    'events':store.rows('SELECT * FROM events ORDER BY id DESC LIMIT 60')}

    @app.get('/api/lab/activity', dependencies=access)
    def activity():
        return {"events": engine.activity}

    @app.get('/api/assets',dependencies=access)
    def assets():
        rows=[]
        for a in project()['assets']:
            try:
                m=registry.contract(a['symbol']);status='ready';message='Modelo versionado y evidencia T4 disponible.'
                selected=m['selected_experiment']
            except PaiError as exc:status='pending';message=str(exc);selected=None
            rows.append({**a,'status':status,'message':message,'model':selected})
        return rows

    @app.get('/api/market/{symbol}',dependencies=access)
    def market_data(symbol:str):
        if symbol not in symbols():raise HTTPException(404,'Activo fuera del catálogo.')
        try:
            now=market.server_time();f=live_candles(market,symbol,now,120)
            f=indicators(f);last=f.iloc[-1]
            try:forecast=registry.forecast(symbol,f);message=None
            except PaiError as exc:forecast=None;message=str(exc)
            return {'symbol':symbol,'source':'MEXC Spot','mode':'live','close':float(last.close),
                    'change':float(last['return']),'date':str(last.date),'close_ms':int(last.close_time),
                    'sma20':float(last.sma20),'vol20':float(last.vol20),'dist_sma20':float(last.dist_sma20),
                    'forecast':forecast,'model_message':message,
                    'chart':[{'date':str(r.date),'price':float(r.close)} for r in f.tail(90).itertuples()]}
        except PaiError as exc:
            store.event('market','MARKET_UNAVAILABLE',str(exc),symbol);raise HTTPException(503,str(exc)) from exc

    @app.post('/api/control/start',dependencies=access)
    def start(body:Start):
        if len(set(body.symbols))!=len(body.symbols) or any(s not in symbols() for s in body.symbols):raise HTTPException(400,'Selección de activos no válida.')
        for symbol in body.symbols:registry.contract(symbol)
        llm.health();market.server_time()
        with store.transaction() as c:store.set('active_symbols',json.dumps(body.symbols),c)
        store.status('running');return {'status':'running','symbols':body.symbols,'frequency':'una decisión por vela diaria cerrada'}

    @app.post('/api/control/pause',dependencies=access)
    def pause():return {'status':store.status('paused')}

    @app.post('/api/control/stop',dependencies=access)
    def stop():return {'status':store.status('stopped'),'positions_kept':True,'message':'Se bloquearon nuevas órdenes. Las posiciones se conservan.'}

    @app.post('/api/cycle/{symbol}',dependencies=access)
    async def once(symbol:str):return await engine.once(symbol)

    @app.post('/api/llm/propose')
    def private_gateway(body:GatewayBody,request:Request):
        key=request.headers.get('x-llm-key','')
        if not secrets.compare_digest(key,settings.gateway_key):
            store.event('gateway','AUTH_DENIED','Gateway LLM rechazó una clave ausente o incorrecta.')
            raise HTTPException(401,'Gateway privado: clave incorrecta.')
        if body.snapshot.get('symbol') not in symbols():raise HTTPException(400,'Símbolo no permitido.')
        p,latency,tools=llm.propose(body.snapshot,body.portfolio)
        return {'proposal':p,'latency_ms':latency,'tools':tools}

    @app.get('/api/evidence',dependencies=access)
    def evidence():
        rows=[]
        for name,label in [('t4.json','Entrenamiento T4'),('ollama_local.json','Inferencia Ollama local'),
                           ('replay_resumen.json','20 ciclos y comparación'),('pruebas.json','Pruebas automatizadas')]:
            p=settings.root/'evidencia'/name
            rows.append({'name':label,'available':p.is_file(),'file':name})
        return rows

    @app.post('/api/replay/start',dependencies=access)
    async def replay_start(body:ReplayStart):
        registry.contract(body.symbol);llm.health()
        if any(j['status']=='running' for j in jobs.values()):raise HTTPException(409,'Ya hay una repetición histórica en curso.')
        from .replay import run_replay
        ident=secrets.token_hex(6);jobs[ident]={'id':ident,'status':'running','mode':'replay','symbol':body.symbol}
        async def run():
            try:
                result=await asyncio.to_thread(run_replay,settings.root,body.symbol,body.cycles,registry,llm)
                jobs[ident].update(status='completed',result=result)
            except (PaiError,ValueError,OSError) as exc:
                jobs[ident].update(status='failed',error=str(exc));store.event('replay','FAILED',str(exc),body.symbol)
        asyncio.create_task(run());return jobs[ident]

    @app.get('/api/replay/jobs',dependencies=access)
    def replay_jobs():return list(jobs.values())

    @app.get('/api/llm/health',dependencies=access)
    def llm_health():return llm.health()

    @app.post('/api/liquidate/{symbol}',dependencies=access)
    def liquidate(symbol:str):
        if symbol not in symbols():raise HTTPException(404,'Símbolo no permitido.')
        return engine.paper.liquidate(symbol,market.book(symbol),market.info(symbol))

    @app.get('/api/export/{table}',dependencies=access)
    def export(table:str):
        import csv,io
        if table not in ('decisions','orders','equity','events'):raise HTTPException(404,'Tabla no exportable.')
        records=store.rows('SELECT * FROM '+table+' ORDER BY id')
        output=io.StringIO()
        if records:
            writer=csv.DictWriter(output,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
        return Response(content=output.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{table}_paper.csv"'})

    dist=settings.root/'frontend/dist'
    if dist.is_dir():app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app
