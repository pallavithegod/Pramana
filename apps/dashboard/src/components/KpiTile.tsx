/** Stat tile per DESIGN.md §4: label → value → delta with colored dot (text
 * stays in ink tokens — color never carries the number). */
export default function KpiTile({
  label,
  value,
  delta,
  deltaTone = "neutral",
  hint,
}: {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "up" | "down" | "neutral";
  hint?: string;
}) {
  const dot =
    deltaTone === "up"
      ? "var(--diverge-pos)"
      : deltaTone === "down"
        ? "var(--diverge-neg)"
        : "var(--ink-muted)";
  return (
    <div className="card px-4 py-3">
      <div className="text-[13px]" style={{ color: "var(--ink-secondary)" }}>
        {label}
      </div>
      <div className="tnum mt-1 text-[28px] leading-8">{value}</div>
      {delta && (
        <div
          className="tnum mt-1 flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ink-secondary)" }}
        >
          <span
            aria-hidden
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: dot }}
          />
          {delta}
        </div>
      )}
      {hint && (
        <div className="mt-1 text-[11px]" style={{ color: "var(--ink-muted)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}
