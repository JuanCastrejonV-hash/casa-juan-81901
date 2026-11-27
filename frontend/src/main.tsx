import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowRight, ChartLine, FlaskConical, House, LockKeyhole,
  LogOut, RefreshCw, Settings2, Wallet, X } from 'lucide-react';
import { api, ApiError, emptyRecords, preview } from './data';
import type { Catalog, Config, Job, LiveScan, Market, Mode, Replay, State, Strategy, View } from './data';
import { Empty, MarketView, Overview, Panel, Scanner } from './views';
import { Comparison, Operations, PaperLabel, ReplayNeeded } from './records';
import { Audit, SystemView } from './inspection';
import { Office } from './office';
import { ResearchView } from './research';
import './style.css';
import './house.css';

const rooms = [
  { label: 'Oficina', icon: House, screens: [{ key: 'office', label: 'Oficina' }] },
  { label: 'Laboratorio', icon: FlaskConical, screens: [{ key: 'research', label: 'Laboratorio' }] },
  { label: 'Mercado', icon: ChartLine, screens: [
    { key: 'market', label: 'Gráfico y señal' }, { key: 'scanner', label: 'Escáner de activos' }] },
  { label: 'Simulación', icon: Wallet, screens: [
    { key: 'operations', label: 'Operaciones' }, { key: 'comparison', label: 'Comparativa' },
    { key: 'overview', label: 'Resumen' }] },
  { label: 'Control', icon: Settings2, screens: [
    { key: 'system', label: 'Agente Paper' }, { key: 'audit', label: 'Auditoría' }] },
] as const;
type Boot = { catalog: Catalog; config: Config; state: State | null; jobs: Job[] };
type Notice = { text: string; error?: boolean };

function Brand() {
  return <div className="brand"><span className="brand-mark" aria-hidden="true">CJ</span>
    <strong>Casa Juan</strong></div>;
}

async function loadWorkspace(signal?: AbortSignal): Promise<Boot> {
  const state = preview ? null : await api<State>('/state', 'GET', undefined, signal);
  const [catalog, config, jobs] = await Promise.all([
    api<Catalog>('/lab/catalog', 'GET', undefined, signal), api<Config>('/config', 'GET', undefined, signal),
    preview ? Promise.resolve([]) : api<Job[]>('/replay/jobs', 'GET', undefined, signal),
  ]);
  return { catalog, config, state, jobs };
}

function isSessionError(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}

function Workspace({ boot, logout, sessionExpired }: { boot: Boot; logout: () => void; sessionExpired: () => void }) {
  const [catalog, setCatalog] = useState(boot.catalog);
  const [live, setLive] = useState(boot.state);
  const [jobs, setJobs] = useState(boot.jobs);
  const [view, setView] = useState<View>('office');
  const [mode, setMode] = useState<Mode>('historical');
  const [symbol, setSymbol] = useState(boot.catalog.assets.find(a => a.replay_status === 'available')?.symbol ??
    boot.catalog.assets[0]?.symbol ?? 'BTCUSDT');
  const [strategy, setStrategy] = useState<Strategy>('agente_con_llm');
  const [market, setMarket] = useState<Market | null>(null);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [scan, setScan] = useState<LiveScan | null>(null);
  const [scope, setScope] = useState<'selected' | 'all'>('selected');
  const [marketLoading, setMarketLoading] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [marketError, setMarketError] = useState('');
  const [replayError, setReplayError] = useState('');
  const [scanError, setScanError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [ollamaStatus, setOllamaStatus] = useState('Pendiente de verificar');
  const asset = catalog.assets.find(item => item.symbol === symbol);
  const hasReplay = asset?.replay_status === 'available';
  const report = mode === 'historical' && replay?.symbol === symbol ? replay : null;
  const currentMarket = market?.symbol === symbol && market.source === mode ? market :
    mode === 'historical' ? asset?.history ?? null : null;
  const records = mode === 'historical' ? report?.records[strategy] ?? emptyRecords : live ?? emptyRecords;
  const ready = catalog.assets.filter(item => item.status === 'ready');

  const showError = useCallback((error: unknown) => {
    if (isSessionError(error)) sessionExpired();
    else setNotice({ text: error instanceof Error ? error.message : 'La solicitud no se completó.', error: true });
  }, [sessionExpired]);

  useEffect(() => {
    if (preview) return;
    let mounted = true;
    const timer = window.setInterval(async () => {
      try {
        const [state, reports] = await Promise.all([api<State>('/state'), api<Job[]>('/replay/jobs')]);
        if (mounted) { setLive(state); setJobs(reports); }
      } catch (error) {
        if (mounted && isSessionError(error)) sessionExpired();
      }
    }, 6500);
    return () => { mounted = false; window.clearInterval(timer); };
  }, [sessionExpired]);

  const jobStates = jobs.map(job => `${job.id}:${job.status}`).join('|');
  useEffect(() => {
    if (preview || !jobStates) return;
    const ctl = new AbortController();
    api<Catalog>('/lab/catalog', 'GET', undefined, ctl.signal).then(setCatalog).catch(error => {
      if (!ctl.signal.aborted) showError(error);
    });
    return () => ctl.abort();
  }, [jobStates, showError]);

  useEffect(() => {
    const ctl = new AbortController();
    setMarketError('');
    setMarketLoading(true);
    api<Market>(`/lab/market/${symbol}?source=${mode}`, 'GET', undefined, ctl.signal).then(result => {
      if (!ctl.signal.aborted) setMarket(result);
    }).catch(error => {
      if (ctl.signal.aborted) return;
      if (isSessionError(error)) sessionExpired();
      else { setMarket(null); setMarketError((error as Error).message); }
    }).finally(() => { if (!ctl.signal.aborted) setMarketLoading(false); });
    return () => ctl.abort();
  }, [symbol, mode, refresh, sessionExpired]);

  useEffect(() => {
    setReplayError('');
    if (!hasReplay || mode !== 'historical') return;
    const ctl = new AbortController();
    api<Replay>(`/lab/replay/${symbol}`, 'GET', undefined, ctl.signal).then(result => {
      if (!ctl.signal.aborted) setReplay(result);
    }).catch(error => {
      if (ctl.signal.aborted) return;
      if (isSessionError(error)) sessionExpired();
      else setReplayError((error as Error).message);
    });
    return () => ctl.abort();
  }, [symbol, hasReplay, refresh, mode, sessionExpired]);

  function navigate(value: View) {
    setView(value);
    if (value !== view) window.scrollTo(0, 0);
  }
  function pick(value: string, target?: View) {
    setSymbol(value);
    if (target) navigate(target);
  }
  function changeMode(next: Mode) {
    if (preview && next === 'live') return;
    if (mode !== next) setMarket(null);
    setNotice(null);
    setMode(next);
  }
  async function scanMarket() {
    if (preview || scanLoading) return;
    setScanError('');
    setScanLoading(true);
    try { setScan(await api<LiveScan>('/lab/scanner')); }
    catch (error) {
      if (isSessionError(error)) sessionExpired();
      else { setScan(null); setScanError((error as Error).message); }
    } finally { setScanLoading(false); }
  }
  async function refreshCurrent() {
    if (view === 'scanner' && mode === 'live') { await scanMarket(); return; }
    setRefresh(value => value + 1);
    if (preview) return;
    try {
      const [next, state, reports] = await Promise.all([api<Catalog>('/lab/catalog'), api<State>('/state'), api<Job[]>('/replay/jobs')]);
      setCatalog(next); setLive(state); setJobs(reports);
    } catch (error) { showError(error); }
  }

  async function control(action: 'start' | 'pause' | 'stop' | 'ollama') {
    if (preview || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      if (action === 'ollama') {
        const service = await api<{ model: string; ollama_version: string }>('/llm/health');
        setOllamaStatus(`${service.model} · ${service.ollama_version}`);
        setNotice({ text: 'Ollama verificado en el equipo.' });
        return;
      }
      await api(`/control/${action}`, 'POST', action === 'start'
        ? { symbols: scope === 'all' ? ready.map(item => item.symbol) : [symbol] } : undefined);
      setLive(await api<State>('/state'));
      setNotice({ text: ({ start: 'Agente Paper iniciado.', pause: 'Agente Paper en pausa.', stop: 'Agente Paper detenido.' })[action] });
    } catch (error) {
      if (action === 'ollama') setOllamaStatus('No disponible');
      showError(error);
    } finally { setBusy(false); }
  }
  async function startReplay() {
    if (preview || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const job = await api<Job>('/replay/start', 'POST', { symbol, cycles: 30 });
      setJobs(current => [...current, job]);
    } catch (error) { showError(error); }
    finally { setBusy(false); }
  }
  async function endSession() {
    try { await api('/logout', 'POST'); logout(); }
    catch (error) { showError(error); }
  }

  const refreshQuote = () => setRefresh(value => value + 1);
  const missing = asset && (replayError ?
    <Panel title="Replay histórico"><Empty title="Error al abrir los registros" detail={replayError}
      action={<button className="button" onClick={refreshQuote}>Reintentar</button>} /></Panel> :
    <ReplayNeeded asset={asset} busy={busy} jobs={jobs} start={startReplay} example={() => pick('BTCUSDT', 'comparison')} />);
  const marketProps = { market: currentMarket, loading: marketLoading, error: marketError, refresh: refreshQuote };

  const room = rooms.find(item => item.screens.some(screen => screen.key === view));
  return <div className="house">
    <header className="house-header">
      <div className="house-header-inner">
        <Brand />
        <div className="house-options">
          <div className="segments mode-switch" aria-label="Fuente de datos">
            <button aria-pressed={mode === 'historical'} onClick={() => changeMode('historical')}>Histórico</button>
            <button aria-pressed={mode === 'live'} onClick={() => changeMode('live')} disabled={preview}
              title={preview ? 'Disponible en el agente local' : 'Consultar MEXC Spot'}>En vivo</button>
          </div>
          <label className="symbol-picker"><span>Activo</span><select aria-label="Activo" value={symbol} onChange={event => pick(event.target.value)}>
            {catalog.assets.map(item => <option key={item.symbol} value={item.symbol}>{item.symbol}</option>)}</select></label>
          <button className="icon-button" onClick={refreshCurrent} aria-label="Actualizar datos" title="Actualizar datos">
            <RefreshCw size={16} className={marketLoading || scanLoading ? 'spin' : ''} /></button>
          <PaperLabel />
          {!preview && <button className="icon-button sign-out" onClick={endSession} aria-label="Cerrar sesión" title="Cerrar sesión"><LogOut size={16} /></button>}
        </div>
      </div>
    </header>
    <div className="house-navigation">
      <nav className="room-nav" aria-label="Espacios de Casa Juan">
        {rooms.map(item => <button key={item.label} aria-current={room === item ? 'page' : undefined}
          onClick={() => navigate(item.screens[0].key)}><item.icon size={17} /><span>{item.label}</span></button>)}
      </nav>
      {room && room.screens.length > 1 && <nav className="room-subnav" aria-label={room.label}>
        {room.screens.map(screen => <button key={screen.key} aria-current={view === screen.key ? 'page' : undefined}
          onClick={() => navigate(screen.key)}>{screen.label}</button>)}
      </nav>}
    </div>
    <main className="content house-content" id="contenido">
      {notice && <div className={notice.error ? 'toast inline-error' : 'toast inline-status'} role="status">
        <span>{notice.text}</span><button className="icon-button" onClick={() => setNotice(null)} aria-label="Cerrar mensaje"><X size={16} /></button>
      </div>}
      {!asset ? <Empty title="El catálogo está vacío" /> : <>
        {view === 'office' && <Office key={symbol + mode} asset={asset} market={currentMarket} replay={report}
          mode={mode} live={live} navigate={navigate} openArchive={() => pick('BTCUSDT')} replayError={replayError} />}
        {view === 'research' && <ResearchView key={symbol} asset={asset} />}
        {view === 'overview' && <Overview catalog={catalog} asset={asset} replay={report} mode={mode} live={live}
          records={report?.records.agente_con_llm ?? records} navigate={navigate} pick={pick} {...marketProps} />}
        {view === 'market' && <MarketView asset={asset} records={records} {...marketProps} />}
        {view === 'scanner' && <Scanner assets={catalog.assets} mode={mode} scan={scan} busy={scanLoading}
          error={mode === 'live' ? scanError : ''} refresh={scanMarket} pick={pick} />}
        {view === 'operations' && <Operations key={symbol + mode} mode={mode} replay={report} asset={asset} config={boot.config}
          live={live} records={records} strategy={strategy} onStrategy={setStrategy} missing={missing} />}
        {view === 'comparison' && <Comparison asset={asset} replay={report} mode={mode}
          useHistorical={() => changeMode('historical')} missing={missing} />}
        {view === 'audit' && <Audit key={symbol + mode + strategy} asset={asset} catalog={catalog} records={records}
          replay={report} mode={mode} strategy={strategy} onStrategy={setStrategy} />}
        {view === 'system' && <SystemView key={symbol} asset={asset} config={boot.config} live={live} replay={report}
          mode={mode} active={busy} scope={scope} setScope={setScope} ready={ready.length} action={control}
          switchLive={() => changeMode('live')} ollamaStatus={ollamaStatus} />}
      </>}
      <footer><span>Juan Fernando Castrejón Villa · Gestión de Bases de Datos</span><span>Proyecto 81901 · UTC · v{catalog.version}</span></footer>
    </main>
  </div>;
}

function App() {
  const [boot, setBoot] = useState<Boot | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    const ctl = new AbortController();
    loadWorkspace(ctl.signal).then(setBoot).catch(failure => {
      if (!ctl.signal.aborted && !isSessionError(failure)) setError((failure as Error).message);
    }).finally(() => { if (!ctl.signal.aborted) setLoading(false); });
    return () => ctl.abort();
  }, []);
  const logout = useCallback(() => { setBoot(null); setError(''); }, []);
  const expired = useCallback(() => { setBoot(null); setError('La sesión expiró. Vuelve a ingresar la clave.'); }, []);
  async function login(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await api('/login', 'POST', { api_key: key });
      setKey('');
      setBoot(await loadWorkspace());
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  if (boot) return <Workspace boot={boot} logout={logout} sessionExpired={expired} />;
  return <main className="login-page">
    <section className="login-brand"><Brand /><p>Simulación de mercado y análisis de decisiones</p></section>
    <section className="login-body">
      <div className="login-card">
        <span className="login-mark">{loading ? <Activity size={25} /> : <LockKeyhole size={24} />}</span>
        <h1>{loading ? 'Abriendo tablero' : preview ? 'Vista histórica' : 'Acceso al laboratorio'}</h1>
        {loading ? <p>Verificando datos y sesión…</p> : preview ? <p className="inline-error">{error}</p> : <>
          <p>Usa la clave generada en el archivo <code>.env</code> del proyecto.</p>
          <form onSubmit={login}><label htmlFor="lab-key">Clave local</label>
            <input id="lab-key" type="password" value={key} onChange={event => setKey(event.target.value)}
              placeholder="PAI_API_KEY" autoComplete="current-password" required />
            {error && <p className="inline-error" role="status">{error}</p>}
            <button className="button primary" type="submit" disabled={busy || !key}>{busy ? 'Ingresando…' : 'Abrir tablero'}<ArrowRight size={17} /></button>
          </form>
        </>}
      </div>
    </section>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
