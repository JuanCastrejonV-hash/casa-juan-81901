from decimal import Decimal,ROUND_DOWN
from datetime import datetime,timezone
import json,math
from pai.config import PaiError,finite

def D(x):return Decimal(str(x))

def pair_rules(info):
    try:
        precision=int(info['baseAssetPrecision']);qp=int(info.get('quotePrecision',info.get('quoteAssetPrecision')))
        minimum=D(info.get('quoteAmountPrecisionMarket') or info['quoteAmountPrecision'])
        min_qty=D(info['baseSizePrecision'])
    except (KeyError,ValueError,TypeError) as exc:raise PaiError('Reglas de tamaño o precisión incompletas en exchangeInfo.') from exc
    if not 0<=precision<=18 or not 0<=qp<=18 or minimum<=0 or min_qty<=0:raise PaiError('Reglas de precisión no válidas.')
    return {'step':D(10)**(-precision),'price_step':D(10)**(-qp),'min_quote':minimum,'min_qty':min_qty,
            'max_quote':D(info.get('maxQuoteAmountMarket') or info.get('maxQuoteAmount') or '1e30')}

class Paper:
    def __init__(self,store,risk):self.store=store;self.risk=risk

    def apply(self,snapshot,proposal,book,info,llm_ms=0,mode='live',tools=None,force=False):
        symbol=snapshot['symbol'];close_ms=int(snapshot['close_ms']);rules=pair_rules(info)
        action=proposal['action'];reason=proposal['reason'];now=int(book['observed_at_ms'])
        if proposal['symbol']!=symbol or int(proposal['candle_close_ms'])!=close_ms:raise PaiError('Propuesta de otro símbolo o vela.')
        if action not in ('BUY','HOLD','SELL'):raise PaiError('Acción no permitida.')
        for key in ['forecast','close','vol20','dist_sma20']:finite(snapshot[key],key)
        bid,ask=finite(book['bid'],'bid'),finite(book['ask'],'ask')
        if not 0<bid<=ask:raise PaiError('Libro de ejecución no válido.')
        if close_ms>now or now-close_ms>self.risk['max_data_age_hours']*3600000:
            raise PaiError('Dato atrasado o vela abierta; nuevas decisiones pausadas.')
        with self.store.transaction() as c:
            if c.execute('SELECT 1 FROM decisions WHERE symbol=? AND close_ms=?',(symbol,close_ms)).fetchone():
                self.store.event('cycle','DUPLICATE','Vela ya procesada: se conserva el estado.',symbol,c)
                return {'duplicate':True,'executed':False,'risk':'DUPLICATE'}
            position=c.execute('SELECT * FROM positions WHERE symbol=?',(symbol,)).fetchone()
            qty=D(position['qty']) if position else D(0)
            basis=D(position['cost_basis']) if position else D(0)
            c.execute('INSERT INTO positions VALUES(?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET mark=CASE WHEN positions.mark_ms<=excluded.mark_ms THEN excluded.mark ELSE positions.mark END,mark_ms=MAX(positions.mark_ms,excluded.mark_ms)',
                      (symbol,str(qty),str(basis),str(snapshot['close']),close_ms))
            account=self.store.account(c);equity=D(account['equity']);cash=D(self.store.get('cash',c))
            day=datetime.fromtimestamp(now/1000,timezone.utc).date().isoformat()
            if self.store.get('daily_day',c)!=day:
                self.store.set('daily_day',day,c);self.store.set('daily_equity',equity,c)
            start=D(self.store.get('daily_equity',c));daily_loss=(start-equity)/start if start>0 else D(1)
            code='OK';executed=False;newqty=qty;newbasis=basis;pnl=None
            if self.store.get('status',c)!='running' and not force:code='STOPPED'
            elif action=='BUY' and cash<=0:code='INSUFFICIENT_BALANCE'
            elif daily_loss>=D(self.risk['daily_loss_limit']) and not force:
                code='DAILY_LOSS';self.store.set('status','paused',c)
            elif any(p['qty']>0 and now-p['mark_ms']>self.risk['max_data_age_hours']*3600000 for p in account['positions']):code='STALE_POSITION'
            elif action=='BUY' and mode!='replay_passive' and (snapshot['forecast']<=snapshot['threshold'] or (snapshot.get('technical_filter',False) and snapshot['dist_sma20']<=0)):code='MODEL_SIGNAL'
            elif action=='SELL' and qty<=0:code='NO_POSITION'
            slip=D(self.risk['slippage_bps'])/10000;fee_rate=D(self.risk['fee']);order=None
            if code=='OK' and action=='BUY':
                if qty>0:code='ALREADY_LONG'
                else:
                    price=(D(book['ask'])*(1+slip)).quantize(rules['price_step'],rounding=ROUND_DOWN)
                    # Redondear al alza el precio de compra no mejora artificialmente el fill.
                    if price<D(book['ask'])*(1+slip):price+=rules['price_step']
                    target=equity*D(self.risk['max_asset_exposure'])
                    allocation=min(target,cash/(1+fee_rate))
                    quantity=(allocation/price).quantize(rules['step'],rounding=ROUND_DOWN)
                    notional=quantity*price;fee=notional*fee_rate
                    projected=D(account['exposure'])+notional
                    if cash<=0 or quantity<=0:code='INSUFFICIENT_BALANCE'
                    elif quantity<rules['min_qty'] or notional<rules['min_quote']:code='MIN_ORDER'
                    elif notional>rules['max_quote']:code='MAX_ORDER'
                    elif projected>equity*D(self.risk['max_total_exposure']):code='EXPOSURE_LIMIT'
                    elif notional+fee>cash:code='INSUFFICIENT_BALANCE'
                    else:
                        cash-=notional+fee;newqty=quantity;newbasis=notional+fee
                        order=(quantity,price,fee,None);executed=True
            elif code=='OK' and action=='SELL':
                price=(D(book['bid'])*(1-slip)).quantize(rules['price_step'],rounding=ROUND_DOWN)
                notional=qty*price;fee=notional*fee_rate
                if qty<rules['min_qty'] or notional<rules['min_quote']:code='MIN_ORDER'
                else:
                    cash+=notional-fee;pnl=notional-fee-basis;newqty=D(0);newbasis=D(0)
                    order=(qty,price,fee,pnl);executed=True
            if cash<0 or newqty<0:raise PaiError('Invariante del simulador: saldo o posición negativa.')
            c.execute('INSERT OR IGNORE INTO candles VALUES(?,?,?)',(symbol,close_ms,json.dumps(snapshot,allow_nan=False)))
            cur=c.execute('INSERT INTO decisions(symbol,close_ms,action,reason,forecast,risk,executed,llm_ms,mode,tools_json) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (symbol,close_ms,action,reason,float(snapshot['forecast']),code,int(executed),llm_ms,mode,json.dumps(tools or [])))
            if order:
                q,p,f,pn=order
                c.execute('INSERT INTO orders(decision_id,symbol,side,qty,price,fee,fill_ms,pnl,forced) VALUES(?,?,?,?,?,?,?,?,?)',
                          (cur.lastrowid,symbol,action,str(q),str(p),str(f),now,str(pn) if pn is not None else None,int(force)))
                c.execute('UPDATE positions SET qty=?,cost_basis=?,mark=?,mark_ms=? WHERE symbol=?',
                          (str(newqty),str(newbasis),str(p),now,symbol))
                self.store.set('cash',cash,c)
            if code!='OK':self.store.event('risk',code,'Propuesta registrada sin ejecución: '+code,symbol,c)
            after=self.store.account(c)
            c.execute('INSERT INTO equity(event_ms,equity,cash,exposure) VALUES(?,?,?,?)',
                      (now,after['equity'],after['cash'],after['exposure']))
            return {'decision_id':cur.lastrowid,'duplicate':False,'executed':executed,'risk':code,'account':after}

    def mark(self,symbol,price,event_ms):
        price=finite(price,'valoración');event_ms=int(event_ms)
        if price<=0:raise PaiError('Precio de valoración no positivo.')
        with self.store.transaction() as c:
            before=self.store.account(c);day=datetime.fromtimestamp(event_ms/1000,timezone.utc).date().isoformat()
            if self.store.get('daily_day',c)!=day:
                self.store.set('daily_day',day,c);self.store.set('daily_equity',before['equity'],c)
            c.execute('UPDATE positions SET mark=?,mark_ms=? WHERE symbol=? AND mark_ms<=?',
                      (str(price),event_ms,symbol,event_ms))
            account=self.store.account(c);start=D(self.store.get('daily_equity',c))
            loss=(start-D(account['equity']))/start if start>0 else D(1)
            if loss>=D(self.risk['daily_loss_limit']) and self.store.get('status',c)=='running':
                self.store.set('status','paused',c);self.store.event('risk','DAILY_LOSS','Límite diario alcanzado; nuevas órdenes bloqueadas.',symbol,c)
            c.execute('INSERT INTO equity(event_ms,equity,cash,exposure) VALUES(?,?,?,?)',
                      (event_ms,account['equity'],account['cash'],account['exposure']))
            return account

    def liquidate(self,symbol,book,info):
        """Acción explícita, separada de detener. También sirve para el cierre del replay."""
        rules=pair_rules(info);bid=finite(book['bid'],'bid')
        if bid<=0:raise PaiError('Cotización de liquidación no válida.')
        with self.store.transaction() as c:
            row=c.execute('SELECT * FROM positions WHERE symbol=?',(symbol,)).fetchone()
            if row is None or D(row['qty'])<=0:raise PaiError('No hay posición que liquidar.')
            qty=D(row['qty']);price=(D(bid)*(1-D(self.risk['slippage_bps'])/10000)).quantize(rules['price_step'],rounding=ROUND_DOWN)
            gross=qty*price;fee=gross*D(self.risk['fee'])
            if qty<rules['min_qty'] or gross<rules['min_quote']:raise PaiError('La posición no cumple el mínimo de liquidación; se mantiene visible como remanente.')
            cash=D(self.store.get('cash',c))+gross-fee;pnl=gross-fee-D(row['cost_basis'])
            self.store.set('cash',cash,c)
            c.execute('UPDATE positions SET qty="0",cost_basis="0",mark=?,mark_ms=? WHERE symbol=?',
                      (str(price),book['observed_at_ms'],symbol))
            c.execute('INSERT INTO orders(decision_id,symbol,side,qty,price,fee,fill_ms,pnl,forced) VALUES(NULL,?,?,?,?,?,?,?,1)',
                      (symbol,'SELL',str(qty),str(price),str(fee),book['observed_at_ms'],str(pnl)))
            self.store.event('control','EXPLICIT_LIQUIDATION','Liquidación Paper solicitada explícitamente; no se deriva del botón detener.',symbol,c)
            account=self.store.account(c)
            c.execute('INSERT INTO equity(event_ms,equity,cash,exposure) VALUES(?,?,?,?)',
                      (book['observed_at_ms'],account['equity'],account['cash'],account['exposure']))
            return account
