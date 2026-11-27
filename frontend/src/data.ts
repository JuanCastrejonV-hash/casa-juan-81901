export type Mode = 'historical' | 'live';
export type Strategy = 'agente_con_llm' | 'modelo_sin_llm' | 'comprar_y_mantener';
export type View = 'office' | 'research' | 'overview' | 'market' | 'scanner' | 'operations' | 'comparison' | 'audit' | 'system';
export type SectionChange = (view: View) => void;

export const strategies = {
  agente_con_llm: { label: 'Con Ollama', color: '#167465' },
  modelo_sin_llm: { label: 'Modelo solo', color: '#5a65a7' },
  comprar_y_mantener: { label: 'Comprar y mantener', color: '#a2692c' },
} satisfies Record<Strategy, { label: string; color: string }>;
export const strategyKeys = Object.keys(strategies) as Strategy[];

export type Candle = {
  time: number; open_time: number; open: number; high: number; low: number; close: number; sma20: number | null;
};
export type Forecast = {
  value: number; threshold: number; technical_filter: boolean; signal: boolean; issue_ms: number; target_ms: number;
};
export type Market = {
  symbol: string; source: Mode; close: number; close_ms: number; change: number; sma20: number;
  dist_sma20: number; vol20: number; count: number; observed_ms: number | null; forecast: Forecast | null;
  chart: Candle[]; model_message?: string | null;
};
export type Model = {
  experiment: string; version: string; features: string[]; lookback: number; seed: number; device: string;
  threshold: number; technical_filter: boolean; data_sha256: string; model_sha256: string; scalers_sha256: string;
  evaluated_at: string | null; inference_error: number | null;
  metrics: { modelo: string; conjunto: string; n: number; mae: number; rmse: number; acierto_direccional: number }[];
  partitions: { conjunto: string; n: number; primer_objetivo: string; ultimo_objetivo: string }[];
};
export type Asset = {
  symbol: string; base: string; name: string; status: 'ready' | 'pending'; message: string | null;
  model: Model | null; history: Market | null; replay_cycles: number | null;
  replay_status: 'available' | 'interrupted' | 'missing';
};
export type Catalog = {
  assets: Asset[]; version: string;
  verification: {
    tests: { tests: number; errors: number; failures: number; skipped: number } | null;
    notebook_url: string | null; colab_files: number | null; max_prediction_error: number | null;
  };
};
export type Account = {
  cash: number; equity: number; exposure: number; initial: number; status: string;
  positions: { symbol: string; qty: number; price: number; value: number; cost_basis: number; mark_ms: number }[];
};
export type Decision = {
  id: number; symbol: string; close_ms: number; action: string; reason: string; forecast: number;
  risk: string; executed: number; llm_ms: number; mode: string;
};
export type Trade = {
  id: number; decision_id?: number; symbol: string; side: string; qty: number | string; price: number | string; fee: number | string;
  fill_ms: number; pnl: number | string | null; forced: number;
};
export type Event = { id: number; created_at: string; stage: string; code: string; message: string; symbol: string | null };
export type Equity = { event_ms: number; equity: number; cash: number; exposure: number };
export type TradingRecords = { decisions: Decision[]; orders: Trade[]; events: Event[]; equity: Equity[] };
export type State = TradingRecords & {
  account: Account; active_symbols: string[]; daily_equity: number; daily_day: string | null;
};
export type ComparisonRow = {
  estrategia: Strategy; patrimonio_final: number; rendimiento_neto: number; max_drawdown: number;
  operaciones_cerradas: number; win_rate: number | null; costos: number; latencia_llm_ms_media: number | null;
  acciones_rechazadas: number; ciclos: number;
};
export type Replay = {
  symbol: string; first_issue: string; last_target: string; cycles: number; initial_cash: number;
  fee: number; slippage_bps: number; passive_allocation: number; comparison: ComparisonRow[];
  records: Record<Strategy, TradingRecords>; inference_error: number | null;
  llm: { model: string | null; ollama_version: string | null; processor: string | null; local: boolean | null; digest: string | null };
};
export type LiveScan = {
  updated_ms: number;
  rows: { symbol: string; market: Market | null; error: string | null; latency_ms: number | null }[];
};
export type Config = {
  interval: string; ollama_model: string;
  risk: {
    initial_cash: number; fee: number; max_total_exposure: number; max_asset_exposure: number;
    daily_loss_limit: number; max_data_age_hours: number; slippage_bps: number; poll_seconds: number;
  };
};
export type Job = { id: string; status: 'running' | 'completed' | 'failed'; symbol: string; error?: string };

declare global {
  interface Window { __PAI_ARCHIVE__?: Record<string, unknown> }
}

const archive = window.__PAI_ARCHIVE__;
export const preview = archive !== undefined;

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function api<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  if (archive) {
    if (method === 'GET' && Object.hasOwn(archive, path)) return archive[path] as T;
    throw new ApiError('Abre la aplicación local para usar esta función.', 404);
  }
  const response = await fetch('/api' + path, {
    method, signal, credentials: 'same-origin', headers: {
      'Content-Type': 'application/json', 'X-Requested-With': 'PAI',
    }, body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(typeof data?.detail === 'string' ? data.detail : 'No se pudo completar la solicitud.', response.status);
  }
  return data as T;
}

const locale = 'es-MX';
const day = new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
const shortDay = new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', timeZone: 'UTC' });
const timestamp = new Intl.DateTimeFormat(locale, {
  day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC',
});
function parsedDate(value: string | number) {
  return new Date(typeof value === 'string' ? value.replace(' ', 'T') : value);
}
export function date(value?: string | number | null, compact = false) {
  if (value == null) return '—';
  const parsed = parsedDate(value);
  return Number.isNaN(parsed.valueOf()) ? '—' : (compact ? shortDay : day).format(parsed);
}
export function dateTime(value?: string | number | null) {
  if (value == null) return '—';
  const parsed = parsedDate(value);
  return Number.isNaN(parsed.valueOf()) ? '—' : timestamp.format(parsed) + ' UTC';
}
export const number = (value: number, digits = 2) => new Intl.NumberFormat(locale, {
  minimumFractionDigits: digits, maximumFractionDigits: digits,
}).format(value);
export const price = (value: number) => number(value, value < 1 ? 5 : 2);
export const pct = (value: number, digits = 2, signed = true) =>
  (signed && value > 0 ? '+' : '') + number(value * 100, digits) + '%';
export const moveClass = (value: number) => value < 0 ? 'loss' : value > 0 ? 'gain' : 'muted';
export const actionName = (value: string) => ({ BUY: 'Comprar', SELL: 'Vender', HOLD: 'Mantener' })[value] ?? value;
export const statusName = (value: string) => ({ running: 'En marcha', stopped: 'Detenido', paused: 'En pausa' })[value] ?? value;
export const riskName = (value: string) => ({
  OK: 'Aprobada', ALREADY_LONG: 'Posición ya abierta', DAILY_LOSS: 'Límite diario', DAILY_LOSS_LIMIT: 'Límite diario',
  EXPOSURE_LIMIT: 'Límite de exposición', MODEL_SIGNAL: 'Fuera de la señal', NO_POSITION: 'Sin posición',
  INSUFFICIENT_BALANCE: 'Saldo insuficiente', NOTIONAL_MIN: 'Monto mínimo', DUPLICATE: 'Vela repetida',
  STOPPED: 'Agente detenido', PAUSED: 'Agente en pausa', AUTH_DENIED: 'Acceso denegado',
  RECOVERED: 'Estado recuperado', EXPLICIT_LIQUIDATION: 'Liquidación de cierre',
})[value] ?? value;

export const replayPeriod = (r: Replay) => `${date(r.first_issue, true)} – ${date(r.last_target)} UTC`;
export const replayStats = (r: Replay | null, key: Strategy) => r?.comparison.find(row => row.estrategia === key);
export const emptyRecords: TradingRecords = { decisions: [], orders: [], equity: [], events: [] };

export function downloadReplay(replay: Replay, kind: keyof TradingRecords | 'comparison', strategy: Strategy) {
  if (!preview) {
    const link = document.createElement('a');
    link.href = `/api/lab/replay/${replay.symbol}/download/${kind}?strategy=${strategy}`;
    link.click();
    return;
  }
  const rows = (kind === 'comparison' ? replay.comparison : replay.records[strategy][kind]) as object[];
  const fields = rows.length ? Object.keys(rows[0]) : [];
  const cell = (value: unknown) => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  const data = [fields.join(','), ...rows.map(row => fields.map(key => cell((row as Record<string, unknown>)[key])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([data], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `${replay.symbol}_${kind === 'comparison' ? 'comparacion' : strategy + '_' + kind}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 500);
}
