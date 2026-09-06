// Apache ECharts option builders — a JS port of backend/core/charts.py, operating on the JSON row
// arrays the API returns. Kept as plain option-builder functions (not React components) so any page
// can build an option object and hand it straight to <EChart options={...} />.
import { MONTH_NAMES, fmtNumber } from "./format";

export const CATEGORY_COLORS = { A: "#2a78d6", B: "#eb6834", C: "#1baf7a", Misc: "#eda100" };
export const CATEGORIES = ["A", "B", "C", "Misc"];
export const GRIDLINE = "#e7e6e0";
export const AXIS_INK = "#c9c8bd";
export const TEXT_PRIMARY = "#14140f";
export const TEXT_MUTED = "#8b8a80";

const TITLE_STYLE = { fontSize: 15, color: TEXT_PRIMARY, fontWeight: 600, fontFamily: "Manrope, Inter, sans-serif" };
const AXIS_LINE = { lineStyle: { color: AXIS_INK } };
const AXIS_LABEL = { color: TEXT_MUTED, fontFamily: "Inter, sans-serif" };
const SPLIT_LINE = { lineStyle: { color: GRIDLINE } };

export function convertWh(valueWh, unit) {
  const divisors = { kWh: 1_000, MWh: 1_000_000, TWh: 1_000_000_000 };
  return valueWh / divisors[unit];
}

export function loadStats(values, unit) {
  if (!values.length) return { peak: 0, average: 0, total: 0 };
  const sum = values.reduce((a, b) => a + b, 0);
  return {
    peak: convertWh(Math.max(...values), unit),
    average: convertWh(sum / values.length, unit),
    total: convertWh(sum, unit),
  };
}

export function shell(title, xData, xName, yName, legend = true) {
  return {
    title: { text: title, left: "center", textStyle: TITLE_STYLE },
    tooltip: { trigger: "axis" },
    legend: { show: legend, top: 30, textStyle: AXIS_LABEL },
    grid: { left: 55, right: 24, top: legend ? 68 : 48, bottom: 42, containLabel: true },
    toolbox: { feature: { saveAsImage: {} }, right: 8, top: 4, iconStyle: { borderColor: TEXT_MUTED } },
    xAxis: { type: "category", name: xName, nameGap: 26, data: xData, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    yAxis: { type: "value", name: yName, nameGap: 14, splitLine: SPLIT_LINE, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    series: [],
    animationDuration: 500,
  };
}

export function gaugeChart(value, title, { unit = "%", maxValue = 100, color = "#2a78d6" } = {}) {
  return {
    series: [
      {
        type: "gauge",
        min: 0,
        max: maxValue,
        radius: "92%",
        progress: { show: true, width: 14, itemStyle: { color } },
        axisLine: { lineStyle: { width: 14, color: [[1, GRIDLINE]] } },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: { show: true, fontSize: 13, color: TEXT_MUTED, offsetCenter: [0, "72%"], fontFamily: "Inter, sans-serif" },
        detail: {
          valueAnimation: true,
          fontSize: 26,
          fontWeight: 800,
          color: TEXT_PRIMARY,
          fontFamily: "Manrope, sans-serif",
          formatter: `{value}${unit}`,
          offsetCenter: [0, "0%"],
        },
        data: [{ value: Math.round(value * 10) / 10, name: title }],
      },
    ],
  };
}

export function pieChart(title, data, subtitle = "") {
  return {
    title: { text: title, subtext: subtitle, left: "center", top: 4, textStyle: TITLE_STYLE, subtextStyle: { color: TEXT_MUTED } },
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { top: "bottom", textStyle: AXIS_LABEL },
    series: [
      {
        type: "pie",
        radius: ["36%", "62%"],
        center: ["50%", "58%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "#fff", borderWidth: 2 },
        label: { formatter: "{b}\n{d}%", color: TEXT_PRIMARY },
        data,
        animationDuration: 500,
      },
    ],
  };
}

// --- Load Setup ---

export function householdSplitPieChart(categories) {
  const total = categories.reduce((a, c) => a + Number(c.household_count || 0), 0);
  const data = categories.map((c) => ({
    value: Math.round(c.household_count),
    name: `Category ${c.category}`,
    itemStyle: { color: CATEGORY_COLORS[c.category] || TEXT_MUTED },
  }));
  return pieChart("Household Split by Category", data, `Total: ${total.toLocaleString()} houses`);
}

export function connectedLoadByCategoryChart(byCategory) {
  const rows = byCategory.map((r) => ({ ...r, mw: r.connected_load_w_subtotal / 1_000_000 }));
  const total = rows.reduce((a, r) => a + r.mw, 0);
  const data = rows.map((r) => ({
    value: Math.round(r.mw * 10000) / 10000,
    name: `Category ${r.category}`,
    itemStyle: { color: CATEGORY_COLORS[r.category] || TEXT_MUTED },
  }));
  return pieChart("Connected Load by Category", data, `Total: ${total.toFixed(3)} MW`);
}

export function topContributorsChart(lines, topN = 10) {
  const top = [...lines]
    .sort((a, b) => b.connected_load_w - a.connected_load_w)
    .slice(0, topN)
    .map((r) => ({ ...r, mw: r.connected_load_w / 1_000_000, label: `${r.category} — ${r.appliance}` }))
    .sort((a, b) => a.mw - b.mw);

  return {
    title: { text: `Top ${topN} Individual Load Contributors`, left: "center", textStyle: TITLE_STYLE },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 170, right: 40, top: 48, bottom: 42, containLabel: true },
    xAxis: { type: "value", name: "Connected Load (MW)", nameGap: 26, splitLine: SPLIT_LINE, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    yAxis: { type: "category", data: top.map((r) => r.label), axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    series: [
      {
        type: "bar",
        data: top.map((r) => ({ value: Math.round(r.mw * 10000) / 10000, itemStyle: { color: CATEGORY_COLORS[r.category] || TEXT_MUTED } })),
        label: { show: true, position: "right", formatter: "{c}", color: TEXT_MUTED },
      },
    ],
    animationDuration: 500,
  };
}

// --- Demand Profile / Energy Insights ---

function categorySeries(rows, unit, mode = "line", showSymbol = false) {
  return CATEGORIES.filter((cat) => rows[0] && rows[0][`${cat}_wh`] !== undefined).map((cat) => ({
    name: `Category ${cat}`,
    type: mode,
    showSymbol,
    data: rows.map((r) => Math.round(convertWh(r[`${cat}_wh`], unit) * 10000) / 10000),
    lineStyle: { color: CATEGORY_COLORS[cat], width: 2 },
    itemStyle: { color: CATEGORY_COLORS[cat] },
  }));
}

export function hourlyProfileChart(hourlyProfile, day, unit) {
  const rows = hourlyProfile.filter((r) => r.day === day);
  const x = rows.map((_, i) => String(i));
  const dateStr = rows[0]?.date || "";
  const option = shell(`Hourly Load Profile — ${dateStr}`, x, "Hour of day", `Demand (${unit})`);
  option.series = categorySeries(rows, unit, "line", true);
  return option;
}

function groupSum(rows, keyFn, valueKeys) {
  const map = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    if (!map.has(k)) map.set(k, Object.fromEntries(valueKeys.map((vk) => [vk, 0])));
    const acc = map.get(k);
    for (const vk of valueKeys) acc[vk] += r[vk] || 0;
  }
  return map;
}

export function dailyProfileChart(hourlyProfile, unit, month = null) {
  const rows = month ? hourlyProfile.filter((r) => new Date(r.date).getUTCMonth() + 1 === month) : hourlyProfile;
  const valueKeys = CATEGORIES.filter((c) => rows[0] && rows[0][`${c}_wh`] !== undefined).map((c) => `${c}_wh`);
  const map = groupSum(rows, (r) => r.date, valueKeys);
  const dates = [...map.keys()].sort();
  const titleSuffix = month ? ` — ${MONTH_NAMES[month - 1]}` : " — Full Year";
  const option = shell(`Daily Load Profile${titleSuffix}`, dates, "Date", `Daily Demand (${unit})`);
  option.series = valueKeys.map((vk) => {
    const cat = vk.replace("_wh", "");
    return {
      name: `Category ${cat}`,
      type: "line",
      showSymbol: false,
      data: dates.map((d) => Math.round(convertWh(map.get(d)[vk], unit) * 10000) / 10000),
      lineStyle: { color: CATEGORY_COLORS[cat], width: 1.6 },
    };
  });
  return option;
}

export function weeklyProfileChart(hourlyProfile, startDay, unit) {
  const rows = hourlyProfile.filter((r) => r.day >= startDay && r.day < startDay + 7);
  const x = rows.map((r) => String(r.hour_of_year));
  const startDate = rows[0]?.date || "";
  const option = shell(`Weekly Load Profile — starting ${startDate}`, x, "Hour of year", `Demand (${unit})`);
  option.series = categorySeries(rows, unit);
  return option;
}

export function monthlyTotalsChart(hourlyProfile, unit) {
  const valueKeys = CATEGORIES.filter((c) => hourlyProfile[0] && hourlyProfile[0][`${c}_wh`] !== undefined).map((c) => `${c}_wh`);
  const map = groupSum(hourlyProfile, (r) => new Date(r.date).getUTCMonth() + 1, valueKeys);
  const months = [...map.keys()].sort((a, b) => a - b);
  const totals = months.reduce((sum, m) => sum + valueKeys.reduce((s, vk) => s + map.get(m)[vk], 0), 0);
  const option = shell(`Monthly Load Totals — Total ${convertWh(totals, unit).toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`,
    months.map((m) => MONTH_NAMES[m - 1]), "Month", `Monthly Demand (${unit})`);
  option.series = valueKeys.map((vk) => {
    const cat = vk.replace("_wh", "");
    return {
      name: `Category ${cat}`,
      type: "line",
      showSymbol: true,
      symbolSize: 7,
      data: months.map((m) => Math.round(convertWh(map.get(m)[vk], unit) * 10000) / 10000),
      lineStyle: { color: CATEGORY_COLORS[cat], width: 2 },
      itemStyle: { color: CATEGORY_COLORS[cat] },
    };
  });
  return option;
}

export function yearlyOverviewChart(hourlyProfile, unit) {
  const map = groupSum(hourlyProfile, (r) => r.date, ["total_wh"]);
  const dates = [...map.keys()].sort();
  const values = dates.map((d) => convertWh(map.get(d).total_wh, unit));
  const annualTotal = values.reduce((a, b) => a + b, 0);
  const option = shell(`Yearly Load Overview — Annual Total ${annualTotal.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`,
    dates, "Date", `Daily Demand (${unit})`, false);
  option.series = [
    {
      name: "Total demand",
      type: "line",
      showSymbol: false,
      data: values.map((v) => Math.round(v * 10000) / 10000),
      lineStyle: { color: CATEGORY_COLORS.A, width: 2 },
      areaStyle: { color: CATEGORY_COLORS.A, opacity: 0.08 },
    },
  ];
  return option;
}

// Year-by-year projected annual demand: Energy(year n) = Energy(year 1) x (1+g)^(n-1) — shared by
// Demand Setup's own growth-projection card and Energy Insights' "Multi-Year Growth" view.
export function demandGrowthProjectionChart(annualWhYear1, projectStartYear, projectDurationYears, growthPct) {
  const g = growthPct / 100;
  const years = Array.from({ length: projectDurationYears }, (_, i) => projectStartYear + i);
  const gwh = years.map((_, i) => (annualWhYear1 * Math.pow(1 + g, i)) / 1_000_000_000);
  const option = shell(
    `Projected Annual Demand — ${projectStartYear} to ${years[years.length - 1]} (+${growthPct}%/yr)`,
    years.map(String), "Year", "Annual Demand (GWh)", false
  );
  option.series = [
    {
      name: "Projected annual demand",
      type: "line",
      showSymbol: true,
      symbolSize: 5,
      data: gwh.map((v) => Math.round(v * 10000) / 10000),
      lineStyle: { color: CATEGORY_COLORS.A, width: 2 },
      areaStyle: { color: CATEGORY_COLORS.A, opacity: 0.08 },
    },
  ];
  return option;
}

// --- Solar Design ---

export function batterySensitivityChart(sensitivity, selectedKwh, selectedHours) {
  const x = sensitivity.map((r) => String(Math.round(r.battery_kwh)));
  const option = shell("Battery Size vs. Unserved-Demand Hours", x, "Battery Size (kWh)", "Zero-Yield Hours / Year");
  option.series = [
    {
      name: "Zero-yield hours",
      type: "line",
      showSymbol: true,
      symbolSize: 6,
      data: sensitivity.map((r) => r.zero_yield_hours),
      lineStyle: { color: CATEGORY_COLORS.A, width: 2 },
      itemStyle: { color: CATEGORY_COLORS.A },
    },
    {
      name: "Selected size",
      type: "scatter",
      symbolSize: 16,
      data: [[String(Math.round(selectedKwh)), selectedHours]],
      itemStyle: { color: CATEGORY_COLORS.B },
      label: { show: true, formatter: `Selected: ${Math.round(selectedKwh).toLocaleString()} kWh (${selectedHours}h)`, position: "top" },
    },
  ];
  return option;
}

export function egenVsDemandChart(simulation, startDay) {
  const rows = simulation.filter((r) => r.hour_of_year > (startDay - 1) * 24 && r.hour_of_year <= (startDay + 6) * 24);
  const x = rows.map((r) => String(r.hour_of_year));
  return {
    title: { text: "Demand vs. PV Generation vs. Battery SOC (one week)", left: "center", textStyle: TITLE_STYLE },
    tooltip: { trigger: "axis" },
    legend: { top: 30, textStyle: AXIS_LABEL },
    grid: { left: 55, right: 65, top: 68, bottom: 42, containLabel: true },
    xAxis: { type: "category", name: "Hour of year", nameGap: 26, data: x, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    yAxis: [
      { type: "value", name: "Demand / Generation (kWh)", nameGap: 14, splitLine: SPLIT_LINE, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
      { type: "value", name: "Battery SOC (kWh)", nameGap: 14, splitLine: { show: false }, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    ],
    series: [
      { name: "Demand (kWh)", type: "line", showSymbol: false, data: rows.map((r) => Math.round((r.demand_wh / 1000) * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.B, width: 2 } },
      { name: "PV Generation (kWh)", type: "line", showSymbol: false, data: rows.map((r) => Math.round((r.egen_wh / 1000) * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.C, width: 2 } },
      { name: "Battery SOC (kWh)", type: "line", showSymbol: false, yAxisIndex: 1, data: rows.map((r) => Math.round((r.battery_soc_wh / 1000) * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.A, width: 2, type: "dotted" } },
    ],
    animationDuration: 500,
  };
}

export function irradianceVsDemandChart(simulation, startDay, days = 7) {
  const rows = simulation.filter((r) => r.hour_of_year > (startDay - 1) * 24 && r.hour_of_year <= (startDay + days - 1) * 24);
  const x = rows.map((r) => String(r.hour_of_year));
  return {
    title: { text: "Hourly Irradiance vs. Demand Profile", left: "center", textStyle: TITLE_STYLE },
    tooltip: { trigger: "axis" },
    legend: { top: 30, textStyle: AXIS_LABEL },
    grid: { left: 55, right: 65, top: 68, bottom: 42, containLabel: true },
    xAxis: { type: "category", name: "Hour of year", nameGap: 26, data: x, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    yAxis: [
      { type: "value", name: "Demand (kWh)", nameGap: 14, splitLine: SPLIT_LINE, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
      { type: "value", name: "Irradiance (W/m²)", nameGap: 14, splitLine: { show: false }, axisLine: AXIS_LINE, axisLabel: AXIS_LABEL },
    ],
    series: [
      { name: "Demand (kWh)", type: "line", showSymbol: false, data: rows.map((r) => Math.round((r.demand_wh / 1000) * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.B, width: 2 } },
      { name: "Irradiance G(i) (W/m²)", type: "line", showSymbol: false, yAxisIndex: 1, data: rows.map((r) => Math.round(r.ghi_wm2 * 10) / 10), lineStyle: { color: CATEGORY_COLORS.Misc, width: 2, type: "dotted" } },
    ],
    animationDuration: 500,
  };
}

export function duckCurveChart(simulation, day = null) {
  let x, demand, netLoad, title;
  const withNet = simulation.map((r) => ({ ...r, net_load_kwh: (r.demand_wh - r.egen_wh) / 1000 }));

  if (day !== null) {
    const rows = withNet.filter((r) => r.hour_of_year > (day - 1) * 24 && r.hour_of_year <= day * 24);
    x = rows.map((_, i) => String(i));
    demand = rows.map((r) => r.demand_wh / 1000);
    netLoad = rows.map((r) => r.net_load_kwh);
    title = `Duck Curve — Day ${day} of the Year`;
  } else {
    const buckets = Array.from({ length: 24 }, () => ({ demand: 0, net: 0, n: 0 }));
    for (const r of withNet) {
      const h = (r.hour_of_year - 1) % 24;
      buckets[h].demand += r.demand_wh;
      buckets[h].net += r.net_load_kwh;
      buckets[h].n += 1;
    }
    x = buckets.map((_, i) => String(i));
    demand = buckets.map((b) => b.demand / b.n / 1000);
    netLoad = buckets.map((b) => b.net / b.n);
    title = "Duck Curve — Annual Average Daily Shape";
  }

  const option = shell(title, x, "Hour of day", "Load (kWh)");
  option.series = [
    { name: day !== null ? "Demand (kWh)" : "Average Demand (kWh)", type: "line", showSymbol: false, data: demand.map((v) => Math.round(v * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.B, width: 1.5, type: "dotted" } },
    {
      name: day !== null ? "Net Load = Demand − PV Generation (kWh)" : "Average Net Load = Demand − PV Generation (kWh)",
      type: "line", showSymbol: false, data: netLoad.map((v) => Math.round(v * 1000) / 1000),
      lineStyle: { color: CATEGORY_COLORS.A, width: 2.5 },
      markLine: { data: [{ yAxis: 0 }], silent: true, lineStyle: { color: AXIS_INK, type: "dashed" }, label: { show: false } },
    },
  ];
  return option;
}

export function generatorDispatchChart(simulation, startDay) {
  const rows = simulation.filter((r) => r.hour_of_year > (startDay - 1) * 24 && r.hour_of_year <= (startDay + 6) * 24);
  const x = rows.map((r) => String(r.hour_of_year));
  const option = shell("Demand vs. PV Generation vs. Generator Output (one week)", x, "Hour of year", "Energy (kWh)");
  option.series = [
    { name: "Demand (kWh)", type: "line", showSymbol: false, data: rows.map((r) => Math.round((r.demand_wh / 1000) * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.B, width: 2 } },
    { name: "PV Generation (kWh)", type: "line", showSymbol: false, data: rows.map((r) => Math.round((r.egen_wh / 1000) * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.C, width: 2 } },
    { name: "Generator Output (kWh)", type: "line", showSymbol: false, data: rows.map((r) => Math.round((r.generator_output_wh / 1000) * 1000) / 1000), lineStyle: { color: CATEGORY_COLORS.Misc, width: 2, type: "dashed" } },
  ];
  return option;
}

export function deficitLoadDurationChart(loadDurationCurve, installedCapacityKw, recommendedKw) {
  const x = loadDurationCurve.map((r) => String(r.hour_rank));
  const option = shell(
    "Deficit Load Duration Curve — Generator Sizing",
    x, "Hours per year (sorted, worst first)", "PV Shortfall / Required Generator Output (kW)"
  );
  option.series = [
    {
      name: "Hourly deficit (kW)", type: "line", showSymbol: false,
      data: loadDurationCurve.map((r) => Math.round((r.deficit_w / 1000) * 100) / 100),
      lineStyle: { color: CATEGORY_COLORS.B, width: 2 },
      areaStyle: { color: CATEGORY_COLORS.B, opacity: 0.08 },
    },
    {
      name: `Installed capacity (${Math.round(installedCapacityKw).toLocaleString()} kW)`, type: "line", showSymbol: false,
      data: loadDurationCurve.map(() => installedCapacityKw),
      lineStyle: { color: CATEGORY_COLORS.C, width: 2, type: "dashed" },
    },
    {
      name: `Recommended (${Math.round(recommendedKw).toLocaleString()} kW)`, type: "line", showSymbol: false,
      data: loadDurationCurve.map(() => recommendedKw),
      lineStyle: { color: CATEGORY_COLORS.A, width: 1.5, type: "dotted" },
    },
  ];
  return option;
}

// --- Financials ---

export function boqCostBreakdownPieChart(boqItems, currency = "EUR") {
  const rows = boqItems.filter((r) => r.total_cost_eur > 0);
  const total = rows.reduce((a, r) => a + r.total_cost_eur, 0);
  const palette = [CATEGORY_COLORS.A, CATEGORY_COLORS.B, CATEGORY_COLORS.C, CATEGORY_COLORS.Misc, "#7a5cd6", "#d65c9e"];
  const data = rows.map((r, i) => ({ value: Math.round(r.total_cost_eur * 100) / 100, name: r.description, itemStyle: { color: palette[i % palette.length] } }));
  return pieChart("Bill of Quantities — Cost Breakdown", data, `Total: ${total.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${currency}`);
}

// --- Results ---

export function scenarioComparisonBarChart(title, yName, batteryValue, dieselValue, decimals = 2) {
  const option = shell(title, ["Solar + Battery", "Solar + Diesel"], "", yName, false);
  option.series = [
    {
      type: "bar",
      barWidth: "45%",
      data: [
        { value: batteryValue, itemStyle: { color: CATEGORY_COLORS.A } },
        { value: dieselValue, itemStyle: { color: CATEGORY_COLORS.B } },
      ],
      label: { show: true, position: "top", color: TEXT_PRIMARY, formatter: (p) => fmtNumber(p.value, decimals) },
    },
  ];
  return option;
}

export function cumulativeCashflowChart(scenarios) {
  const x = scenarios[0]?.yearly.map((r) => String(r.year)) || [];
  const option = shell("Cumulative Discounted Cash Flow", x, "Project year", "Cumulative discounted cash flow (million EUR)");
  const series = [];
  for (const s of scenarios) {
    series.push({
      name: s.label,
      type: "line",
      showSymbol: false,
      data: s.yearly.map((r) => Math.round((r.cumulative_discounted_eur / 1e6) * 10000) / 10000),
      lineStyle: { color: s.color, width: 2 },
      markLine: { data: [{ yAxis: 0 }], silent: true, lineStyle: { color: AXIS_INK, type: "dashed" }, label: { show: false } },
    });
    if (s.discountedPaybackYears != null) {
      series.push({
        name: `${s.label} payback`,
        type: "scatter",
        symbolSize: 12,
        data: [[String(Math.round(s.discountedPaybackYears)), 0]],
        itemStyle: { color: s.color },
        label: { show: true, formatter: `payback: ${s.discountedPaybackYears.toFixed(1)}y`, position: "top" },
      });
    }
  }
  option.series = series;
  return option;
}
