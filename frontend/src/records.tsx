import { useState } from 'react';
import type { ReactNode } from 'react';
import { Activity, ArrowRight, Download, Play, ShieldCheck, Wallet } from 'lucide-react';
import { Legend, TimeChart } from './chart';
import { actionName, dateTime, downloadReplay, moveClass, number, pct, preview, price, replayPeriod,
  replayStats, riskName, strategies, strategyKeys } from './data';
import type { Asset, Config, Job, Mode, Replay, State, Strategy, TradingRecords } from './data';
import { Badge, Empty, Heading, Metric, Panel, StrategySelect, ValueRows } from './views';

export function ReplayNeeded({ asset, jobs, busy, start, example }: {
  asset: Asset; jobs: Job[]; busy: boolean; start: () => void; example: () => void;
}) {
  const active = jobs.find(job => job.symbol === asset.symbol && job.status === 'running');
  const failure = [...jobs].reverse().find(job => job.symbol === asset.symbol && job.status === 'failed');
  const anyActive = jobs.some(job => job.status === 'running');
  const interrupted = asset.replay_status === 'interrupted';
  const available = asset.replay_status === 'available';
  const detail = failure?.error || (active ? 'Procesando velas, propuestas de Ollama y controles de riesgo.' :
    interrupted ? 'El intento conserva su evidencia. Consulta los eventos de la sesión.' : available ?
    'Leyendo el replay de este activo.' : preview ? 'Genera el replay de este activo al iniciar la aplicación local con Ollama.' :
    'Ejecuta 30 ciclos con sus velas archivadas y el modelo verificado.');
  return <Panel title="Replay histórico">
    <Empty title={active ? 'Replay en curso' : interrupted ? 'Replay interrumpido' : available ? 'Cargando resultados' : 'Replay pendiente'}
      detail={detail} action={<div className="empty-actions">
        {!preview && !interrupted && !available && <button className="button primary" onClick={start}
          disabled={asset.status !== 'ready' || anyActive || busy}><Play size={15} /> Ejecutar 30 ciclos</button>}
        {asset.symbol !== 'BTCUSDT' && <button className="button" onClick={example}>Abrir BTCUSDT <ArrowRight size={15} /></button>}
      </div>} />
  </Panel>;
}

function RiskMeter({ label, value, max }: { label: string; value: number; max: number }) {
  const ratio = Math.min(1, Math.max(0, value / max));
  return <div className="meter"><div><span>{label}</span><strong>{pct(value, 1, false)} / {pct(max, 0, false)}</strong></div>
    <div className="meter-track" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max * 100} aria-valuenow={Math.min(value, max) * 100}>
      <i style={{ width: `${ratio * 100}%` }} className={ratio >= .85 ? 'warn-meter' : ''} />
    </div></div>;
}

export function Operations({ mode, replay, asset, config, live, records, strategy, onStrategy, missing }: {
  mode: Mode; replay: Replay | null; asset: Asset; config: Config; live: State | null; records: TradingRecords;
  strategy: Strategy; onStrategy: (value: Strategy) => void; missing: ReactNode;
}) {
  const [outcome, setOutcome] = useState('all');
  const historical = mode === 'historical';
  const stats = replayStats(replay, strategy);
  const last = records.equity.at(-1);
  const account = historical ? last : live?.account;
  const cash = account?.cash, exposure = account?.exposure;
  const initial = historical ? replay?.initial_cash : live?.account.initial;
  const equity = historical ? stats?.patrimonio_final : live?.account.equity;
  const pnl = equity == null || initial == null ? null : (equity - initial);
  const dailyLoss = !historical && live && live.daily_equity > 0 &&
    live.daily_day === new Date().toISOString().slice(0, 10)
    ? Math.max(0, 1 - live.account.equity / live.daily_equity) : null;
  const positions = historical ? [] : live?.account.positions.filter(position => position.qty > 0) ?? [];
  const scoped = [...records.decisions].filter(row => row.symbol === asset.symbol).sort((a, b) => b.close_ms - a.close_ms);
  const orders = [...records.orders].filter(row => row.symbol === asset.symbol).sort((a, b) => b.fill_ms - a.fill_ms);
  const decisions = scoped.filter(row => outcome === 'all' || (outcome === 'executed' ? row.executed === 1 : row.risk !== 'OK'));
  return <>
    <Heading title="Operaciones Paper" context={historical ? replay ? `${asset.symbol} · ${replayPeriod(replay)}` : asset.symbol :
      `Cartera compartida · Registros de ${asset.symbol}`} action={historical && replay && <StrategySelect value={strategy} onChange={onStrategy} />} />
    {historical && !replay ? missing : <>
      <div className="metric-grid">
        <Metric label="Patrimonio" value={equity == null ? '—' : number(equity)} detail="USDT" icon={<Wallet size={17} />} variant="featured" />
        <Metric label="Efectivo" value={cash == null ? '—' : number(cash)} detail="USDT disponibles" />
        <Metric label="Invertido" value={exposure == null ? '—' : number(exposure)} detail="Valor de posiciones" />
        <Metric label="Ganancia / pérdida" value={pnl == null ? '—' : <span className={moveClass(pnl)}>{number(pnl)}</span>}
          detail={initial && equity != null ? `${pct(equity / initial - 1)} sobre el capital inicial` : 'USDT'} />
      </div>
      <div className="control-grid">
        <Panel title="Órdenes ejecutadas" detail={`${asset.symbol} · ${orders.length} registros`}
          action={orders.length > 0 && (replay ? <button className="button compact" onClick={() => downloadReplay(replay, 'orders', strategy)}>
            <Download size={15} /> CSV</button> : <a className="button compact" href="/api/export/orders"><Download size={15} /> CSV</a>)}>
          {orders.length ? <div className="table-frame"><table><thead><tr><th>Hora UTC</th><th>Acción</th><th>Precio</th><th>Cantidad</th><th>PnL · USDT</th></tr></thead>
            <tbody>{orders.map(row => <tr key={row.id}>
              <td className="nowrap">{dateTime(row.fill_ms)}</td><td><Badge tone={row.side === 'BUY' ? 'good' : 'neutral'}>{actionName(row.side)}</Badge></td>
              <td className="mono">{price(Number(row.price))}</td><td className="mono">{number(Number(row.qty), 6)}</td>
              <td className={`mono ${moveClass(Number(row.pnl))}`}>{row.pnl == null ? '—' : number(Number(row.pnl))}</td>
            </tr>)}</tbody></table></div> : <Empty title="Aún no hay órdenes para este activo" />}
        </Panel>
        <Panel title="Límites Paper" detail="Reglas de riesgo del motor" className="risk-panel">
          <RiskMeter label="Exposición actual" value={equity && exposure != null ? exposure / equity : 0} max={config.risk.max_total_exposure} />
          {dailyLoss != null && <RiskMeter label="Pérdida del día UTC" value={dailyLoss} max={config.risk.daily_loss_limit} />}
          <ValueRows rows={[
            ['Exposición máxima por activo', pct(config.risk.max_asset_exposure, 0, false)],
            ['Límite de pérdida diaria', pct(config.risk.daily_loss_limit, 0, false)],
            ['Comisión por ejecución', pct(historical ? replay?.fee ?? config.risk.fee : config.risk.fee, 2, false)],
            ['Deslizamiento por ejecución', `${historical ? replay?.slippage_bps ?? config.risk.slippage_bps : config.risk.slippage_bps} pb`],
          ]} />
        </Panel>
      </div>
      {!historical && <Panel title="Posiciones abiertas" detail="Cartera Paper compartida">
        {positions.length ? <div className="table-frame"><table><thead><tr><th>Activo</th><th>Cantidad</th><th>Valor · USDT</th><th>Última valoración</th></tr></thead>
          <tbody>{positions.map(position => <tr key={position.symbol}><td className="mono">{position.symbol}</td>
            <td className="mono">{number(position.qty, 6)}</td><td className="mono">{number(position.value)}</td>
            <td className="nowrap">{dateTime(position.mark_ms)}</td></tr>)}</tbody></table></div>
          : <Empty title="Sin posiciones abiertas en esta sesión" />}
      </Panel>}
      {!historical && records.equity.length > 1 && <Panel title="Patrimonio de la sesión" detail="Valoraciones registradas de la cartera Paper">
        <TimeChart label="Patrimonio Paper en vivo en USDT" precision={number} curves={[{
          label: 'Patrimonio', color: strategies.agente_con_llm.color, fill: true,
          points: records.equity.map(row => ({ time: row.event_ms, value: row.equity })),
        }]} />
      </Panel>}
      <Panel title="Decisiones" detail={`${scoped.length} registros de ${asset.symbol}`}
        action={scoped.length > 0 && (replay ? <button className="button" onClick={() => downloadReplay(replay, 'decisions', strategy)}>
          <Download size={15} /> Exportar</button> : <a className="button" href="/api/export/decisions"><Download size={15} /> Exportar</a>)}>
        <div className="toolbar"><label className="filter"><span>Resultado</span><select value={outcome} onChange={e => setOutcome(e.target.value)}>
          <option value="all">Todos</option><option value="executed">Ejecutadas</option><option value="blocked">Rechazadas</option>
        </select></label></div>
        {decisions.length ? <div className="table-frame"><table><thead><tr><th>Cierre</th><th>Propuesta</th><th>Pronóstico</th><th>Resultado</th><th>Razón</th><th>Latencia</th></tr></thead>
          <tbody>{decisions.map(row => <tr key={row.id}>
            <td className="nowrap">{dateTime(row.close_ms)}</td><td>{actionName(row.action)}</td>
            <td className="mono">{pct(row.forecast, 3)}</td>
            <td><Badge tone={row.executed ? 'good' : row.risk === 'OK' ? 'neutral' : 'warning'}>{row.executed ? 'Ejecutada' : row.risk === 'OK' ? 'Sin orden' : riskName(row.risk)}</Badge></td>
            <td className="wrap-cell">{row.reason}</td><td className="mono nowrap">{row.llm_ms ? `${number(row.llm_ms / 1000, 2)} s` : '—'}</td>
          </tr>)}</tbody></table></div> : <Empty title="Sin decisiones para este filtro" />}
      </Panel>
    </>}
  </>;
}

export function Comparison({ asset, replay, mode, useHistorical, missing }: {
  asset: Asset; replay: Replay | null; mode: Mode; useHistorical: () => void; missing: ReactNode;
}) {
  const [shown, setShown] = useState<Strategy[]>(strategyKeys);
  if (mode === 'live') return <>
    <Heading title="Comparación de estrategias" context={asset.symbol} />
    <Panel title="Comparación histórica"><Empty title="Comparación con velas archivadas"
      detail="Las tres estrategias se contrastan con el mismo periodo y los mismos costos."
      action={<button className="button primary" onClick={useHistorical}>Abrir histórico <ArrowRight size={15} /></button>} /></Panel>
  </>;
  if (!replay) return <><Heading title="Comparación de estrategias" context={asset.symbol} />{missing}</>;
  const rows = strategyKeys.flatMap(key => {
    const row = replayStats(replay, key);
    return row ? [row] : [];
  });
  const curves = shown.map(key => ({ ...strategies[key], dash: key !== 'agente_con_llm',
    points: replay.records[key].equity.map(item => ({ time: item.event_ms, value: item.equity })) }));
  const trajectory = replay.records.agente_con_llm.equity;
  const equal = strategyKeys.every(key => replay.records[key].equity.length === trajectory.length &&
    replay.records[key].equity.every((point, index) => point.event_ms === trajectory[index].event_ms && point.equity === trajectory[index].equity));
  const maximum = Math.max(...rows.map(row => row.rendimiento_neto));
  const leaders = rows.filter(row => row.rendimiento_neto === maximum);
  const metrics = [
    { label: 'Rendimiento neto', show: (r: typeof rows[number]) => <b className={moveClass(r.rendimiento_neto)}>{pct(r.rendimiento_neto)}</b> },
    { label: 'Patrimonio final · USDT', show: (r: typeof rows[number]) => number(r.patrimonio_final) },
    { label: 'Caída máxima', show: (r: typeof rows[number]) => pct(r.max_drawdown, 2, false) },
    { label: 'Operaciones ejecutadas', show: (r: typeof rows[number]) => replay.records[r.estrategia].orders.length },
    { label: 'Operaciones cerradas', show: (r: typeof rows[number]) => r.operaciones_cerradas },
    { label: 'Tasa de acierto', show: (r: typeof rows[number]) => r.win_rate == null ? 'Sin cierres' : pct(r.win_rate, 1, false) },
    { label: 'Propuestas rechazadas', show: (r: typeof rows[number]) => r.acciones_rechazadas },
    { label: 'Comisiones · USDT', show: (r: typeof rows[number]) => number(r.costos) },
    { label: 'Latencia media de Ollama', show: (r: typeof rows[number]) => r.estrategia === 'agente_con_llm' && r.latencia_llm_ms_media != null ?
      `${number(r.latencia_llm_ms_media / 1000, 2)} s` : '—' },
  ];
  return <>
    <Heading title="Comparación de estrategias" context={`${asset.symbol} · ${replayPeriod(replay)}`}
      action={<button className="button" onClick={() => downloadReplay(replay, 'comparison', 'agente_con_llm')}><Download size={16} /> Exportar comparación</button>} />
    <div className="metric-grid three">
      {rows.map(row => <Metric key={row.estrategia} label={strategies[row.estrategia].label}
        value={number(row.patrimonio_final)} detail={<>USDT <b className={moveClass(row.rendimiento_neto)}>{pct(row.rendimiento_neto)}</b></>}
        icon={<Wallet size={17} />} variant={row.estrategia === 'agente_con_llm' ? 'featured' : ''} />)}
    </div>
    <Panel title="Evolución del patrimonio" detail={`${replay.cycles} ciclos · ${number(replay.initial_cash, 0)} USDT por estrategia`} className="equity-panel"
      action={<div className="toggles">{strategyKeys.map(key =>
        <label key={key}><input type="checkbox" checked={shown.includes(key)}
          disabled={shown.length === 1 && shown.includes(key)}
          onChange={() => setShown(current => current.includes(key) ? current.filter(k => k !== key) : [...current, key])} />
          {strategies[key].label}</label>)}</div>}>
      <TimeChart curves={curves} precision={number} label="Evolución histórica del patrimonio en USDT" />
      <Legend entries={curves} />
      {equal && <p className="chart-note">Las tres trayectorias coinciden en este periodo.</p>}
    </Panel>
    <Panel title="Resultados del replay" detail={`Comisión ${pct(replay.fee, 2, false)} · Deslizamiento ${replay.slippage_bps} puntos básicos por ejecución`}>
      <div className="table-frame"><table><thead><tr><th>Métrica</th>{rows.map(r => <th key={r.estrategia}>
        <span className="strategy-heading"><i style={{ background: strategies[r.estrategia].color }} />{strategies[r.estrategia].label}</span>
      </th>)}</tr></thead><tbody>{metrics.map(metric => <tr key={metric.label}><th scope="row">{metric.label}</th>
        {rows.map(r => <td key={r.estrategia} className="mono">{metric.show(r)}</td>)}</tr>)}</tbody></table></div>
      <p className="panel-note"><Activity size={16} /> {leaders.length === rows.length
        ? `Igual rendimiento neto para las tres estrategias en los ${replay.cycles} ciclos.`
        : leaders.length > 1 ? `${leaders.map(row => strategies[row.estrategia].label).join(' y ')} empataron en el mayor rendimiento del replay.` :
          `${strategies[leaders[0].estrategia].label} obtuvo el mayor rendimiento observado.`}</p>
    </Panel>
  </>;
}

export function PaperLabel() {
  return <span className="paper-label"><ShieldCheck size={16} /> Solo Paper</span>;
}
