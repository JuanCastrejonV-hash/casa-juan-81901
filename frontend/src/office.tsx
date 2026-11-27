import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { Activity, ArrowLeft, ArrowRight, ChartCandlestick, Cpu, Database, FileCheck2,
  FlaskConical, Pause, Play, Shield, Sparkles, Waves } from 'lucide-react';
import officeImage from './assets/casa-juan.webp?inline';
import { actionName, api, dateTime, number, pct, price, riskName, statusName } from './data';
import type { Asset, Decision, Market, Mode, Replay, SectionChange, State, Trade } from './data';

type Stage = 'market' | 'variables' | 'model' | 'ollama' | 'risk' | 'ledger';
type LiveEvent = { index: number; symbol: string; at_ms: number; stage: Stage | 'idle' | 'error'; detail: string | null };
const stations = [
  { id: 'market', label: 'Datos', actor: 'Pai', x: 17, y: 52, workX: 19, workY: 64, icon: Waves },
  { id: 'variables', label: 'Variables', actor: 'Pai', x: 32, y: 42, workX: 34, workY: 55, icon: ChartCandlestick },
  { id: 'model', label: 'Modelo DL', actor: 'Wey', x: 45, y: 36, workX: 47, workY: 48, icon: Cpu },
  { id: 'ollama', label: 'Ollama', actor: 'Wey', x: 60, y: 40, workX: 60, workY: 52, icon: Sparkles },
  { id: 'risk', label: 'Riesgo', actor: 'Cawn', x: 75, y: 45, workX: 75, workY: 58, icon: Shield },
  { id: 'ledger', label: 'Bitácora', actor: 'Cawn', x: 87, y: 49, workX: 88, workY: 61, icon: Database },
] as const;
const crew = [
  { name: 'Pai', x: 25, y: 70, color: '#7cdacb', hair: '#2f2928', face: '#e9b888' },
  { name: 'Wey', x: 51, y: 66, color: '#bd95ef', hair: '#352542', face: '#f2b795' },
  { name: 'Cawn', x: 73, y: 65, color: '#f0af68', hair: '#362621', face: '#dca27d' },
] as const;

const stageNames: Record<LiveEvent['stage'], string> = {
  market: 'Validando velas', variables: 'Calculando variables', model: 'Calculando variables y pronóstico',
  ollama: 'Consultando Ollama', risk: 'Aplicando controles', ledger: 'Registrando el ciclo',
  idle: 'En espera', error: 'Ciclo interrumpido',
};

function describeStage(stage: Stage, asset: Asset, market: Market | null, row: Decision | undefined, trade: Trade | undefined) {
  if (!row) {
    return {
      market: 'MEXC Spot. Se verifica que la vela diaria esté cerrada, ordenada y vigente.',
      variables: 'Se usan los indicadores y transformaciones fijados durante el entrenamiento.',
      model: asset.model?.experiment ?? 'El modelo y su escalador deben estar verificados.',
      ollama: 'El modelo local propone la acción y su motivo con información de mercado y cartera.',
      risk: 'El motor Paper valida señal, saldo, exposición y vigencia de la vela.',
      ledger: 'Decisiones, operaciones y eventos quedan registrados para volver a examinarlos.',
    }[stage];
  }
  const candle = market?.chart.find(candle => candle.time === row.close_ms);
  const forecast = pct(row.forecast, 3);
  switch (stage) {
    case 'market':
      return `Vela de ${asset.symbol} archivada al ${dateTime(row.close_ms)}${candle ? ` · ${price(candle.close)} USDT de cierre` : ''}.`;
    case 'variables':
      return `Ventana del modelo: ${asset.model?.lookback ?? '—'} velas${candle?.sma20 != null ? ` · SMA20 ${price(candle.sma20)} USDT` : ''}.`;
    case 'model':
      return `Pronóstico guardado ${forecast} para el rendimiento de la siguiente vela.`;
    case 'ollama':
      return `Propuso ${actionName(row.action).toLocaleLowerCase('es-MX')}${row.llm_ms ? ` en ${number(row.llm_ms / 1000, 2)} s` : ''}. ${row.reason}`;
    case 'risk':
      return `${riskName(row.risk)} · ${row.executed ? 'El motor registró una ejecución Paper' :
        row.risk === 'OK' ? 'La propuesta se registró sin ejecutar una orden' : 'La propuesta quedó sin ejecución'}.`;
    case 'ledger':
      return trade ? `${actionName(trade.side)} Paper a ${price(Number(trade.price))} USDT · ${dateTime(trade.fill_ms)}.` :
        `Decisión ${row.id} guardada en la bitácora.`;
  }
}

function Figure({ person, active }: { person: typeof crew[number]; active: Stage | undefined }) {
  const work = stations.find(station => station.id === active && station.actor === person.name);
  return <span className={work ? 'figure working' : 'figure'} style={{
    left: `${work?.workX ?? person.x}%`, top: `${work?.workY ?? person.y}%`,
    '--shirt': person.color, '--hair': person.hair, '--face': person.face,
  } as CSSProperties} aria-hidden="true">
    <span className="figure-shadow" />
    <span className="figure-person"><i className="figure-head" /><i className="figure-body" />
      <i className="figure-hand left" /><i className="figure-hand right" /><i className="figure-leg left" /><i className="figure-leg right" /></span>
    <span className="figure-name">{person.name}</span>
  </span>;
}

export function Office({ asset, market, mode, replay, live, navigate, openArchive, replayError }: {
  asset: Asset; market: Market | null; mode: Mode; replay: Replay | null; live: State | null;
  navigate: SectionChange; openArchive: () => void; replayError: string;
}) {
  const [cycle, setCycle] = useState(0);
  const [step, setStep] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [inspected, setInspected] = useState<Stage | null>(null);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [activityError, setActivityError] = useState('');
  const historical = mode === 'historical';
  const decisions = replay ? [...replay.records.agente_con_llm.decisions].sort((a, b) => a.close_ms - b.close_ms) : [];
  const row = historical ? decisions[cycle] : live?.decisions.find(decision => decision.symbol === asset.symbol);
  const orders = historical ? replay?.records.agente_con_llm.orders : live?.orders;
  const trade = orders?.find(order => order.decision_id === row?.id && row);
  const latest = events.at(-1);
  const liveStage = latest && latest.stage !== 'idle' && latest.stage !== 'error' ? latest.stage : undefined;
  const active = historical ? playing ? stations[step]?.id : undefined : liveStage;
  const focused = inspected ?? (historical ? stations[step]?.id : liveStage) ?? 'market';
  const chosenStation = stations.find(station => station.id === focused)!;
  const progressLabel = historical ? row ? `Ciclo ${cycle + 1} de ${decisions.length}` :
    replayError ? 'Replay no disponible' : asset.replay_status === 'available' ? 'Cargando replay' : 'Replay disponible en BTCUSDT' :
    latest ? stageNames[latest.stage] : live ? statusName(live.account.status) : 'En espera';

  useEffect(() => {
    if (!historical || !playing) return;
    const timer = window.setTimeout(() => {
      if (step >= stations.length - 1) setPlaying(false);
      else setStep(step + 1);
    }, 1050);
    return () => window.clearTimeout(timer);
  }, [historical, playing, step]);

  useEffect(() => {
    if (historical) return;
    const request = new AbortController();
    let timer = 0;
    async function track() {
      try {
        const result = await api<{ events: LiveEvent[] }>('/lab/activity', 'GET', undefined, request.signal);
        if (!request.signal.aborted) { setEvents(result.events); setActivityError(''); }
      } catch {
        if (!request.signal.aborted) setActivityError('Telemetría temporalmente no disponible.');
      } finally {
        if (!request.signal.aborted) timer = window.setTimeout(track, 800);
      }
    }
    void track();
    return () => { request.abort(); window.clearTimeout(timer); };
  }, [historical]);

  function pickCycle(next: number) {
    setCycle(next);
    setStep(-1);
    setPlaying(false);
    setInspected(null);
  }

  function toggle() {
    setInspected(null);
    if (playing) setPlaying(false);
    else {
      if (step < 0 || step >= stations.length - 1) setStep(0);
      setPlaying(true);
    }
  }

  const latestDecision = row ? actionName(row.action) : '—';
  return <>
    <header className="office-heading">
      <div><p className="office-greeting">Qué onda, Juan.</p><h1>Tu oficina de trading</h1></div>
      <button className="button" onClick={() => navigate('research')}><FlaskConical size={16} /> Abrir laboratorio <ArrowRight size={15} /></button>
    </header>
    <div className="office-grid">
      <section className="office-scene" aria-label="Oficina interactiva de Casa Juan">
        <img src={officeImage} width="1536" height="1024" alt="Oficina con escritorios, palmeras, alberca y autos al atardecer" draggable={false} />
        <div className="scene-source"><span />{historical ? 'Reproducción histórica' : 'Agente Paper en vivo'}</div>
        {stations.map(station => <button key={station.id}
          className={`station ${active === station.id ? 'station-active' : ''} ${inspected === station.id ? 'station-selected' : ''}`}
          aria-label={`Ver estación ${station.label}`} aria-pressed={inspected === station.id}
          style={{ left: `${station.x}%`, top: `${station.y}%` }}
          onClick={() => setInspected(station.id)}>
          <station.icon size={15} /><span>{station.label}</span>
        </button>)}
        {crew.map(person => <Figure key={person.name} person={person} active={active} />)}
      </section>
      <section className="office-console" aria-label={historical ? 'Controles del replay' : 'Actividad del agente'}>
        <header>
          <p>{historical ? 'Recorrido del agente' : `Actividad · ${latest?.symbol ?? asset.symbol}`}</p>
          <h2>{progressLabel}</h2>
          {historical && row && <span className="console-time">{asset.symbol} · {dateTime(row.close_ms)}</span>}
          {!historical && latest && <span className="console-time">{dateTime(latest.at_ms)}</span>}
        </header>
        {historical && row ? <div className="playback-controls">
          <button type="button" className="icon-button" aria-label="Ciclo anterior" disabled={cycle === 0}
            onClick={() => pickCycle(cycle - 1)}><ArrowLeft size={17} /></button>
          <button type="button" className="button primary" onClick={toggle}>{playing ? <Pause size={16} /> : <Play size={16} />}
            {playing ? 'Pausar' : step >= 0 && step < stations.length - 1 ? 'Continuar' : 'Reproducir ciclo'}</button>
          <button type="button" className="icon-button" aria-label="Siguiente ciclo" disabled={cycle + 1 >= decisions.length}
            onClick={() => pickCycle(cycle + 1)}><ArrowRight size={17} /></button>
        </div> : historical && asset.replay_status !== 'available' ?
          <button className="button compact" onClick={openArchive}>Abrir replay de BTCUSDT <ArrowRight size={14} /></button> :
          !historical && <button className="button compact" onClick={() => navigate('system')}>Control del agente <ArrowRight size={14} /></button>}
        <div className="station-list" aria-label="Estaciones y estado">
          {stations.map(station => <button key={station.id} type="button" onClick={() => setInspected(station.id)}
            className={focused === station.id ? 'selected' : ''} aria-pressed={focused === station.id}>
            <station.icon size={16} /><span>{station.label}</span><small>{station.actor}</small>
          </button>)}
        </div>
        <div className="station-readout" aria-live="polite">
          <strong><chosenStation.icon size={16} /> {chosenStation.actor} · {chosenStation.label}</strong>
          <p>{!historical && !inspected && latest?.detail ? riskName(latest.detail) :
            describeStage(focused, asset, market, historical ? row : undefined, trade)}</p>
        </div>
        {(activityError || replayError) && <p className="console-time" role="status">{activityError || replayError}</p>}
        {!historical && events.length > 0 && <details className="office-events">
          <summary>Actividad reciente</summary>
          <ol>{events.slice(-8).reverse().map(event => <li key={event.index}>
            <strong>{event.symbol} · {stageNames[event.stage]}</strong>
            <span>{dateTime(event.at_ms)}{event.detail ? ` · ${riskName(event.detail)}` : ''}</span>
          </li>)}</ol>
        </details>}
      </section>
    </div>
    <div className="office-dock">
      <article><Activity size={18} /><div><span>Pronóstico</span><strong>{row ? pct(row.forecast, 3) : market?.forecast ? pct(market.forecast.value, 3) : '—'}</strong></div>
        <button className="text-action" onClick={() => navigate('market')}>Ver mercado <ArrowRight size={14} /></button></article>
      <article><FileCheck2 size={18} /><div><span>Propuesta registrada</span><strong>{latestDecision}</strong></div>
        <button className="text-action" onClick={() => navigate('operations')}>Ver operaciones <ArrowRight size={14} /></button></article>
      <article><Shield size={18} /><div><span>Control de riesgo</span><strong>{row ? riskName(row.risk) : '—'}</strong></div>
        <button className="text-action" onClick={() => navigate('audit')}>Ver auditoría <ArrowRight size={14} /></button></article>
    </div>
  </>;
}
