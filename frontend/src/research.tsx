import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Download, FlaskConical, Play, Sparkles } from 'lucide-react';
import { Legend, TimeChart } from './chart';
import { actionName, api, date, dateTime, moveClass, number, pct, preview, price } from './data';
import type { Asset } from './data';
import { Badge, Empty, Heading, Metric, Panel, ValueRows } from './views';
import { allocation, capital, describeRule, families, filters, proposals, researchRun, ruleKey, splitHistory } from './strategy';
import type { Costs, Family, Filter, ResearchHistory, ResearchRun, Rule } from './strategy';

type RequestKind = 'grid' | 'ai' | 'manual';
type Ideas = { candidates: Rule[]; model: string; latency_ms: number };
const defaultRule: Rule = { family: 'breakout', lookback: 20, triggerBps: 50, filter: 'volume' };
const colors = { strategy: '#8260a6', reference: '#9c6946' };

function saveFile(name: string, contents: string, type: string) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 800);
}

function showCell(candidate: Rule) {
  return `${candidate.lookback} velas · ${candidate.triggerBps} pb · ${filters[candidate.filter]}`;
}

function Results({ run, history, useRule }: { run: ResearchRun; history: ResearchHistory; useRule: (rule: Rule) => void }) {
  const selected = run.selected;
  const result = run.strategy;
  const rule = selected ? describeRule(selected.rule) : null;
  const passive = run.reference;
  const curves = [
    ...(result ? [{ label: 'Regla evaluada', points: result.points, color: colors.strategy }] : []),
    { label: 'Comprar y mantener', points: passive.points, color: colors.reference, dash: true },
  ];

  function exportExperiment() {
    saveFile(`Casa_Juan_${history.symbol}_experimento.json`, JSON.stringify({
      version: 1, symbol: history.symbol, sourceSha256: history.sha256, excludedFromUtc: new Date(history.excluded_from_ms),
      capital, allocation, ...run,
    }, null, 2), 'application/json');
  }

  return <>
    <Panel title={selected ? `Regla evaluada · ${families[selected.rule.family]}` : 'La búsqueda no encontró una candidata elegible'}
      detail={selected ? showCell(selected.rule) : 'La clasificación exige tres cierres en al menos dos ventanas de validación.'}
      action={<button className="button compact" onClick={exportExperiment}><Download size={15} /> Experimento JSON</button>} className="research-winner">
      <div className="trial-overview">
        {rule ? <ValueRows rows={[[ 'Entrada', rule.entry ], [ 'Salida', rule.exit ],
          [ 'Método de prueba', run.origin ], [ 'Configuraciones evaluadas', run.tested ]]} />
          : <p className="panel-note">Puedes revisar las reglas propuestas y probar una con el editor.</p>}
        <ValueRows rows={[
          ['Tramo final', `${date(run.first)} – ${date(run.last)}`],
          ['Modelo de costos', `${run.costs.feeBps} pb comisión · ${run.costs.slipBps} pb deslizamiento`],
        ]} />
      </div>
    </Panel>
    <div className="metric-grid">
      <Metric label="Retorno de la regla" value={<span className={moveClass(result?.net ?? 0)}>{result ? pct(result.net) : '—'}</span>}
        detail="Rendimiento neto del tramo final" variant="featured" />
      <Metric label="Comprar y mantener" value={<span className={moveClass(passive.net)}>{pct(passive.net)}</span>}
        detail="Mismo tramo, costos y tamaño inicial" />
      <Metric label="Máximo drawdown" value={result ? pct(result.drawdown, 2, false) : '—'}
        detail={`Referencia pasiva ${pct(passive.drawdown, 2, false)}`} />
      <Metric label="Retorno con costos ×2" value={run.doubleCosts ? pct(run.doubleCosts.net) : '—'}
        detail={run.costs.feeBps || run.costs.slipBps ? 'Sensibilidad a costos' : 'Costos en cero'} />
    </div>
    <Panel title="Patrimonio simulado" detail="USDT · valuación al cierre UTC">
      <TimeChart curves={curves} label="Patrimonio de la estrategia y compra pasiva" precision={number} />
      <Legend entries={curves} />
      {result && <div className="research-trade-stats">
        <span>Cierres <b>{result.trades}</b></span>
        <span>Win rate <b>{result.winRate == null ? '—' : pct(result.winRate, 2, false)}</b></span>
        <span>Velas con posición <b>{pct(result.exposure, 1, false)}</b></span>
        <span>Comisión total <b>{number(result.fees)} USDT</b></span>
      </div>}
    </Panel>
    <Panel title="Clasificación en validación" detail={run.selectionWindows.map(([a, b]) => `${date(a, true)}–${date(b, true)}`).join(' · ')}
      action={<span className="muted compact">{Math.min(12, run.ranked.length)} de {run.tested}</span>}>
      <div className="table-frame"><table><thead><tr>
        <th>Familia</th><th>Configuración</th><th>Retorno V1</th><th>Retorno V2</th><th>Retorno V3</th>
        <th>Puntuación</th><th>Cierres</th><th>Regla</th>
      </tr></thead><tbody>{run.ranked.slice(0, 12).map(row => <tr key={ruleKey(row.rule)}>
        <td>{families[row.rule.family]}</td><td>{showCell(row.rule)}</td>
        {row.validation.map((piece, i) => <td key={i} className={`mono ${moveClass(piece.net)}`}>{pct(piece.net)}</td>)}
        <td className="mono">{pct(row.score, 2, false)}</td><td className="mono">{row.trades}</td>
        <td><button className="text-action" onClick={() => useRule(row.rule)}>Editar <ArrowUpRight size={14} /></button></td>
      </tr>)}</tbody></table></div>
      <p className="panel-note">Puntuación de selección = mediana de (retorno neto − drawdown). Cada ventana comienza en efectivo.</p>
    </Panel>
    {result && <Panel title="Operaciones del tramo final" detail={`${result.orders.length} movimientos de la regla`}>
      {result.orders.length ? <div className="table-frame research-orders"><table><thead><tr>
        <th>Fecha UTC</th><th>Acción</th><th>Precio ejecutado</th><th>Comisión</th><th>PnL</th><th>Motivo</th>
      </tr></thead><tbody>{result.orders.map(row => <tr key={row.at}>
        <td className="nowrap">{dateTime(row.at)}</td><td><Badge tone={row.side === 'BUY' ? 'good' : 'neutral'}>{actionName(row.side)}</Badge></td>
        <td className="mono">{price(row.fill)}</td><td className="mono">{number(row.fee)}</td>
        <td className={`mono ${moveClass(row.pnl ?? 0)}`}>{row.pnl == null ? '—' : number(row.pnl)}</td><td>{row.reason}</td>
      </tr>)}</tbody></table></div> : <Empty title="La regla mantuvo el efectivo durante el tramo" />}
    </Panel>}
  </>;
}

export function ResearchView({ asset }: { asset: Asset }) {
  const [history, setHistory] = useState<ResearchHistory | null>(null);
  const [loadError, setLoadError] = useState('');
  const [rule, setRule] = useState(defaultRule);
  const [costs, setCosts] = useState<Costs>({ feeBps: 10, slipBps: 2 });
  const [busy, setBusy] = useState<RequestKind | null>(null);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [error, setError] = useState('');
  const activeRequest = useRef<AbortController | null>(null);
  const editor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const loading = new AbortController();
    api<ResearchHistory>(`/lab/research/${asset.symbol}`, 'GET', undefined, loading.signal)
      .then(setHistory).catch(error => { if (!loading.signal.aborted) setLoadError(error.message); });
    return () => {
      loading.abort();
      activeRequest.current?.abort();
    };
  }, [asset.symbol]);

  async function start(kind: RequestKind) {
    if (!history || activeRequest.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(kind);
    setProgress({ done: 0, total: 0 });
    setError('');
    try {
      let origin = 'Generador de reglas';
      let candidates = proposals();
      if (kind === 'ai') {
        const ideas = await api<Ideas>(`/lab/research/${asset.symbol}/ideas`, 'POST', undefined, controller.signal);
        candidates = ideas.candidates;
        origin = `${ideas.model} local · ${number(ideas.latency_ms / 1000, 1)} s`;
      }
      if (kind === 'manual') {
        candidates = [rule];
        origin = 'Regla de Juan';
      }
      const result = await researchRun(history, candidates, costs, origin,
        (done, total) => { if (!controller.signal.aborted) setProgress({ done, total }); },
        controller.signal, kind === 'manual');
      if (!controller.signal.aborted) setRun(result);
    } catch (error) {
      if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'No se completó el experimento.');
    } finally {
      activeRequest.current = null;
      if (!controller.signal.aborted) setBusy(null);
    }
  }

  const validation = history ? splitHistory(history.bars) : null;
  const ruleDetails = describeRule(rule);
  return <>
    <Heading title="Laboratorio de estrategias" context={`${asset.symbol} · Velas diarias históricas`} />
    <div className="research-intro">
      <div>
        <h2>Diseña, prueba y compara</h2>
        <p>Genera reglas de tendencia, ruptura, impulso y reversión. Cada candidata se puntúa en tres ventanas de validación y la elegida se enfrenta a comprar y mantener en un tramo posterior.</p>
      </div>
      <div className="research-actions">
        <button className="button primary" disabled={!history || !!busy} onClick={() => start('grid')}><FlaskConical size={16} /> Generar y probar</button>
        {!preview && <button className="button" disabled={!history || !!busy} onClick={() => start('ai')}><Sparkles size={16} /> Idear con Ollama</button>}
      </div>
    </div>
    {loadError && <div className="inline-error" role="alert">{loadError}</div>}
    {!history && !loadError && <p role="status" className="inline-status">Preparando historia verificada…</p>}
    {error && <div className="inline-error" role="alert">{error}</div>}
    {busy && <div className="research-progress" role="status">
      <span>{progress.total ? `Validando reglas · ${progress.done} / ${progress.total}`
        : busy === 'ai' ? 'Ollama está redactando reglas estructuradas' : 'Preparando candidatos'}</span>
      <progress value={progress.total ? progress.done : undefined} max={progress.total || 1} />
    </div>}
    <div className="control-grid research-controls" ref={editor}>
      <Panel title="Editor de reglas" detail="Evalúa una configuración que elijas">
        <fieldset disabled={!!busy} className="rule-editor">
          <label>Familia<select value={rule.family} onChange={event => {
            const family = event.target.value as Family;
            setRule(previous => ({ ...previous, family, triggerBps: family === 'reversion' ? Math.max(1, previous.triggerBps) : previous.triggerBps }));
          }}>{Object.entries(families).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
          <label>Ventana (velas)<input type="number" min={5} max={90} value={rule.lookback}
            onChange={event => setRule({ ...rule, lookback: Number(event.target.value) })} /></label>
          <label>Umbral (pb)<input type="number" min={rule.family === 'reversion' ? 1 : 0} max={1000} value={rule.triggerBps}
            onChange={event => setRule({ ...rule, triggerBps: Number(event.target.value) })} /></label>
          <label>Filtro de entrada<select value={rule.filter} onChange={event => setRule({ ...rule, filter: event.target.value as Filter })}>
            {Object.entries(filters).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        </fieldset>
        <p className="panel-note">{ruleDetails.entry}. Salida cuando {ruleDetails.exit.toLocaleLowerCase('es-MX')}.</p>
        <button className="button compact" disabled={!history || !!busy} onClick={() => start('manual')}><Play size={15} /> Probar mi regla</button>
      </Panel>
      <Panel title="Condiciones del experimento" detail="Señal al cierre · ejecución en la apertura siguiente">
        <fieldset disabled={!!busy} className="rule-editor cost-editor">
          <label>Comisión (pb)<input type="number" min={0} max={100} value={costs.feeBps}
            onChange={event => setCosts({ ...costs, feeBps: Number(event.target.value) })} /></label>
          <label>Deslizamiento (pb)<input type="number" min={0} max={100} value={costs.slipBps}
            onChange={event => setCosts({ ...costs, slipBps: Number(event.target.value) })} /></label>
        </fieldset>
        <ValueRows rows={[
          ['Capital y exposición', `${number(capital, 0)} USDT · hasta ${pct(allocation, 0, false)} por compra`],
          ['Historia para investigar', history ? `${number(history.bars.length, 0)} velas previas al TE académico` : '—'],
          ['Tramo final', history && validation ? `${date(history.bars[validation.evaluation.start][0])} – ${date(history.bars.at(-1)?.[0])}` : '—'],
        ]} />
      </Panel>
    </div>
    {run && history && <Results run={run} history={history} useRule={candidate => { setRule(candidate); editor.current?.scrollIntoView({ block: 'nearest' }); }} />}
  </>;
}
