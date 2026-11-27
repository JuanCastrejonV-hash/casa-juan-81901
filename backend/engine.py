import asyncio,time
from pathlib import Path
from pai.config import PaiError,project,save_json
from pai.data import MexcPublic,rows_frame,audit
from .paper import Paper

class Engine:
    def __init__(self,store,registry,llm,market=None,root=None):
        self.store=store;self.registry=registry;self.llm=llm;self.market=market or MexcPublic()
        self.risk=project()['paper'];self.paper=Paper(store,self.risk);self.root=root
        self.cycle_lock=asyncio.Lock();self.task=None
        self.activity = ()

    def record_stage(self, symbol, stage, detail=None):
        index = self.activity[-1]["index"] + 1 if self.activity else 1
        event = {"index": index, "symbol": symbol, "stage": stage,
                 "at_ms": time.time_ns() // 1_000_000, "detail": detail}
        self.activity = (*self.activity[-35:], event)

    def _cycle(self,symbol):
        # Todas las dependencias se validan antes de cualquier orden simulada.
        self.record_stage(symbol, "market")
        self.registry.contract(symbol)
        now=self.market.server_time();info=self.market.info(symbol)
        frame,_=audit(rows_frame(self.market.candles(symbol,120)),now,min_rows=60)
        close_ms=int(frame.close_time.iloc[-1])
        if now-close_ms>self.risk['max_data_age_hours']*3600000:raise PaiError('Dato atrasado: la vela cerrada más reciente excede el límite.')
        old=self.store.rows('SELECT id FROM decisions WHERE symbol=? AND close_ms=?',(symbol,close_ms))
        if old:
            self.record_stage(symbol, "idle", "Vela ya registrada.")
            return {'duplicate':True,'executed':False,'risk':'DUPLICATE'}
        self.record_stage(symbol, "model")
        snapshot=self.registry.forecast(symbol,frame)
        self.record_stage(symbol, "ollama")
        proposal,latency,tools=self.llm.propose(snapshot,self.store.account())
        # El libro se consulta después de la inferencia: no se adjudica un precio pasado.
        self.record_stage(symbol, "risk")
        book=self.market.book(symbol)
        result=self.paper.apply(snapshot,proposal,book,info,latency,'live',tools)
        self.record_stage(symbol, "ledger", result["risk"])
        if self.root and getattr(self.llm,'evidence',None):save_json(Path(self.root)/'evidencia/ollama_local.json',self.llm.evidence)
        self.record_stage(symbol, "idle")
        return result

    async def once(self,symbol):
        async with self.cycle_lock:
            if self.store.status()!='running':raise PaiError('Agente pausado o detenido; iniciar para procesar velas.')
            try:return await asyncio.to_thread(self._cycle,symbol)
            except (PaiError,ValueError,OSError) as exc:
                self.record_stage(symbol, "error", str(exc))
                self.store.event('cycle','DEPENDENCY_ERROR',str(exc),symbol);self.store.status('paused')
                raise PaiError(str(exc)) from exc

    async def loop(self):
        while True:
            for pos in self.store.account()['positions']:
                if pos['qty']<=0:continue
                try:
                    book=await asyncio.to_thread(self.market.book,pos['symbol'])
                    self.paper.mark(pos['symbol'],book['bid'],book['observed_at_ms'])
                except (PaiError,ValueError,OSError) as exc:
                    self.store.event('risk','MARK_UNAVAILABLE',str(exc),pos['symbol'])
                    if self.store.status()=='running':self.store.status('paused')
            if self.store.status()=='running':
                selected=self.store.get('active_symbols') or '[]'
                import json
                for symbol in json.loads(selected):
                    if self.store.status()!='running':break
                    try:await self.once(symbol)
                    except PaiError:break
            await asyncio.sleep(self.risk['poll_seconds'])

    def start_scheduler(self):
        if not self.task or self.task.done():self.task=asyncio.create_task(self.loop())
