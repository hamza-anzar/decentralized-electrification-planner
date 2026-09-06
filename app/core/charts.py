"""Interactive Apache ECharts option builders for the app (rendered via streamlit-echarts' st_echarts),
replacing the earlier Plotly charts per the user's request. Every builder returns a plain ECharts
"option" dict — nothing here touches Streamlit directly, so pages just do:

    from streamlit_echarts import st_echarts
    st_echarts(options=charts.some_chart(...), height="420px")

All charts are keyed off the same validated CATEGORY_COLORS palette so a category or scenario never
gets a different color from one chart to the next. Categorical breakdowns (household split, connected
load by category, BOQ cost breakdown) render as donut/pie charts with % labels; time-series profiles
(hourly/daily/weekly/monthly/annual demand, PV generation, cash flow) render as line charts; headline
single-number "how full/how good" figures (capacity factor, ROI) render as round gauge charts — all per
the user's ask for "graphs, pie charts, % charts, round charts".
"""
import pandas as pd

from .style import CATEGORY_COLORS, GRIDLINE, AXIS_INK, TEXT_PRIMARY, TEXT_MUTED

CATEGORIES = ["A", "B", "C", "Misc"]

_TITLE_STYLE = {"fontSize": 15, "color": TEXT_PRIMARY, "fontWeight": 600}
_AXIS_LINE = {"lineStyle": {"color": AXIS_INK}}
_AXIS_LABEL = {"color": TEXT_MUTED}
_SPLIT_LINE = {"lineStyle": {"color": GRIDLINE}}


def _shell(title: str, x_data=None, x_name: str = "", y_name: str = "", legend: bool = True) -> dict:
    """Common option skeleton for a single-y-axis category-x-axis chart (line/bar)."""
    return {
        "title": {"text": title, "left": "center", "textStyle": _TITLE_STYLE},
        "tooltip": {"trigger": "axis"},
        "legend": {"show": legend, "top": 30, "textStyle": _AXIS_LABEL},
        "grid": {"left": 55, "right": 30, "top": 70 if legend else 50, "bottom": 45, "containLabel": True},
        "toolbox": {"feature": {"saveAsImage": {}}, "right": 10, "top": 5},
        "xAxis": {"type": "category", "name": x_name, "nameGap": 28, "data": x_data or [],
                  "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "yAxis": {"type": "value", "name": y_name, "nameGap": 14, "splitLine": _SPLIT_LINE,
                  "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "series": [],
    }


def convert_wh(value_wh, unit: str):
    """Convert a Wh value (scalar, Series, or array) to the requested display unit: kWh, MWh, or TWh."""
    divisors = {"kWh": 1_000, "MWh": 1_000_000, "TWh": 1_000_000_000}
    return value_wh / divisors[unit]


def load_stats(series_wh: pd.Series, unit: str) -> dict:
    """Peak / average / total for a Wh series, converted to the requested display unit — used to show
    'peak load, average load, etc.' underneath every profile chart."""
    if len(series_wh) == 0:
        return {"peak": 0.0, "average": 0.0, "total": 0.0}
    return {
        "peak": float(convert_wh(series_wh.max(), unit)),
        "average": float(convert_wh(series_wh.mean(), unit)),
        "total": float(convert_wh(series_wh.sum(), unit)),
    }


def gauge_chart(value: float, title: str, unit: str = "%", max_value: float = 100, color: str = None) -> dict:
    """A round gauge chart for one headline "how full / how good" figure."""
    color = color or CATEGORY_COLORS["A"]
    return {
        "series": [{
            "type": "gauge", "min": 0, "max": max_value, "radius": "90%",
            "progress": {"show": True, "width": 14, "itemStyle": {"color": color}},
            "axisLine": {"lineStyle": {"width": 14, "color": [[1, GRIDLINE]]}},
            "pointer": {"show": False},
            "axisTick": {"show": False}, "splitLine": {"show": False}, "axisLabel": {"show": False},
            "title": {"show": True, "fontSize": 13, "color": TEXT_MUTED, "offsetCenter": [0, "72%"]},
            "detail": {"valueAnimation": True, "fontSize": 24, "fontWeight": 700, "color": TEXT_PRIMARY,
                       "formatter": "{value}" + unit, "offsetCenter": [0, "0%"]},
            "data": [{"value": round(value, 1), "name": title}],
        }],
    }


def pie_chart(title: str, data: list, subtitle: str = "") -> dict:
    """Generic donut pie chart. `data` is a list of {"value": float, "name": str, "itemStyle": {"color": hex}}."""
    return {
        "title": {"text": title, "subtext": subtitle, "left": "center", "textStyle": _TITLE_STYLE,
                   "subtextStyle": {"color": TEXT_MUTED}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"top": "bottom", "textStyle": _AXIS_LABEL},
        "series": [{
            "type": "pie", "radius": ["38%", "68%"], "center": ["50%", "52%"], "avoidLabelOverlap": True,
            "itemStyle": {"borderColor": "#fff", "borderWidth": 2},
            "label": {"formatter": "{b}\n{d}%", "color": TEXT_PRIMARY},
            "data": data,
        }],
    }


# --- Step 1 (Load Setup): Connected load ---

def household_split_pie_chart(household_categories_df: pd.DataFrame) -> dict:
    total = int(household_categories_df["household_count"].sum())
    data = [
        {"value": int(row["household_count"]), "name": f"Category {row['category']}",
         "itemStyle": {"color": CATEGORY_COLORS.get(row["category"], TEXT_MUTED)}}
        for _, row in household_categories_df.iterrows()
    ]
    return pie_chart("Household Split by Category", data, subtitle=f"Total: {total:,} houses")


def connected_load_by_category_chart(by_category_df: pd.DataFrame) -> dict:
    df = by_category_df.copy()
    df["mw"] = df["connected_load_w_subtotal"] / 1_000_000
    total_mw = df["mw"].sum()
    data = [
        {"value": round(row["mw"], 4), "name": f"Category {row['category']}",
         "itemStyle": {"color": CATEGORY_COLORS.get(row["category"], TEXT_MUTED)}}
        for _, row in df.iterrows()
    ]
    return pie_chart("Connected Load by Category", data, subtitle=f"Total: {total_mw:.3f} MW")


def top_contributors_chart(lines_df: pd.DataFrame, top_n: int = 10) -> dict:
    top = lines_df.nlargest(top_n, "connected_load_w").copy()
    top["mw"] = top["connected_load_w"] / 1_000_000
    top["label"] = top["category"] + " — " + top["appliance"]
    top = top.sort_values("mw")
    colors = [CATEGORY_COLORS.get(c, TEXT_MUTED) for c in top["category"]]

    return {
        "title": {"text": f"Top {top_n} Individual Load Contributors", "left": "center", "textStyle": _TITLE_STYLE},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 160, "right": 40, "top": 50, "bottom": 45, "containLabel": True},
        "xAxis": {"type": "value", "name": "Connected Load (MW)", "nameGap": 28, "splitLine": _SPLIT_LINE,
                  "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "yAxis": {"type": "category", "data": top["label"].tolist(), "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "series": [{
            "type": "bar", "data": [{"value": round(v, 4), "itemStyle": {"color": c}} for v, c in zip(top["mw"], colors)],
            "label": {"show": True, "position": "right", "formatter": "{c}", "color": TEXT_MUTED},
        }],
    }


# --- Step 2/3 (Demand Profile / Energy Insights): hourly / daily / weekly / monthly / annual ---

def _category_line_series(df: pd.DataFrame, unit: str, mode: str = "line", show_symbol: bool = False) -> list:
    series = []
    for cat in CATEGORIES:
        col = f"{cat}_wh"
        if col not in df.columns:
            continue
        series.append({
            "name": f"Category {cat}", "type": mode, "showSymbol": show_symbol,
            "data": [round(v, 4) for v in convert_wh(df[col].values, unit)],
            "lineStyle": {"color": CATEGORY_COLORS[cat], "width": 2},
            "itemStyle": {"color": CATEGORY_COLORS[cat]},
        })
    return series


def hourly_profile_chart(hourly_profile_df: pd.DataFrame, day: int, unit: str) -> dict:
    """One day's 24-hour profile, by category — the finest granularity view."""
    window = hourly_profile_df[hourly_profile_df["day"] == day].copy()
    x = [str(h) for h in range(len(window))]
    date_str = window["date"].iloc[0] if len(window) else ""
    option = _shell(f"Hourly Load Profile — {date_str}", x, "Hour of day", f"Demand ({unit})")
    option["series"] = _category_line_series(window, unit, show_symbol=True)
    return option


def daily_profile_chart(hourly_profile_df: pd.DataFrame, unit: str, month: int = None) -> dict:
    """Day-by-day totals, by category — full year by default, or one month if `month` is given."""
    df = hourly_profile_df.copy()
    df["date_dt"] = pd.to_datetime(df["date"])
    if month is not None:
        df = df[df["date_dt"].dt.month == month]
    daily = df.groupby("date_dt")[[f"{c}_wh" for c in CATEGORIES if f"{c}_wh" in df.columns]].sum()
    x = daily.index.astype(str).tolist()
    title_suffix = f" — {pd.Timestamp(2026, month, 1).strftime('%B')}" if month else " — Full Year"
    option = _shell(f"Daily Load Profile{title_suffix}", x, "Date", f"Daily Demand ({unit})")
    option["series"] = _category_line_series(daily, unit)
    return option


def weekly_profile_chart(hourly_profile_df: pd.DataFrame, start_day: int, unit: str) -> dict:
    """168-hour window starting at `start_day` (1-365), by category."""
    window = hourly_profile_df[(hourly_profile_df["day"] >= start_day) & (hourly_profile_df["day"] < start_day + 7)].copy()
    x = [str(h) for h in window["hour_of_year"]]
    start_date = window["date"].iloc[0] if len(window) else ""
    option = _shell(f"Weekly Load Profile — starting {start_date}", x, "Hour of year", f"Demand ({unit})")
    option["series"] = _category_line_series(window, unit)
    return option


def monthly_totals_chart(hourly_profile_df: pd.DataFrame, unit: str) -> dict:
    """12 months, by category — lines with markers."""
    df = hourly_profile_df.copy()
    df["month"] = pd.to_datetime(df["date"]).dt.month
    monthly = df.groupby("month")[[f"{c}_wh" for c in CATEGORIES if f"{c}_wh" in df.columns]].sum()
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    x = [month_names[m - 1] for m in monthly.index]
    totals = convert_wh(monthly.sum(axis=1).values, unit)
    option = _shell(f"Monthly Load Totals — Total {totals.sum():,.1f} {unit}", x, "Month", f"Monthly Demand ({unit})")
    option["series"] = _category_line_series(monthly, unit, show_symbol=True)
    return option


def yearly_overview_chart(hourly_profile_df: pd.DataFrame, unit: str) -> dict:
    """Single-line daily-total trend, full year — the coarsest granularity view."""
    df = hourly_profile_df.copy()
    daily = df.groupby("date")["total_wh"].sum()
    annual_total = convert_wh(daily.sum(), unit)
    x = daily.index.astype(str).tolist()

    option = _shell(f"Yearly Load Overview — Annual Total {annual_total:,.2f} {unit}", x, "Date", f"Daily Demand ({unit})", legend=False)
    option["series"] = [{
        "name": "Total demand", "type": "line", "showSymbol": False,
        "data": [round(v, 4) for v in convert_wh(daily.values, unit)],
        "lineStyle": {"color": CATEGORY_COLORS["A"], "width": 2},
        "areaStyle": {"color": CATEGORY_COLORS["A"], "opacity": 0.08},
    }]
    return option


# --- Step 4 (Solar Design): PV / Battery ---

def battery_sensitivity_chart(sensitivity_df: pd.DataFrame, selected_kwh: float, selected_hours: int) -> dict:
    x = [str(int(v)) for v in sensitivity_df["battery_kwh"]]
    option = _shell("Battery Size vs. Unserved-Demand Hours", x, "Battery Size (kWh)", "Zero-Yield Hours / Year")
    option["series"] = [
        {"name": "Zero-yield hours", "type": "line", "showSymbol": True, "symbolSize": 6,
         "data": sensitivity_df["zero_yield_hours"].tolist(), "lineStyle": {"color": CATEGORY_COLORS["A"], "width": 2},
         "itemStyle": {"color": CATEGORY_COLORS["A"]}},
        {"name": "Selected size", "type": "scatter", "symbolSize": 16,
         "data": [[str(int(selected_kwh)), selected_hours]], "itemStyle": {"color": CATEGORY_COLORS["B"]},
         "label": {"show": True, "formatter": f"Selected: {selected_kwh:,.0f} kWh ({selected_hours}h)", "position": "top"}},
    ]
    return option


def egen_vs_demand_chart(simulation_df: pd.DataFrame, start_day: int) -> dict:
    """One week of hourly demand vs. PV generation, and the resulting battery SOC — dual y-axis."""
    window = simulation_df[(simulation_df["hour_of_year"] > (start_day - 1) * 24) & (simulation_df["hour_of_year"] <= (start_day + 6) * 24)]
    x = [str(h) for h in window["hour_of_year"]]
    return {
        "title": {"text": "Demand vs. PV Generation vs. Battery SOC (one week)", "left": "center", "textStyle": _TITLE_STYLE},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 30, "textStyle": _AXIS_LABEL},
        "grid": {"left": 55, "right": 65, "top": 70, "bottom": 45, "containLabel": True},
        "xAxis": {"type": "category", "name": "Hour of year", "nameGap": 28, "data": x, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "yAxis": [
            {"type": "value", "name": "Demand / Generation (kWh)", "nameGap": 14, "splitLine": _SPLIT_LINE, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
            {"type": "value", "name": "Battery SOC (kWh)", "nameGap": 14, "splitLine": {"show": False}, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        ],
        "series": [
            {"name": "Demand (kWh)", "type": "line", "showSymbol": False, "data": [round(v, 3) for v in (window["demand_wh"] / 1000)],
             "lineStyle": {"color": CATEGORY_COLORS["B"], "width": 2}, "itemStyle": {"color": CATEGORY_COLORS["B"]}},
            {"name": "PV Generation (kWh)", "type": "line", "showSymbol": False, "data": [round(v, 3) for v in (window["egen_wh"] / 1000)],
             "lineStyle": {"color": CATEGORY_COLORS["C"], "width": 2}, "itemStyle": {"color": CATEGORY_COLORS["C"]}},
            {"name": "Battery SOC (kWh)", "type": "line", "showSymbol": False, "yAxisIndex": 1,
             "data": [round(v, 3) for v in (window["battery_soc_wh"] / 1000)],
             "lineStyle": {"color": CATEGORY_COLORS["A"], "width": 2, "type": "dotted"}, "itemStyle": {"color": CATEGORY_COLORS["A"]}},
        ],
    }


def irradiance_vs_demand_chart(simulation_df: pd.DataFrame, start_day: int, days: int = 7) -> dict:
    """Dedicated hourly irradiance (GHI, W/m2) vs. demand profile (kWh) chart, dual y-axis so both
    units read cleanly — separate from the demand/generation/SOC chart above."""
    window = simulation_df[(simulation_df["hour_of_year"] > (start_day - 1) * 24) & (simulation_df["hour_of_year"] <= (start_day + days - 1) * 24)]
    x = [str(h) for h in window["hour_of_year"]]
    return {
        "title": {"text": "Hourly Irradiance vs. Demand Profile", "left": "center", "textStyle": _TITLE_STYLE},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 30, "textStyle": _AXIS_LABEL},
        "grid": {"left": 55, "right": 65, "top": 70, "bottom": 45, "containLabel": True},
        "xAxis": {"type": "category", "name": "Hour of year", "nameGap": 28, "data": x, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        "yAxis": [
            {"type": "value", "name": "Demand (kWh)", "nameGap": 14, "splitLine": _SPLIT_LINE, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
            {"type": "value", "name": "Irradiance (W/m²)", "nameGap": 14, "splitLine": {"show": False}, "axisLine": _AXIS_LINE, "axisLabel": _AXIS_LABEL},
        ],
        "series": [
            {"name": "Demand (kWh)", "type": "line", "showSymbol": False, "data": [round(v, 3) for v in (window["demand_wh"] / 1000)],
             "lineStyle": {"color": CATEGORY_COLORS["B"], "width": 2}, "itemStyle": {"color": CATEGORY_COLORS["B"]}},
            {"name": "Irradiance G(i) (W/m²)", "type": "line", "showSymbol": False, "yAxisIndex": 1,
             "data": [round(v, 1) for v in window["ghi_wm2"]],
             "lineStyle": {"color": CATEGORY_COLORS["Misc"], "width": 2, "type": "dotted"}, "itemStyle": {"color": CATEGORY_COLORS["Misc"]}},
        ],
    }


def duck_curve_chart(simulation_df: pd.DataFrame, day: int = None) -> dict:
    """The 'duck curve': net load (demand - PV generation) over a day, showing the midday PV dip and
    the steep evening ramp. If `day` is None, plots the average net-load shape across the whole year."""
    df = simulation_df.copy()
    df["net_load_kwh"] = (df["demand_wh"] - df["egen_wh"]) / 1000

    if day is not None:
        window = df[(df["hour_of_year"] > (day - 1) * 24) & (df["hour_of_year"] <= day * 24)]
        x = [str(h) for h in range(len(window))]
        demand = (window["demand_wh"] / 1000).tolist()
        net_load = window["net_load_kwh"].tolist()
        title = f"Duck Curve — Day {day} of the Year"
        demand_name, net_name = "Demand (kWh)", "Net Load = Demand − PV Generation (kWh)"
    else:
        df["hour_of_day"] = (df["hour_of_year"] - 1) % 24
        avg = df.groupby("hour_of_day")[["demand_wh", "net_load_kwh"]].mean()
        x = [str(h) for h in avg.index]
        demand = (avg["demand_wh"] / 1000).tolist()
        net_load = avg["net_load_kwh"].tolist()
        title = "Duck Curve — Annual Average Daily Shape"
        demand_name, net_name = "Average Demand (kWh)", "Average Net Load = Demand − PV Generation (kWh)"

    option = _shell(title, x, "Hour of day", "Load (kWh)")
    option["series"] = [
        {"name": demand_name, "type": "line", "showSymbol": False, "data": [round(v, 3) for v in demand],
         "lineStyle": {"color": CATEGORY_COLORS["B"], "width": 1.5, "type": "dotted"}},
        {"name": net_name, "type": "line", "showSymbol": False, "data": [round(v, 3) for v in net_load],
         "lineStyle": {"color": CATEGORY_COLORS["A"], "width": 2.5}, "markLine": {"data": [{"yAxis": 0}], "silent": True,
          "lineStyle": {"color": AXIS_INK, "type": "dashed"}, "label": {"show": False}}},
    ]
    return option


# --- Financials: BOQ cost breakdown ---

def boq_cost_breakdown_pie_chart(boq_items_df: pd.DataFrame, currency: str = "EUR") -> dict:
    df = boq_items_df[boq_items_df["total_cost_eur"] > 0].copy()
    total = df["total_cost_eur"].sum()
    palette = list(CATEGORY_COLORS.values()) + [CATEGORY_COLORS["Misc"]]
    data = [
        {"value": round(row["total_cost_eur"], 2), "name": row["description"],
         "itemStyle": {"color": palette[i % len(palette)]}}
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return pie_chart("Bill of Quantities — Cost Breakdown", data, subtitle=f"Total: {total:,.0f} {currency}")


# --- Results: ROI / cash flow ---

def cumulative_cashflow_chart(scenarios: list) -> dict:
    """scenarios: list of {"label": str, "yearly": DataFrame, "color": hex, "discounted_payback_years": float|None}."""
    x = [str(int(y)) for y in scenarios[0]["yearly"]["year"]] if scenarios else []
    option = _shell("Cumulative Discounted Cash Flow", x, "Project year", "Cumulative discounted cash flow (million EUR)")
    series = []
    for s in scenarios:
        series.append({
            "name": s["label"], "type": "line", "showSymbol": False,
            "data": [round(v, 4) for v in (s["yearly"]["cumulative_discounted_eur"] / 1e6)],
            "lineStyle": {"color": s["color"], "width": 2},
            "markLine": {"data": [{"yAxis": 0}], "silent": True, "lineStyle": {"color": AXIS_INK, "type": "dashed"}, "label": {"show": False}},
        })
        if s.get("discounted_payback_years") is not None:
            payback_year_str = str(int(round(s["discounted_payback_years"])))
            series.append({
                "name": f"{s['label']} payback", "type": "scatter", "symbolSize": 12,
                "data": [[payback_year_str, 0]], "itemStyle": {"color": s["color"]},
                "label": {"show": True, "formatter": f"payback: {s['discounted_payback_years']:.1f}y", "position": "top"},
            })
    option["series"] = series
    return option
