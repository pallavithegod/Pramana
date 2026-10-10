/** Chart-role tokens resolved from CSS custom properties at render time, so
 * ECharts (canvas — can't read CSS vars) matches the active theme. */

export interface ChartTheme {
  surface: string;
  ink: string;
  inkSecondary: string;
  inkMuted: string;
  grid: string;
  baseline: string;
  series: string[];
  deEmphasis: string;
  divergeNeg: string;
  divergeMid: string;
  divergePos: string;
  isDark: boolean;
  /** Ordered single-hue ramp (5 steps) for ordinal scales like lead-time
   * buckets — stepped per mode so every step clears contrast on its surface. */
  ordinal: string[];
}

// blue ramp steps (reference palette): light surface may go darker; dark
// surface starts lighter (no darker than step 600) — selected per mode.
const ORDINAL_LIGHT = ["#0d366b", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef"];
const ORDINAL_DARK = ["#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"];

export function readTheme(): ChartTheme {
  const s = getComputedStyle(document.documentElement);
  const v = (name: string) => s.getPropertyValue(name).trim();
  const stamp = document.documentElement.dataset.theme;
  const isDark =
    stamp === "dark" ||
    (!stamp && window.matchMedia("(prefers-color-scheme: dark)").matches);
  return {
    isDark,
    ordinal: isDark ? ORDINAL_DARK : ORDINAL_LIGHT,
    surface: v("--surface"),
    ink: v("--ink"),
    inkSecondary: v("--ink-secondary"),
    inkMuted: v("--ink-muted"),
    grid: v("--grid"),
    baseline: v("--baseline"),
    series: [v("--series-1"), v("--series-2"), v("--series-3"), v("--series-4")],
    deEmphasis: v("--de-emphasis"),
    divergeNeg: v("--diverge-neg"),
    divergeMid: v("--diverge-mid"),
    divergePos: v("--diverge-pos"),
  };
}

/** Shared ECharts scaffolding: recessive grid/axes, our tooltip, no toolbox. */
export function baseOption(t: ChartTheme) {
  return {
    backgroundColor: "transparent",
    textStyle: {
      fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif',
    },
    grid: { left: 48, right: 16, top: 28, bottom: 32, containLabel: false },
    tooltip: {
      backgroundColor: t.surface,
      borderColor: t.grid,
      borderWidth: 1,
      textStyle: { color: t.ink, fontSize: 12 },
      extraCssText: "box-shadow: 0 2px 8px rgba(11,11,11,.12); border-radius: 6px;",
    },
    xAxis: {
      axisLine: { lineStyle: { color: t.baseline } },
      axisTick: { show: false },
      axisLabel: { color: t.inkMuted, fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: t.inkMuted, fontSize: 11 },
      splitLine: { lineStyle: { color: t.grid, width: 1 } },
    },
  };
}
