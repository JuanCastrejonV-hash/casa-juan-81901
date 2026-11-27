import { useState } from 'react';
import type { ReactNode } from 'react';
import { Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3, CircleHelp, Clock3,
  Database, Filter, Search, Wallet, Waves } from 'lucide-react';
import { MarketChart, Sparkline } from './chart';
import { actionName, date, dateTime, moveClass, number, pct, price, replayPeriod,
  riskName, statusName, strategies } from './data';
import type { Asset, Catalog, Decision, LiveScan, Market, Mode, Replay, SectionChange,
  State, Trade, TradingRecords, View } from './data';

export function Heading({ title, context, action }: { title: string; context?: string; action?: ReactNode }) {
  return <header className="view-heading"><div><h1>{title}</h1>{context && <p>{context}</p>}</div>{action}</header>;
}

export function Panel({ title, detail, action, children, className = '' }: {
  title: string; detail?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return <section className={`panel ${className}`}>
    <header className="panel-heading"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div>{action}</header>
    {children}
  </section>;
}

export function Empty({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return <div className="empty"><span className="empty-mark"><Database size={20} /></span><strong>{title}</strong>
    {detail && <p>{detail}</p>}{action}</div>;
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'good' | 'warning' | 'danger' }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Metric({ label, value, detail, icon, variant = '' }: {
  label: string; value: ReactNode; detail: ReactNode; icon?: ReactNode; variant?: string;
}) {
  return <div className={`metric ${variant}`}><div className="metric-label">{label}{icon && <span>{icon}</span>}</div>
    <strong>{value}</strong><div className="metric-detail">{detail}</div></div>;
}

export function Coin({ asset }: { asset: Asset }) {
  return <span className="coin" aria-hidden="true" data-base={asset.base}>
    {asset.base === 'BTC' ? '₿' : asset.base === 'ETH' ? 'Ξ' : asset.base.slice(0, 2)}
  </span>;
}

export function ValueRows({ rows }: { rows: [string, ReactNode][] }) {
  return <dl className="value-rows">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>;
}

export function PricePanel({ asset, market, loading, error, orders, refresh }: {
  asset: Asset; market: Market | null; loading: boolean; error: string; orders: Trade[]; refresh: () => void;
}) {
  return <Panel title={`Precio de ${asset.name}`} className="price-panel"
    detail={market ? `${asset.symbol} · ${market.source === 'live' ? 'MEXC Spot' : 'Histórico auditado'} · Velas diarias` : asset.symbol}>
    {loading && <p className="inline-status">Consultando velas de {asset.symbol}…</p>}
    {error && <div className="inline-error" role="status"><CircleHelp size={17} /><span>{error}</span>
      <button className="text-action" onClick={refresh}>Reintentar</button></div>}
    {market ? <>
      <div className="quote-line"><strong>{price(market.close)}</strong><span>USDT</span>
        <span className={`move-tag ${moveClass(market.change)}`}>{market.change < 0 ? <ArrowDownRight size={13} /> : <ArrowUpRight size={13} />}{pct(market.change)}<small>1D</small></span>
      </div>
      <MarketChart key={`${market.symbol}-${market.source}`} market={market} orders={orders} />
    </> : <Empty title={loading ? 'Cargando el gráfico' : 'Velas sin cargar'} detail={loading ? undefined :
      'Consulta la fuente del mercado o selecciona un activo con histórico disponible.'} />}
  </Panel>;
}

export function ForecastPanel({ market, decision, asset }: { market: Market | null; decision?: Decision; asset: Asset }) {
  const forecast = market?.forecast;
  return <Panel title="Señal del modelo" detail={asset.model?.experiment.replaceAll('_', ' ') ?? asset.symbol} className="forecast-panel">
    <div className="signal-main">
      <span>{forecast ? `Objetivo ${date(forecast.target_ms)} UTC` : 'Rendimiento a un día'}</span>
      <strong>{forecast ? pct(forecast.value, 3) : '—'}</strong>
      {forecast && <Badge tone={forecast.signal ? 'good' : 'neutral'}>{forecast.signal ? 'Comprar' : 'Efectivo'}</Badge>}
    </div>
    <ValueRows rows={[
      ['Umbral de compra', forecast ? pct(forecast.threshold, 3, false) : '—'],
      ['Filtro de tendencia', forecast ? forecast.technical_filter ? 'Cierre sobre SMA 20' : 'Desactivado' : '—'],
      ['Distancia a SMA 20', market ? pct(market.dist_sma20) : '—'],
    ]} />
    {market?.model_message && <p className="inline-status">{market.model_message}</p>}
    <div className="decision-note"><span>Última decisión registrada</span>
      <strong>{decision ? actionName(decision.action) : 'Sin registro'}</strong>
      {decision && <><p>{decision.reason}</p><Badge tone={decision.executed ? 'good' : decision.risk !== 'OK' ? 'warning' : 'neutral'}>
        {decision.executed ? 'Ejecutada' : decision.risk === 'OK' ? 'Sin operación' : riskName(decision.risk)}
      </Badge></>}
    </div>
  </Panel>;
}

export function Overview({ catalog, asset, market, replay, records, mode, live, loading, error, refresh, navigate, pick }: {
  catalog: Catalog; asset: Asset; market: Market | null; replay: Replay | null; records: TradingRecords;
  mode: Mode; live: State | null; loading: boolean; error: string; refresh: () => void;
  navigate: SectionChange; pick: (symbol: string, view?: View) => void;
}) {
  const saved = replay?.comparison.find(row => row.estrategia === 'agente_con_llm');
  const final = mode === 'historical' ? saved?.patrimonio_final : live?.account.equity;
  const net = mode === 'historical' ? saved?.rendimiento_neto :
    live ? live.account.equity / live.account.initial - 1 : undefined;
  const ready = catalog.assets.filter(a => a.status === 'ready').length;
  const recent = [...records.decisions].filter(row => row.symbol === asset.symbol).sort((a, b) => b.close_ms - a.close_ms);
  const context = mode === 'historical' ? replay ? `${asset.symbol} · ${replayPeriod(replay)}` :
    `${asset.symbol} · Histórico auditado de MEXC Spot` : 'Cartera Paper compartida · Mercado MEXC Spot';
  return <>
    <Heading title="Vista general" context={context}
      action={<button className="button" onClick={() => navigate(mode === 'historical' ? 'comparison' : 'operations')}>
        {mode === 'historical' ? 'Comparar estrategias' : 'Ver operaciones'} <ArrowRight size={15} />
      </button>} />
    <div className="metric-grid">
      <Metric label={mode === 'historical' ? 'Patrimonio · Con Ollama' : 'Patrimonio Paper'} variant="featured" icon={<Wallet size={17} />}
        value={final == null ? '—' : number(final)} detail={final == null ? 'Replay pendiente' : <>USDT <b className={moveClass(net ?? 0)}>{net == null ? '' : pct(net)}</b></>} />
      <Metric label={mode === 'historical' ? 'Caída máxima' : 'Exposición de la cartera'} icon={<Activity size={17} />}
        value={mode === 'historical' ? saved ? pct(saved.max_drawdown, 2, false) : '—' :
          live ? pct(live.account.exposure / (live.account.equity || 1), 1, false) : '—'}
        detail={mode === 'historical' ? 'Drawdown del periodo' : 'Posiciones / patrimonio'} />
      <Metric label={mode === 'historical' ? 'Ciclos guardados' : 'Estado del agente'} icon={<Clock3 size={17} />}
        value={mode === 'historical' ? replay?.cycles ?? '—' : live ? statusName(live.account.status) : '—'}
        detail={mode === 'historical' ? saved ? `${saved.acciones_rechazadas} propuestas rechazadas` : 'Disponible tras ejecutar un replay' :
          `${live?.active_symbols.length ?? 0} activos configurados`} />
      <Metric label="Modelos con T4" icon={<Waves size={17} />} value={`${ready} / ${catalog.assets.length}`} detail="Catálogo del proyecto" />
    </div>
    <div className="content-grid">
      <PricePanel asset={asset} market={market} orders={records.orders} loading={loading} error={error} refresh={refresh} />
      <ForecastPanel asset={asset} market={market} decision={recent[0]} />
    </div>
    <Panel title="Activos de seguimiento" detail={mode === 'historical' ? 'Último cierre archivado por activo' : 'Modelos disponibles para la sesión Paper'}
      action={<button className="text-action" onClick={() => navigate('scanner')}>Abrir escáner <ArrowRight size={15} /></button>}>
      <div className="table-frame"><table><thead><tr><th>Activo</th><th>Modelo</th><th>Estado</th>
        {mode === 'historical' && <><th>Último cierre</th><th>Variación 1D</th><th>Ciclos</th></>}</tr></thead>
        <tbody>{catalog.assets.slice(0, 5).map(item => <tr key={item.symbol} className={asset.symbol === item.symbol ? 'selected-row' : ''}>
          <td><button className="asset-link" onClick={() => pick(item.symbol, 'market')}><Coin asset={item} /><span><b>{item.symbol}</b><small>{item.name}</small></span></button></td>
          <td>{item.model?.experiment.replaceAll('_', ' ') ?? '—'}</td>
          <td><Badge tone={item.status === 'ready' ? 'good' : 'warning'}>{item.status === 'ready' ? 'Verificado' : 'Pendiente'}</Badge></td>
          {mode === 'historical' && <>
            <td className="mono">{item.history ? price(item.history.close) : '—'}</td>
            <td className={`mono ${moveClass(item.history?.change ?? 0)}`}>{item.history ? pct(item.history.change) : '—'}</td>
            <td className="mono">{item.replay_cycles ?? '—'}</td>
          </>}
        </tr>)}</tbody></table></div>
    </Panel>
  </>;
}

export function MarketView({ asset, market, records, loading, error, refresh }: {
  asset: Asset; market: Market | null; records: TradingRecords; loading: boolean; error: string; refresh: () => void;
}) {
  const recent = [...records.decisions].filter(row => row.symbol === asset.symbol).sort((a, b) => b.close_ms - a.close_ms)[0];
  return <>
    <Heading title="Mercado" context={`${asset.name} / Tether · ${asset.symbol}`} />
    <div className="metric-grid">
      <Metric label="Cierre" value={market ? price(market.close) : '—'} detail={market ? `${pct(market.change)} en un día` : 'USDT'} icon={<BarChart3 size={17} />} />
      <Metric label="SMA 20" value={market ? price(market.sma20) : '—'} detail="Promedio de 20 cierres" icon={<Activity size={17} />} />
      <Metric label="Volatilidad 20" value={market ? pct(market.vol20, 2, false) : '—'} detail="Desviación de retornos diarios" icon={<Waves size={17} />} />
      <Metric label="Última vela" value={market ? date(market.close_ms, true) : '—'} detail={market ? dateTime(market.close_ms) : 'Zona horaria UTC'} icon={<Clock3 size={17} />} />
    </div>
    <div className="content-grid">
      <PricePanel asset={asset} market={market} orders={records.orders} loading={loading} error={error} refresh={refresh} />
      <ForecastPanel asset={asset} market={market} decision={recent} />
    </div>
  </>;
}

export function Scanner({ assets, mode, scan, busy, error, refresh, pick }: {
  assets: Asset[]; mode: Mode; scan: LiveScan | null; busy: boolean; error: string;
  refresh: () => void; pick: (symbol: string, view?: View) => void;
}) {
  const [query, setQuery] = useState('');
  const [order, setOrder] = useState('catalog');
  const [trend, setTrend] = useState('all');
  const results = assets.map(asset => {
    const live = scan?.rows.find(row => row.symbol === asset.symbol);
    return { asset, market: mode === 'historical' ? asset.history : live?.market ?? null,
      error: mode === 'historical' ? asset.message : live?.error, latency: live?.latency_ms };
  });
  const valid = results.filter(row => row.market !== null);
  const above = valid.filter(row => row.market!.dist_sma20 > 0).length;
  const term = query.toLocaleLowerCase('es-MX').trim();
  const visible = results
    .filter(row => (row.asset.symbol + row.asset.name).toLocaleLowerCase('es-MX').includes(term))
    .filter(row => trend === 'all' || (row.market && (trend === 'above' ? row.market.dist_sma20 > 0 : row.market.dist_sma20 <= 0)));
  if (order !== 'catalog') visible.sort((a, b) => (b.market?.[order === 'volatility' ? 'vol20' : 'change'] ?? -Infinity)
    - (a.market?.[order === 'volatility' ? 'vol20' : 'change'] ?? -Infinity));
  return <>
    <Heading title="Escáner de activos" context={mode === 'historical' ? 'Velas archivadas del catálogo del proyecto' :
      scan ? `Consulta MEXC · ${dateTime(scan.updated_ms)}` : 'Consulta de mercado en MEXC Spot'}
      action={mode === 'live' && <button className="button primary" onClick={refresh} disabled={busy}>
        <Activity size={16} />{busy ? 'Consultando…' : 'Consultar mercado'}
      </button>} />
    {error && <div className="inline-error" role="status">{error}</div>}
    <div className="metric-grid three">
      <Metric label="En catálogo" value={assets.length} detail="Pares en USDT" icon={<Database size={17} />} />
      <Metric label="Con datos" value={valid.length} detail={mode === 'historical' ? 'Muestras congeladas' : 'Última consulta'} icon={<Activity size={17} />} />
      <Metric label="Sobre SMA 20" value={valid.length ? `${above} / ${valid.length}` : '—'} detail="Cierre superior a la media" icon={<ArrowUpRight size={17} />} />
    </div>
    <Panel title="Cierres diarios" action={<span className="muted compact">{visible.length} activos</span>}>
      <div className="toolbar">
        <label className="search-box"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} aria-label="Buscar activo" placeholder="Buscar por símbolo o nombre" /></label>
        <label className="filter"><Filter size={15} /><select aria-label="Filtrar tendencia" value={trend} onChange={e => setTrend(e.target.value)}>
          <option value="all">Todas las tendencias</option><option value="above">Sobre SMA 20</option><option value="below">En o bajo SMA 20</option>
        </select></label>
        <label className="filter"><span>Orden</span><select aria-label="Orden del escáner" value={order} onChange={e => setOrder(e.target.value)}>
          <option value="catalog">Catálogo</option><option value="change">Mayor variación</option><option value="volatility">Mayor volatilidad</option>
        </select></label>
      </div>
      {visible.length ? <div className="table-frame"><table><thead><tr><th>Activo</th><th>Cierre · USDT</th><th>Var. 1D</th>
        <th>Dist. SMA 20</th><th>Vol. 20</th><th>30 velas</th><th className="nowrap">Vela UTC</th><th>{mode === 'live' ? 'Consulta' : 'Replay'}</th></tr></thead>
        <tbody>{visible.map(({ asset, market, error: itemError, latency }) => <tr key={asset.symbol}>
          <td><button className="asset-link" onClick={() => pick(asset.symbol, 'market')}><Coin asset={asset} />
            <span><b>{asset.symbol}</b><small>{asset.name}</small></span></button></td>
          <td className="mono">{market ? price(market.close) : '—'}</td>
          <td className={`mono ${moveClass(market?.change ?? 0)}`}>{market ? pct(market.change) : '—'}</td>
          <td className={`mono ${moveClass(market?.dist_sma20 ?? 0)}`}>{market ? pct(market.dist_sma20) : '—'}</td>
          <td className="mono">{market ? pct(market.vol20, 2, false) : '—'}</td>
          <td>{market ? <Sparkline values={market.chart.map(c => c.close)} /> : '—'}</td>
          <td className="nowrap">{market ? date(market.close_ms) : '—'}</td>
          <td>{mode === 'live' ? itemError ? <span className="loss" title={itemError}>Error de consulta</span> :
            latency == null ? 'Pendiente' : `${number(latency, 0)} ms` :
            asset.replay_cycles == null ? <span className="muted">Pendiente</span> :
              <button className="text-action" onClick={() => pick(asset.symbol, 'comparison')}>{asset.replay_cycles} ciclos</button>}</td>
        </tr>)}</tbody></table></div> : <Empty title="Sin activos con ese filtro" />}
    </Panel>
  </>;
}

export function StrategySelect({ value, onChange }: { value: keyof typeof strategies; onChange: (key: keyof typeof strategies) => void }) {
  return <label className="field-inline"><span>Estrategia</span><select value={value} onChange={e => onChange(e.target.value as keyof typeof strategies)}>
    {Object.entries(strategies).map(([key, item]) => <option value={key} key={key}>{item.label}</option>)}
  </select></label>;
}
