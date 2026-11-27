import { useState } from 'react';
import { Activity, ArrowLeft, ArrowRight, CheckCircle2, Cpu, Database, Download, ExternalLink,
  FileCheck2, GitBranch, Layers3, Pause, Play, RefreshCw, Search, ShieldCheck, Square } from 'lucide-react';
import { actionName, date, dateTime, downloadReplay, number, pct, preview, replayPeriod, riskName, statusName } from './data';
import type { Asset, Catalog, Config, Market, Mode, Replay, State, Strategy, TradingRecords } from './data';
import { Badge, Empty, Heading, Metric, Panel, StrategySelect, ValueRows } from './views';

function Hash({ label, value }: { label: string; value: string }) {
  return <details className="hash"><summary>{label}<code title={value}>{value.slice(0, 14)}…</code></summary>
    <code className="full-hash">{value}</code></details>;
}

export function Audit({ asset, catalog, records, replay, mode, strategy, onStrategy }: {
  asset: Asset; catalog: Catalog; records: TradingRecords; replay: Replay | null; mode: Mode;
  strategy: Strategy; onStrategy: (value: Strategy) => void;
}) {
  const [query, setQuery] = useState('');
  const [stage, setStage] = useState('all');
  const model = asset.model;
  const tested = catalog.verification.tests;
  const stages = [...new Set(records.events.map(row => row.stage))].sort();
  const term = query.toLocaleLowerCase('es-MX').trim();
  const visible = records.events
    .filter(row => (stage === 'all' || stage === row.stage) &&
      `${row.message} ${row.code} ${row.symbol ?? ''}`.toLocaleLowerCase('es-MX').includes(term))
    .sort((first, second) => second.id - first.id);
  return <>
    <Heading title="Auditoría" context={`${asset.symbol} · Evidencia del entrenamiento y las decisiones`}
      action={mode === 'historical' && replay && <StrategySelect value={strategy} onChange={onStrategy} />} />
    <div className="metric-grid three">
      <Metric label="Pruebas documentadas" icon={<FileCheck2 size={17} />} value={tested?.tests ?? '—'}
        detail={tested ? `${tested.failures + tested.errors} fallos o errores registrados` : 'Evidencia pendiente'} />
      <Metric label="Archivos de Colab verificados" icon={<Database size={17} />} value={catalog.verification.colab_files ?? '—'} detail="Inventario de la entrega" />
      <Metric label="Diferencia máxima de predicción" icon={<Activity size={17} />}
        value={catalog.verification.max_prediction_error?.toExponential(2) ?? '—'} detail="Inferencia local frente a Colab" />
    </div>
    <div className="control-grid">
      <Panel title="Validación del modelo" detail={asset.symbol}
        action={catalog.verification.notebook_url && <a className="text-action" href={catalog.verification.notebook_url} target="_blank" rel="noreferrer">Colab <ExternalLink size={14} /></a>}>
        {model ? <>
          <ValueRows rows={[
            ['Experimento', <span className="mono">{model.experiment}</span>],
            ['Dispositivo de entrenamiento', model.device],
            ['Evaluación TE', dateTime(model.evaluated_at)],
            ['Diferencia local / Colab', model.inference_error?.toExponential(3) ?? '—'],
          ]} />
          <div className="table-frame"><table><thead><tr><th>Referencia</th><th>Muestras TE</th><th>MAE</th><th>RMSE</th><th>Acierto direccional</th></tr></thead>
            <tbody>{model.metrics.filter(row => row.conjunto === 'TE').map(row => <tr key={row.modelo}>
              <td>{row.modelo}</td><td className="mono">{row.n}</td><td className="mono">{number(row.mae, 6)}</td>
              <td className="mono">{number(row.rmse, 6)}</td><td className="mono">{pct(row.acierto_direccional, 2, false)}</td>
            </tr>)}</tbody></table></div>
        </> : <Empty title="Modelo pendiente" detail={asset.message ?? undefined} />}
      </Panel>
      <Panel title="Trazabilidad" detail="Modelo, transformaciones y evidencia">
        {model ? <>
          <Hash label="SHA-256 del modelo" value={model.model_sha256} />
          <Hash label="SHA-256 del escalador" value={model.scalers_sha256} />
          <Hash label="SHA-256 de los datos" value={model.data_sha256} />
          <ValueRows rows={[
            ['Versión del modelo', model.version], ['Semilla seleccionada', model.seed],
            ['Ventana', `${model.lookback} velas`], ['Variables', model.features.join(', ')],
            ['Ollama registrado', replay?.llm.model ?? '—'],
          ]} />
        </> : <Empty title="Sin manifiesto verificado" />}
      </Panel>
    </div>
    <Panel title="Bitácora de eventos" detail={mode === 'historical' ? replay ? replayPeriod(replay) : asset.symbol : 'Sesión Paper local'}
      action={records.events.length > 0 && (replay ? <button className="button" onClick={() => downloadReplay(replay, 'events', strategy)}><Download size={15} /> Exportar</button> :
        <a className="button" href="/api/export/events"><Download size={15} /> Exportar</a>)}>
      <div className="toolbar">
        <label className="search-box"><Search size={16} /><input aria-label="Buscar eventos" value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar por código o mensaje" /></label>
        <label className="filter"><span>Etapa</span><select value={stage} onChange={e => setStage(e.target.value)}>
          <option value="all">Todas</option>{stages.map(value => <option key={value} value={value}>{value}</option>)}
        </select></label><span className="muted compact">{visible.length} eventos</span>
      </div>
      {visible.length ? <div className="table-frame"><table><thead><tr><th>Registro UTC</th><th>Etapa</th><th>Activo</th><th>Evento</th><th>Detalle</th></tr></thead>
        <tbody>{visible.map(row => <tr key={row.id}>
          <td className="nowrap">{dateTime(row.created_at)}</td><td>{row.stage}</td><td className="mono">{row.symbol ?? '—'}</td>
          <td><Badge tone={['risk', 'auth', 'gateway'].includes(row.stage) ? 'warning' : 'neutral'}>{riskName(row.code)}</Badge></td>
          <td className="wrap-cell">{row.message}</td>
        </tr>)}</tbody></table></div> : <Empty title="Sin eventos para este filtro" />}
    </Panel>
  </>;
}

type ControlAction = 'start' | 'pause' | 'stop' | 'ollama';
const stages = [
  { title: 'Vela cerrada', icon: BarIcon },
  { title: 'Variables', icon: Layers3 },
  { title: 'Modelo DL', icon: Cpu },
  { title: 'Ollama', icon: GitBranch },
  { title: 'Control de riesgo', icon: ShieldCheck },
  { title: 'Registro Paper', icon: Database },
];

function BarIcon({ size }: { size: number }) {
  return <Activity size={size} />;
}

function CycleInspector({ replay, asset, archived }: { replay: Replay | null; asset: Asset; archived: Market | null }) {
  const [step, setStep] = useState(0);
  const [position, setPosition] = useState<number | null>(null);
  const decisions = replay?.records.agente_con_llm.decisions ?? [];
  const selected = Math.min(position ?? decisions.length - 1, decisions.length - 1);
  const row = decisions[selected];
  const candle = archived?.chart.find(item => item.time === row?.close_ms);
  const hasDecision = row !== undefined;
  const details = [
    hasDecision ? `Cierre referenciado en la decisión. ${dateTime(row.close_ms)}${candle ? ` · ${number(candle.close)} USDT` : ''}` :
      'La entrada del pipeline es una vela diaria cerrada de MEXC Spot.',
    asset.model ? `${asset.model.lookback} velas de entrada · ${asset.model.features.join(', ')}.` : 'Variables del manifiesto del modelo.',
    row ? `${asset.model?.experiment ?? 'Modelo archivado'} · Pronóstico de ${pct(row.forecast, 3)}.` : 'La predicción usa el modelo y el escalador versionados.',
    row && replay ? `${replay.llm.model ?? 'Ollama local'} · Propuso ${actionName(row.action).toLowerCase()} · ${number(row.llm_ms / 1000, 2)} s.` :
      'El agente consulta Ollama local para obtener una propuesta y su justificación.',
    row ? `${riskName(row.risk)}. ${row.reason}` : 'El motor aplica exposición, pérdida diaria, saldo y vigencia de la vela.',
    row ? `Decisión ${row.id} · ${row.executed ? 'La orden se ejecutó en Paper.' : 'La propuesta quedó registrada sin orden.'}` :
      'Las decisiones, órdenes y eventos se registran en la base Paper.',
  ];
  return <Panel title="Flujo de una decisión" detail={row ? `${asset.symbol} · Ciclo ${selected + 1} de ${decisions.length}` : asset.symbol}
    action={decisions.length > 0 && <div className="step-controls">
      <button className="icon-button" aria-label="Ciclo anterior" onClick={() => setPosition(selected - 1)} disabled={selected <= 0}><ArrowLeft size={16} /></button>
      <button className="icon-button" aria-label="Siguiente ciclo" onClick={() => setPosition(selected + 1)} disabled={selected >= decisions.length - 1}><ArrowRight size={16} /></button>
      <button className="button compact" onClick={() => setPosition(null)}>Último ciclo</button>
    </div>}>
    <div className="pipeline">{stages.map((item, index) => <button type="button" key={item.title}
      className={`pipeline-step ${step === index ? 'active' : ''}`} aria-pressed={step === index} onClick={() => setStep(index)}>
      <span className="pipeline-icon"><item.icon size={19} /></span><span><small>Paso {index + 1}</small><strong>{item.title}</strong></span>
    </button>)}</div>
    <div className="pipeline-detail"><strong>{stages[step].title}</strong><p>{details[step]}</p></div>
  </Panel>;
}

export function SystemView({ asset, config, live, replay, mode, active, scope, setScope, ready, action, switchLive,
  ollamaStatus }: {
  asset: Asset; config: Config; live: State | null; replay: Replay | null; mode: Mode; active: boolean;
  scope: 'selected' | 'all'; setScope: (value: 'selected' | 'all') => void; ready: number; action: (value: ControlAction) => void;
  switchLive: () => void; ollamaStatus: string;
}) {
  const status = live?.account.status;
  return <>
    <Heading title="Sistema" context="Procesamiento, límites y control de la simulación" />
    <div className="control-grid">
      <Panel title="Agente local" detail={status ? `Estado de la sesión · ${statusName(status)}` : 'Vista histórica'}
        action={!preview && <a className="text-action" href="/docs" target="_blank" rel="noreferrer">API <ExternalLink size={14} /></a>}>
        {preview ? <div className="setup-note">
          <p>Para operar la simulación en vivo, abre la carpeta extraída del proyecto y ejecuta <strong>Iniciar_Windows.bat</strong> o <strong>Iniciar_Mac.command</strong>.</p>
          <p>Usa la clave local indicada en la guía. Ollama se inicia en tu equipo para los replays nuevos y decisiones en vivo.</p>
        </div> : <>
          <ValueRows rows={[
            ['Activos de la sesión', live?.active_symbols.join(', ') || 'Sin seleccionar'],
            ['Ollama configurado', config.ollama_model], ['Estado de Ollama', ollamaStatus],
            ['Frecuencia de revisión', `Cada ${config.risk.poll_seconds} s · decisiones por vela diaria`],
          ]} />
          <div className="control-actions">
            <button className="button" onClick={() => action('ollama')} disabled={active}><RefreshCw size={15} /> Verificar Ollama</button>
            {mode === 'historical' && <button className="button" onClick={switchLive}>Abrir modo en vivo <ArrowRight size={15} /></button>}
          </div>
          {mode === 'live' && <div className="control-actions">
            <label className="field-inline"><span>Alcance</span><select value={scope} onChange={e => setScope(e.target.value as 'selected' | 'all')}>
              <option value="selected">{asset.symbol}</option><option value="all">Modelos verificados ({ready})</option>
            </select></label>
            <button className="button primary" onClick={() => action('start')} disabled={active || (scope === 'selected' ? asset.status !== 'ready' : !ready)}><Play size={15} /> Iniciar</button>
          </div>}
          <div className="control-actions">
            <button className="button" onClick={() => action('pause')} disabled={active || status !== 'running'}><Pause size={15} /> Pausar</button>
            <button className="button danger-button" onClick={() => action('stop')} disabled={active || !status || status === 'stopped'}><Square size={14} /> Detener</button>
          </div>
        </>}
      </Panel>
      <Panel title="Configuración de riesgo">
        <ValueRows rows={[
          ['Capital inicial', `${number(config.risk.initial_cash, 0)} USDT`],
          ['Exposición máxima total', pct(config.risk.max_total_exposure, 0, false)],
          ['Exposición máxima por activo', pct(config.risk.max_asset_exposure, 0, false)],
          ['Pérdida diaria', pct(config.risk.daily_loss_limit, 0, false)],
          ['Antigüedad máxima de una vela', `${config.risk.max_data_age_hours} h`],
          ['Detener agente', 'Conserva posiciones abiertas'],
        ]} />
        <p className="panel-note"><CheckCircle2 size={15} /> Órdenes simuladas con saldo virtual.</p>
      </Panel>
    </div>
    <CycleInspector replay={replay} asset={asset} archived={asset.history} />
    {replay && <Panel title="Ejecución histórica de Ollama" detail={`${replay.symbol} · ${date(replay.last_target)} UTC`}>
      <ValueRows rows={[
        ['Modelo local registrado', replay.llm.model ?? '—'],
        ['Versión de Ollama', replay.llm.ollama_version ?? '—'],
        ['Procesador', replay.llm.processor ?? '—'],
        ['Diferencia de inferencia con Colab', replay.inference_error?.toExponential(3) ?? '—'],
      ]} />
    </Panel>}
  </>;
}
