export type Bar = [time: number, open: number, high: number, low: number, close: number, volume: number];
export type ResearchHistory = { symbol: string; excluded_from_ms: number; sha256: string; bars: Bar[] };
export type Family = 'trend' | 'breakout' | 'momentum' | 'reversion';
export type Filter = 'none' | 'volume' | 'trend';
export type Rule = { family: Family; lookback: number; triggerBps: number; filter: Filter };
export type Costs = { feeBps: number; slipBps: number };
export type Span = { start: number; end: number };
type Point = { time: number; value: number };
type Order = { at: number; side: 'BUY' | 'SELL'; fill: number; units: number; fee: number; reason: string; pnl: number | null };
export type Trial = {
  net: number; drawdown: number; trades: number; winRate: number | null; fees: number;
  exposure: number; points: Point[]; orders: Order[];
};
export type Evaluation = { rule: Rule; score: number; eligible: boolean; validation: Trial[]; trades: number };
export type ResearchRun = {
  origin: string; tested: number; ranked: Evaluation[]; selected: Evaluation | null;
  first: number; last: number; selectionWindows: [number, number][]; costs: Costs;
  strategy: Trial | null; reference: Trial; doubleCosts: Trial | null;
};

export const capital = 50_000;
export const allocation = .10;
export const dayMs = 86_400_000;
export const families: Record<Family, string> = {
  trend: 'Tendencia', breakout: 'Ruptura', momentum: 'Impulso', reversion: 'Reversión',
};
export const filters: Record<Filter, string> = {
  none: 'Sin filtro', volume: 'Volumen relativo', trend: 'Tendencia SMA50',
};

const grids: Record<Family, { lookbacks: number[]; triggers: number[] }> = {
  trend: { lookbacks: [10, 20, 40, 60], triggers: [0, 75, 150] },
  breakout: { lookbacks: [10, 20, 40, 60], triggers: [0, 50, 100] },
  momentum: { lookbacks: [10, 20, 40, 60], triggers: [50, 150, 300] },
  reversion: { lookbacks: [10, 20, 40, 60], triggers: [150, 300, 600] },
};

export function assertRule(rule: Rule) {
  if (!Object.hasOwn(families, rule.family) || !Object.hasOwn(filters, rule.filter) ||
      !Number.isInteger(rule.lookback) || rule.lookback < 5 || rule.lookback > 90 ||
      !Number.isInteger(rule.triggerBps) || rule.triggerBps < 0 || rule.triggerBps > 1000 ||
      (rule.family === 'reversion' && rule.triggerBps === 0)) {
    throw new Error('Usa una familia válida, 5 a 90 velas y un umbral permitido. Reversión requiere un umbral positivo.');
  }
}

export function ruleKey(rule: Rule) {
  return [rule.family, rule.lookback, rule.triggerBps, rule.filter].join('-');
}

export function proposals() {
  const rules: Rule[] = [];
  for (const family of Object.keys(grids) as Family[]) {
    const { lookbacks, triggers } = grids[family];
    for (const lookback of lookbacks) {
      for (const triggerBps of triggers) {
        for (const filter of Object.keys(filters) as Filter[]) {
          rules.push({ family, lookback, triggerBps, filter });
        }
      }
    }
  }
  return rules;
}

function sumSeries(bars: Bar[], index: 4 | 5) {
  const sums = [0];
  for (const bar of bars) sums.push(sums[sums.length - 1] + bar[index]);
  return sums;
}

export function splitHistory(bars: Bar[]) {
  if (bars.length < 600) throw new Error('Se requieren al menos 600 velas diarias.');
  const calibrationEnd = Math.floor(bars.length * .55);
  const evaluationStart = Math.floor(bars.length * .80);
  const validation = Array.from({ length: 3 }, (_, i) => ({
    start: calibrationEnd + Math.floor((evaluationStart - calibrationEnd) * i / 3),
    end: calibrationEnd + Math.floor((evaluationStart - calibrationEnd) * (i + 1) / 3),
  }));
  return { calibrationEnd, validation, evaluation: { start: evaluationStart, end: bars.length } };
}

export function describeRule(rule: Rule) {
  const { lookback, triggerBps, family, filter } = rule;
  const threshold = (triggerBps / 100).toLocaleString('es-MX', { maximumFractionDigits: 2 }) + '%';
  const entries = {
    trend: `Cierre sobre la SMA${lookback} por más de ${threshold}`,
    breakout: `Cierre por encima del máximo de las ${lookback} velas previas más ${threshold}`,
    momentum: `Rendimiento de ${lookback} velas por encima de ${threshold}`,
    reversion: `Cierre al menos ${threshold} debajo de la SMA${lookback}`,
  };
  const exits = {
    trend: `Cierre en o debajo de la SMA${lookback}`,
    breakout: `Cierre en o debajo del mínimo de las ${Math.max(3, Math.floor(lookback / 2))} velas previas`,
    momentum: 'El rendimiento de la ventana llega a cero o cae por debajo',
    reversion: `El cierre alcanza la SMA${lookback}`,
  };
  const gate = filter === 'volume' ? ' y volumen superior a 1.25× su media de 20 velas previas' :
    filter === 'trend' ? ' y cierre en o sobre SMA50' : '';
  return { entry: entries[family] + gate, exit: exits[family] };
}

function prepare(bars: Bar[]) {
  const closeSums = sumSeries(bars, 4);
  const volumeSums = sumSeries(bars, 5);
  const spreads = new Map<number, { top: number[]; bottom: number[] }>();
  const sma = (index: number, lookback: number) =>
    (closeSums[index + 1] - closeSums[index + 1 - lookback]) / lookback;

  function priorEdges(lookback: number) {
    const existing = spreads.get(lookback);
    if (existing) return existing;
    const top: number[] = [], bottom: number[] = [];
    const shorter = Math.max(3, Math.floor(lookback / 2));
    for (let i = lookback; i < bars.length; i++) {
      let high = -Infinity, low = Infinity;
      for (let j = i - lookback; j < i; j++) high = Math.max(high, bars[j][2]);
      for (let j = i - shorter; j < i; j++) low = Math.min(low, bars[j][3]);
      top[i] = high;
      bottom[i] = low;
    }
    const edges = { top, bottom };
    spreads.set(lookback, edges);
    return edges;
  }

  return function signal(rule: Rule, index: number, hasPosition: boolean) {
    const window = rule.lookback, close = bars[index][4], threshold = rule.triggerBps / 10_000;
    if (index < Math.max(window, 50)) return false;
    if (!hasPosition && rule.filter === 'trend' && close < sma(index, 50)) return false;
    if (!hasPosition && rule.filter === 'volume' &&
        bars[index][5] <= 1.25 * (volumeSums[index] - volumeSums[index - 20]) / 20) return false;
    switch (rule.family) {
      case 'breakout': {
        const { top, bottom } = priorEdges(window);
        return hasPosition ? close > bottom[index] : close > top[index] * (1 + threshold);
      }
      case 'momentum': {
        const returns = close / bars[index - window][4] - 1;
        return returns > (hasPosition ? 0 : threshold);
      }
      case 'reversion': {
        const distance = close / sma(index, window) - 1;
        return hasPosition ? distance < 0 : distance <= -threshold;
      }
      case 'trend':
        return close > sma(index, window) * (hasPosition ? 1 : 1 + threshold);
    }
  };
}

type Signal = ReturnType<typeof prepare>;

export function backtest(bars: Bar[], span: Span, costs: Costs, rule: Rule | null, collect = true, signal = prepare(bars)): Trial {
  const commission = costs.feeBps / 10_000, slip = costs.slipBps / 10_000;
  let cash = capital, units = 0, basis = 0, top = capital, drawdown = 0;
  let fees = 0, wins = 0, trades = 0, investedBars = 0, equity = capital;
  const points: Point[] = collect ? [{ time: bars[span.start][0] - 1, value: capital }] : [];
  const orders: Order[] = [];

  function fill(side: 'BUY' | 'SELL', at: number, price: number, reason: string) {
    const execution = price * (1 + (side === 'BUY' ? slip : -slip));
    if (side === 'BUY') {
      const available = Math.min(cash, cash * allocation);
      units = available / (execution * (1 + commission));
      const fee = units * execution * commission;
      basis = units * execution + fee;
      cash -= basis;
      fees += fee;
      if (collect) orders.push({ at, side, fill: execution, units, fee, pnl: null, reason });
    } else {
      const fee = units * execution * commission, proceeds = units * execution - fee;
      const pnl = proceeds - basis;
      cash += proceeds;
      fees += fee;
      trades++;
      if (pnl > 0) wins++;
      if (collect) orders.push({ at, side, fill: execution, units, fee, pnl, reason });
      units = 0;
      basis = 0;
    }
  }

  for (let index = span.start; index < span.end; index++) {
    const [time, opening, , , closing] = bars[index];
    const last = index === span.end - 1;
    // Today's decision was available at the preceding candle close.
    const hold = rule ? signal(rule, index - 1, units > 0) : true;
    if (units && !hold) fill('SELL', time, opening, 'Regla de salida al cierre previo');
    if (!units && hold && !last) fill('BUY', time, opening, rule ? 'Señal al cierre previo' : 'Inicio de la referencia pasiva');
    if (units) investedBars++;
    if (units && last) fill('SELL', time + dayMs - 1, closing, 'Liquidación al cierre del tramo');
    equity = cash + units * closing;
    top = Math.max(top, equity);
    drawdown = Math.max(drawdown, (top - equity) / top);
    if (collect) points.push({ time: time + dayMs - 1, value: equity });
  }
  return { net: equity / capital - 1, drawdown, trades, winRate: trades ? wins / trades : null, fees,
    exposure: investedBars / (span.end - span.start), points, orders };
}

export function rankRule(bars: Bar[], validation: Span[], costs: Costs, rule: Rule, signal: Signal): Evaluation {
  const results = validation.map(span => backtest(bars, span, costs, rule, false, signal));
  const values = results.map(trial => trial.net - trial.drawdown).sort((a, b) => a - b);
  const trades = results.reduce((sum, trial) => sum + trial.trades, 0);
  return { rule, validation: results, score: values[1], trades,
    eligible: trades >= 3 && results.filter(result => result.trades > 0).length >= 2 };
}

export async function researchRun(history: ResearchHistory, candidates: Rule[], costs: Costs, origin: string,
  onProgress: (evaluated: number, total: number) => void, signal?: AbortSignal, manual = false): Promise<ResearchRun> {
  if (!Number.isFinite(costs.feeBps) || costs.feeBps < 0 || costs.feeBps > 100 ||
      !Number.isFinite(costs.slipBps) || costs.slipBps < 0 || costs.slipBps > 100) {
    throw new Error('Comisión y deslizamiento deben quedar entre 0 y 100 pb.');
  }
  candidates.forEach(assertRule);
  const unique = Array.from(new Map(candidates.map(rule => [ruleKey(rule), rule])).values());
  if (!unique.length) throw new Error('El investigador necesita al menos una regla.');
  const { bars } = history;
  const { validation, evaluation } = splitHistory(bars);
  const predict = prepare(bars);
  const ranked: Evaluation[] = [];
  onProgress(0, unique.length);
  for (let i = 0; i < unique.length; i++) {
    signal?.throwIfAborted();
    if (i % 12 === 0) await new Promise<void>(resolve => setTimeout(resolve, 0));
    ranked.push(rankRule(bars, validation, costs, unique[i], predict));
    if ((i + 1) % 12 === 0 || i === unique.length - 1) onProgress(i + 1, unique.length);
  }
  signal?.throwIfAborted();
  ranked.sort((a, b) => Number(b.eligible) - Number(a.eligible) || b.score - a.score ||
    ruleKey(a.rule).localeCompare(ruleKey(b.rule)));
  const selected = manual ? ranked[0] : ranked.find(row => row.eligible) ?? null;
  const rule = selected?.rule;
  const strategy = rule ? backtest(bars, evaluation, costs, rule, true, predict) : null;
  const reference = backtest(bars, evaluation, costs, null, true, predict);
  const stressed = { feeBps: costs.feeBps * 2, slipBps: costs.slipBps * 2 };
  return { origin, tested: unique.length, ranked, selected, costs,
    strategy, reference, doubleCosts: rule ? backtest(bars, evaluation, stressed, rule, false, predict) : null,
    first: bars[evaluation.start][0], last: bars[evaluation.end - 1][0],
    selectionWindows: validation.map(span => [bars[span.start][0], bars[span.end - 1][0]]),
  };
}
