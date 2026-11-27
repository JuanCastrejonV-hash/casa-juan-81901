import { useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { date, number, price } from './data';
import type { Market, Trade } from './data';

export type Point = { time: number; value: number | null };
export type Curve = { label: string; color: string; points: Point[]; dash?: boolean; fill?: boolean };
type Marker = { time: number; value: number; color: string };
type Plot = { left: number; right: number; top: number; bottom: number; start: number; end: number; min: number; max: number };
const axisLabel = (value: number) => value >= 1000 ? number(value, 0) : price(value);

function preparePlot(width: number, height: number, curves: Curve[], markers: Marker[]): Plot | null {
  const points = curves.flatMap(curve => curve.points).filter(point => typeof point.value === 'number' && Number.isFinite(point.value));
  if (!points.length) return null;
  const start = Math.min(...points.map(point => point.time));
  const end = Math.max(...points.map(point => point.time));
  const values = [...points.map(point => point.value as number), ...markers.filter(mark => mark.time >= start && mark.time <= end).map(mark => mark.value)];
  const min = Math.min(...values), max = Math.max(...values);
  const padding = (max - min || Math.abs(max) * .05 || 1) * .07;
  return { left: width < 380 ? 60 : 72, right: Math.max(80, width - 13), top: 13,
    bottom: height - 30, start, end, min: min - padding, max: max + padding };
}

export function TimeChart({ curves, markers = [], label, precision = price }: {
  curves: Curve[]; markers?: Marker[]; label: string; precision?: (value: number) => string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [hover, setHover] = useState<number | null>(null);
  const { width, height } = size;
  const plot = preparePlot(width, height, curves, markers);
  const focusCurve = curves[0];
  const cursor = hover == null || !plot || !focusCurve ? null : focusCurve.points.reduce<Point | null>((closest, point) =>
    point.value != null && (!closest || Math.abs(hover - point.time) < Math.abs(hover - closest.time)) ? point : closest, null);

  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width: Math.round(width), height: Math.round(height) });
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !plot || width < 100 || height < 90) return;
    const dpi = window.devicePixelRatio || 1;
    canvas.width = width * dpi;
    canvas.height = height * dpi;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpi, dpi);
    const { left, right, top, bottom, start, end, min, max } = plot;
    const px = (time: number) => left + (time - start) / (end - start || 1) * (right - left);
    const py = (value: number) => bottom - (value - min) / (max - min || 1) * (bottom - top);
    ctx.font = '11px ui-monospace, monospace';
    ctx.fillStyle = '#5f7672';
    ctx.strokeStyle = '#e5ece8';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let index = 0; index <= 4; index += 1) {
      const y = top + (bottom - top) * index / 4;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      ctx.fillText(axisLabel(max - (max - min) * index / 4), left - 10, y);
    }
    const ticks = width < 450 ? 2 : 4;
    for (let index = 0; index <= ticks; index += 1) {
      ctx.textAlign = index === 0 ? 'left' : index === ticks ? 'right' : 'center';
      ctx.fillText(date(start + (end - start) * index / ticks, true), left + (right - left) * index / ticks, bottom + 18);
    }
    for (const curve of curves) {
      const points = curve.points.filter(point => typeof point.value === 'number' && Number.isFinite(point.value));
      if (!points.length) continue;
      ctx.beginPath();
      points.forEach((point, index) => {
        if (index) ctx.lineTo(px(point.time), py(point.value as number));
        else ctx.moveTo(px(point.time), py(point.value as number));
      });
      if (curve.fill) {
        ctx.save();
        ctx.lineTo(px(points[points.length - 1].time), bottom);
        ctx.lineTo(px(points[0].time), bottom);
        ctx.closePath();
        const gradient = ctx.createLinearGradient(0, top, 0, bottom);
        gradient.addColorStop(0, curve.color + '28');
        gradient.addColorStop(1, curve.color + '02');
        ctx.fillStyle = gradient;
        ctx.fill();
        ctx.restore();
        ctx.beginPath();
        points.forEach((point, index) => {
          if (index) ctx.lineTo(px(point.time), py(point.value as number));
          else ctx.moveTo(px(point.time), py(point.value as number));
        });
      }
      ctx.strokeStyle = curve.color;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.setLineDash(curve.dash ? [5, 4] : []);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    for (const marker of markers) {
      if (marker.time < start || marker.time > end) continue;
      ctx.fillStyle = marker.color;
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(px(marker.time), py(marker.value), 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
    if (cursor && cursor.value != null) {
      const x = px(cursor.time);
      ctx.strokeStyle = '#91a7a2';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = focusCurve.color;
      ctx.beginPath(); ctx.arc(x, py(cursor.value), 3.5, 0, Math.PI * 2); ctx.fill();
    }
  }, [curves, cursor, focusCurve, height, markers, plot, width]);

  function track(event: PointerEvent<HTMLDivElement>) {
    if (!plot) return;
    const x = event.clientX - event.currentTarget.getBoundingClientRect().left;
    const ratio = Math.min(1, Math.max(0, (x - plot.left) / (plot.right - plot.left)));
    setHover(plot.start + ratio * (plot.end - plot.start));
  }

  return <div className="plot" ref={container} onPointerMove={track} onPointerLeave={() => setHover(null)}>
    <canvas ref={ref} aria-label={label} role="img" />
    {cursor && cursor.value != null && <div className="chart-hover">
      <span>{date(cursor.time)} UTC</span>
      {curves.map(curve => {
        const value = curve.points.find(point => point.time === cursor.time)?.value;
        return value != null && <div key={curve.label}><i style={{ background: curve.color }} />{curve.label}<strong>{precision(value)}</strong></div>;
      })}
    </div>}
  </div>;
}

export function Legend({ entries }: { entries: { label: string; color: string; dash?: boolean }[] }) {
  return <div className="legend">{entries.map(item => <span key={item.label}>
    <i style={{ borderColor: item.color, borderTopStyle: item.dash ? 'dashed' : 'solid' }} />{item.label}
  </span>)}</div>;
}

export function MarketChart({ market, orders }: { market: Market; orders: Trade[] }) {
  const [days, setDays] = useState(90);
  const [average, setAverage] = useState(true);
  const [showOrders, setShowOrders] = useState(true);
  const points = useMemo(() => market.chart.slice(-days), [market.chart, days]);
  const curves: Curve[] = [
    { label: 'Cierre', color: '#167465', fill: true, points: points.map(candle => ({ time: candle.time, value: candle.close })) },
  ];
  if (average) curves.push({ label: 'SMA 20', color: '#a2692c', dash: true,
    points: points.map(candle => ({ time: candle.time, value: candle.sma20 })) });
  const known = orders.filter(order => order.symbol === market.symbol);
  const markers = showOrders ? known.map(order => ({ time: order.fill_ms, value: Number(order.price),
    color: order.side === 'BUY' ? '#13795d' : '#aa4b50' })) : [];
  return <>
    <div className="chart-tools">
      <div className="segments" aria-label="Ventana de precio">{[30, 90, 180].map(value =>
        <button type="button" key={value} aria-pressed={days === value} onClick={() => setDays(value)}>{value} d</button>)}</div>
      <div className="toggles">
        <label><input type="checkbox" checked={average} onChange={event => setAverage(event.target.checked)} /> SMA 20</label>
        {known.length > 0 && <label><input type="checkbox" checked={showOrders} onChange={event => setShowOrders(event.target.checked)} /> Órdenes</label>}
      </div>
    </div>
    <TimeChart curves={curves} markers={markers} label={`Precio en USDT de ${market.symbol}`} />
    <Legend entries={markers.length ? [...curves, { label: 'Compra Paper', color: '#13795d' }, { label: 'Venta Paper', color: '#aa4b50' }] : curves} />
  </>;
}

export function Sparkline({ values }: { values: number[] }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current, ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || values.length < 2) return;
    const min = Math.min(...values), max = Math.max(...values);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 3;
    ctx.strokeStyle = values[values.length - 1] >= values[0] ? '#167465' : '#a94b50';
    ctx.beginPath();
    values.forEach((value, index) => {
      const x = 3 + index / (values.length - 1) * (canvas.width - 6);
      const y = max === min ? canvas.height / 2 : canvas.height - 5 - (value - min) / (max - min) * (canvas.height - 10);
      if (index) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.stroke();
  }, [values]);
  return <canvas ref={ref} width={176} height={51} className="sparkline" role="img" aria-label="Cierres de las últimas 30 velas" />;
}
