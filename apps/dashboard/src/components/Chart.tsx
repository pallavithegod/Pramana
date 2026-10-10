"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { readTheme, type ChartTheme } from "@/lib/theme";

/** Single ECharts entry point (DESIGN.md §8): every chart inherits theme roles,
 * tooltip styling and the no-toolbox rule from here — grammar by construction. */
export default function Chart({
  build,
  height = 320,
  onClick,
}: {
  /** Returns an ECharts option object; typed loosely because ECharts' strict
   * formatter types reject our narrowed callback params. */
  build: (t: ChartTheme) => object;
  height?: number;
  onClick?: (params: echarts.ECElementEvent) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chartRef.current = chart;
    const render = () => chart.setOption(build(readTheme()) as echarts.EChartsOption, true);
    render();
    if (onClick) chart.on("click", (p) => onClick(p as echarts.ECElementEvent));

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    const mo = new MutationObserver(render); // re-theme on data-theme flips
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", render);
    return () => {
      ro.disconnect();
      mo.disconnect();
      mq.removeEventListener("change", render);
      chart.dispose();
    };
  }, [build, onClick]);

  return <div ref={ref} style={{ height, width: "100%" }} />;
}
