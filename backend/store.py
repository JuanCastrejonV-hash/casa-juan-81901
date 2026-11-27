import sqlite3,json,threading
from contextlib import contextmanager
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS positions(symbol TEXT PRIMARY KEY,qty TEXT NOT NULL,cost_basis TEXT NOT NULL,
                                     mark TEXT NOT NULL,mark_ms INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS candles(symbol TEXT NOT NULL,close_ms INTEGER NOT NULL,payload TEXT NOT NULL,
                                   PRIMARY KEY(symbol,close_ms));
CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY,symbol TEXT NOT NULL,close_ms INTEGER NOT NULL,
 action TEXT NOT NULL,reason TEXT NOT NULL,forecast REAL NOT NULL,risk TEXT NOT NULL,
 executed INTEGER NOT NULL,llm_ms REAL NOT NULL,mode TEXT NOT NULL,tools_json TEXT NOT NULL,
 UNIQUE(symbol,close_ms));
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,decision_id INTEGER REFERENCES decisions(id),
 symbol TEXT NOT NULL,side TEXT NOT NULL,qty TEXT NOT NULL,price TEXT NOT NULL,fee TEXT NOT NULL,
 fill_ms INTEGER NOT NULL,pnl TEXT,forced INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS equity(id INTEGER PRIMARY KEY,event_ms INTEGER NOT NULL,equity REAL NOT NULL,
 cash REAL NOT NULL,exposure REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,stage TEXT NOT NULL,
 code TEXT NOT NULL,message TEXT NOT NULL,symbol TEXT);
CREATE INDEX IF NOT EXISTS idx_events_code ON events(code);
'''

class Store:
    def __init__(self,path,initial='50000'):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True) if str(path)!=':memory:' else None
        self.lock=threading.RLock();self.db=sqlite3.connect(path,check_same_thread=False,isolation_level=None)
        self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL');self.db.executescript(SCHEMA)
        with self.transaction() as c:
            if self.get('cash',c) is None:
                for k,v in {'cash':str(initial),'initial':str(initial),'status':'stopped',
                            'daily_day':'','daily_equity':str(initial)}.items():self.set(k,v,c)
            elif self.get('status',c)=='running':
                self.set('status','paused',c)
                self.event('restart','RECOVERED','Estado recuperado. El agente quedó pausado; no se repiten operaciones.',conn=c)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield self.db
                self.db.execute('COMMIT')
            except BaseException:
                self.db.execute('ROLLBACK');raise

    def get(self,key,conn=None):
        with self.lock:r=(conn or self.db).execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
        return r[0] if r else None

    def set(self,key,value,conn=None):
        (conn or self.db).execute('INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))

    def event(self,stage,code,message,symbol=None,conn=None):
        (conn or self.db).execute('INSERT INTO events(created_at,stage,code,message,symbol) VALUES(?,?,?,?,?)',
                  (datetime.now(timezone.utc).isoformat(),stage,code,str(message)[:600],symbol))

    def status(self,value=None):
        if value is not None:
            with self.transaction() as c:
                self.set('status',value,c);self.event('control',value.upper(),'Control humano: '+value,conn=c)
        return self.get('status')

    def rows(self,sql,args=()):
        with self.lock:return [dict(r) for r in self.db.execute(sql,args)]

    def account(self,conn=None):
        c=conn or self.db;cash=Decimal(self.get('cash',c));positions=[];exposure=Decimal('0')
        for r in c.execute('SELECT * FROM positions ORDER BY symbol'):
            q=Decimal(r['qty']);mark=Decimal(r['mark']);value=q*mark;exposure+=value
            positions.append({'symbol':r['symbol'],'qty':float(q),'price':float(mark),'value':float(value),
                              'cost_basis':float(Decimal(r['cost_basis'])),'mark_ms':r['mark_ms']})
        return {'cash':float(cash),'equity':float(cash+exposure),'exposure':float(exposure),
                'initial':float(self.get('initial',c)),'positions':positions,'status':self.get('status',c)}

    def close(self):self.db.close()
