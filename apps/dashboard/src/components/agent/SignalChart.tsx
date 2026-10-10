import type { Signal } from "@/lib/chat";
export default function SignalChart({ signal }: { signal: Signal }) {
  const points = (signal.trajectory ?? []).filter(p => Number.isFinite(p.raw) && Number.isFinite(p.baseline) && Number.isFinite(p.variance) && p.variance >= 0);
  if (points.length < 3) return <div className="chart-fallback"><span className="snapshot-badge">Snapshot Mode: Cached Economic Observations</span><div><span>OBSERVATION HISTORY</span><b>{points.length || signal.n_observations}</b></div>{signal.smoothed_baseline != null ? <div className="baseline-meter"><span>BASELINE</span><strong>{signal.currency} {signal.smoothed_baseline.toFixed(2)}</strong><i/></div> : <p>Trajectory requires at least three valid observations. The measured coverage and saved signal summary remain available.</p>}{signal.band_low != null && signal.band_high != null && <div className="band-summary"><span>95% CONDITIONAL BAND</span><b>{signal.currency} {signal.band_low.toFixed(2)} — {signal.band_high.toFixed(2)}</b></div>}</div>;
  const width = 560, height = 188, pad = 28;
  const low = points.map(p => p.baseline - 1.96 * Math.sqrt(p.variance));
  const high = points.map(p => p.baseline + 1.96 * Math.sqrt(p.variance));
  const min = Math.min(...points.map(p => p.raw), ...low), max = Math.max(...points.map(p => p.raw), ...high), span = Math.max(max - min, 1e-6);
  const x = (i: number) => pad + i * (width - 2 * pad) / (points.length - 1), y = (v: number) => height - pad - (v - min) * (height - 2 * pad) / span;
  const line = (values: number[]) => values.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
  const band = high.map((v, i) => `${x(i)},${y(v)}`).concat(low.map((v, i) => `${x(i)},${y(v)}`).reverse()).join(" ");
  return <figure className="signal-chart"><div className="chart-legend"><span><i className="legend-raw"/>Raw observations</span><span><i className="legend-base"/>PRISM baseline</span><span><i className="legend-band"/>95% conditional band</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Observed prices and filtered baseline for ${signal.title ?? signal.product_id}; shaded conditional model bands`}>
      <text x={pad} y="13" className="chart-axis-label">{signal.currency} {max.toFixed(2)}</text><text x={pad} y={height - 4} className="chart-axis-label">{signal.currency} {min.toFixed(2)}</text>
      {[.25, .5, .75].map(f => <line key={f} x1={pad} x2={width - pad} y1={y(min + f * span)} y2={y(min + f * span)} className="chart-gridline"/>)}
      <polygon points={band} className="chart-band"/><path d={line(points.map(p => p.raw))} className="chart-raw"/><path d={line(points.map(p => p.baseline))} className="chart-baseline"/>
      {points.map((point, i) => <circle key={i} cx={x(i)} cy={y(point.raw)} r="3.2" className="chart-point"><title>{point.observed_at}: {signal.currency} {point.raw.toFixed(2)} raw; {point.baseline.toFixed(2)} baseline</title></circle>)}
    </svg><figcaption>{points[0].observed_at.slice(0, 10)} → {points[points.length - 1].observed_at.slice(0, 10)} <span>· observation steps, not equal calendar intervals</span></figcaption>
  </figure>;
}
