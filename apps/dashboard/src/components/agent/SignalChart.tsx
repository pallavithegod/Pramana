import type { Signal } from "@/lib/chat";
export default function SignalChart({ signal }: {
    signal: Signal;
}) {
    const points = signal.trajectory ?? [];
    if (points.length < 3)
        return null;
    const width = 560, height = 170, pad = 20;
    const low = points.map(p => p.baseline - 1.96 * Math.sqrt(p.variance));
    const high = points.map(p => p.baseline + 1.96 * Math.sqrt(p.variance));
    const min = Math.min(...points.map(p => p.raw), ...low);
    const max = Math.max(...points.map(p => p.raw), ...high);
    const span = Math.max(max - min, 1e-6);
    const x = (index: number) => pad + index * (width - 2 * pad) / (points.length - 1);
    const y = (value: number) => height - pad - (value - min) * (height - 2 * pad) / span;
    const line = (values: number[]) => values.map((value, i) => `${i ? "L" : "M"}${x(i)},${y(value)}`).join(" ");
    const band = high.map((value, i) => `${x(i)},${y(value)}`).concat(low.map((value, i) => `${x(i)},${y(value)}`).reverse()).join(" ");
    return <figure className="signal-chart"><div className="chart-legend"><span>● Raw price</span><span>● PRISM baseline</span><span>▰ Conditional 95% band</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Observed prices and filtered baseline for ${signal.title ?? signal.product_id}; shaded conditional model bands`}>
      <text x={pad} y="12" fontSize="8" fill="#70808e">{signal.currency} {max.toFixed(2)}</text>
      <text x={pad} y={height - 3} fontSize="8" fill="#70808e">{signal.currency} {min.toFixed(2)}</text>
      {[.25, .5, .75].map(f => <line key={f} x1={pad} x2={width - pad} y1={y(min + f * span)} y2={y(min + f * span)} stroke="#e1e7e9" strokeDasharray="3 5"/>)}
      <polygon points={band} fill="#087f69" opacity=".10"/>
      <path d={line(points.map(p => p.raw))} fill="none" stroke="#8c9daa" strokeWidth="1.5"/>
      <path d={line(points.map(p => p.baseline))} fill="none" stroke="#087f69" strokeWidth="2.5"/>
      {points.map((point, i) => <circle key={i} cx={x(i)} cy={y(point.raw)} r="3" fill="#8c9daa"><title>{point.observed_at}: {signal.currency} {point.raw.toFixed(2)} raw; {point.baseline.toFixed(2)} baseline</title></circle>)}
    </svg><figcaption>{points[0].observed_at.slice(0, 10)} → {points[points.length - 1].observed_at.slice(0, 10)} · observation steps, not equal calendar intervals</figcaption>
  </figure>;
}
