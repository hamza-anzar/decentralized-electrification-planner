import ReactECharts from "echarts-for-react";

// Thin wrapper so every chart in the app shares the same sizing/loading behavior. `option` is a plain
// ECharts option object built by src/lib/charts.js — this component never contains chart-shaping logic.
export default function EChart({ option, height = 380, loading = false, className = "" }) {
  return (
    <div className={className} style={{ height }}>
      <ReactECharts
        option={option}
        style={{ height: "100%", width: "100%" }}
        notMerge
        lazyUpdate
        showLoading={loading}
        opts={{ renderer: "svg" }}
      />
    </div>
  );
}
