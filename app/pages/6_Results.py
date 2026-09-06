import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from core import summary_roi as sr
from core import cost_lcoe as cl
from core import site_info as si
from core import charts
from core import ui
from core.paths import DATA_DIR

st.set_page_config(page_title="Results", page_icon="📋", layout="wide")
ui.inject_theme()
ui.page_header_image("results", "Results",
                      "Every prior step's headline figures in one place, plus payback/NPV/ROI — built from scratch, since the source workbook has no revenue model.")
ui.disclaimer_banner()

required = ["connected_load_results.csv", "hourly_load_profile_2026.csv", "pv_battery_sizing_results_2026.csv",
            "default_pv_parameters.csv", "cost_lcoe_results_2026.csv", "default_cost_parameters.csv", "default_land_cost_options.csv"]
missing = [f for f in required if not (DATA_DIR / f).exists()]
if missing:
    st.warning(f"Missing results from earlier steps: {missing}. Visit and save each step first.")
    st.stop()

connected_load = pd.read_csv(DATA_DIR / "connected_load_results.csv").set_index("result")["value"]
hourly_profile = pd.read_csv(DATA_DIR / "hourly_load_profile_2026.csv")
annual_demand_wh = hourly_profile["total_wh"].sum()
pv_battery_results = pd.read_csv(DATA_DIR / "pv_battery_sizing_results_2026.csv").set_index("result")["value"]
pv_parameters = pd.read_csv(DATA_DIR / "default_pv_parameters.csv").set_index("parameter")["value"]
cost_lcoe_results = pd.read_csv(DATA_DIR / "cost_lcoe_results_2026.csv").set_index("result")["value"]
cost_parameters = pd.read_csv(DATA_DIR / "default_cost_parameters.csv")
cost_parameters["value"] = cl.coerce_numeric_column(cost_parameters["value"])
land_cost_options = pd.read_csv(DATA_DIR / "default_land_cost_options.csv")
site = si.as_dict(si.load_defaults())
household_categories = pd.read_csv(DATA_DIR / "default_household_categories.csv") if (DATA_DIR / "default_household_categories.csv").exists() else None

currency = st.radio("Show cost figures in", ["EUR", "PKR", "USD"], horizontal=True, key="s6_currency")
eur_rate = cl.get_param(cost_parameters, "eur_to_pkr_rate")
usd_rate = cl.get_param(cost_parameters, "eur_to_usd_rate")


def _fmt(eur_value):
    return f"{cl.convert_currency(eur_value, currency, eur_rate, usd_rate):,.2f} {currency}"


# --- 1. Project / site overview ---
ui.section_header("📍", "Project overview", color=ui.ACCENT_COLORS["purple"])
with st.container(border=True):
    total_houses = int(household_categories["household_count"].sum()) if household_categories is not None else None
    tiles = [
        ("🏷️", "Project", str(site.get("project_name", "—")), ui.ACCENT_COLORS["purple"]),
        ("🌍", "Location", f"{site.get('region_city_village', '—')}, {site.get('country', '—')}", ui.ACCENT_COLORS["blue"]),
        ("🏘️", "Houses", f"{total_houses:,}" if total_houses is not None else "—", ui.ACCENT_COLORS["orange"]),
        ("👥", "Population", f"{int(float(site.get('population', 0))):,} people", ui.ACCENT_COLORS["aqua"]),
    ]
    ui.stat_tiles(tiles)
    st.caption(f"Lat/Lon: {site.get('latitude', '—')}, {site.get('longitude', '—')} · Area: {site.get('area_km2', '—')} km² · "
               f"Climate: {site.get('weather_type', '—')} · Socio-economic class: {site.get('socioeconomic_class', '—')} · "
               f"Pre-project electrification: {site.get('electrification_pct', 0)}%")

st.divider()

# --- 2. Headline system / cost figures ---
ui.section_header("🔧", "System & cost summary", color=ui.ACCENT_COLORS["gray"])
project_lifetime = int(cl.get_param(cost_parameters, "project_lifetime_years"))

with st.container(border=True):
    ui.stat_tiles([
        ("☀️", "System size (Ppeak)", f"{pv_parameters['ppeak_w']/1e6:.3f} MW", ui.ACCENT_COLORS["yellow"]),
        ("🔋", "Battery size", f"{pv_battery_results['battery_capacity_kwh']:,.0f} kWh", ui.ACCENT_COLORS["blue"]),
        ("⏱️", "No-electricity hours/year", f"{pv_battery_results['zero_yield_hours']:.0f} h", ui.ACCENT_COLORS["orange"]),
        ("📅", "Project lifetime", f"{project_lifetime} years", ui.ACCENT_COLORS["aqua"]),
    ])
    ui.stat_tiles([
        ("⚡", "Annual demand", f"{annual_demand_wh/1e9:.4f} GWh", ui.ACCENT_COLORS["blue"]),
        ("☀️", "Annual generation", f"{pv_battery_results['annual_egen_wh']/1e9:.4f} GWh", ui.ACCENT_COLORS["yellow"]),
        ("💶", "Investment cost (Capex)", _fmt(cost_lcoe_results["capital_cost_eur"]), ui.ACCENT_COLORS["purple"]),
        ("🧾", "LCOE", f"{cl.convert_currency(cost_lcoe_results['lcoe_eur_per_kwh'], currency, eur_rate, usd_rate):.4f} {currency}/kWh", ui.ACCENT_COLORS["gray"]),
    ])

st.divider()

# --- 3. ROI assumptions ---
ui.section_header("💡", "ROI assumptions", color=ui.ACCENT_COLORS["orange"])
st.warning(
    "**The source workbook has no revenue model at all** — only cost (LCOE). `electricity_tariff_eur_per_kwh` below "
    "defaults to an explicit **break-even placeholder** (= the computed LCOE), not a researched market rate. "
    "**Replace it with a real planned tariff, subsidy, or avoided-cost figure** for a meaningful ROI — everything "
    "below (payback, NPV, ROI) moves directly off of it.",
    icon="⚠️",
)

if "s6_roi_parameters" not in st.session_state:
    st.session_state.s6_roi_parameters = sr.build_default_roi_parameters(cost_lcoe_results["lcoe_eur_per_kwh"])

with st.expander("📥 Download ROI parameters template / 📤 Upload edited version"):
    col1, col2 = st.columns(2)
    with col1:
        buf = io.BytesIO()
        sr.export_roi_template(st.session_state.s6_roi_parameters, buf)
        st.download_button("Download current ROI parameters as .xlsx", buf.getvalue(), file_name="ROI_Parameters_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        uploaded = st.file_uploader("Upload an edited .xlsx", type=["xlsx"], key="s6_upload")
        if uploaded is not None:
            result = sr.import_roi_template(uploaded)
            if result["errors"]:
                for e in result["errors"]:
                    st.error(e)
            else:
                st.session_state.s6_roi_parameters = result["roi_parameters"]
                st.success("Uploaded ROI parameters applied.")

st.session_state.s6_roi_parameters = st.data_editor(
    st.session_state.s6_roi_parameters, num_rows="fixed", width="stretch", key="s6_roi_editor",
    disabled=["parameter", "unit", "description"],
)

show_comparison = st.checkbox("Show a comparison scenario at a different tariff", value=True)
compare_pct = st.slider("Comparison tariff, as % of the current tariff above", 50, 200, 150, step=10, disabled=not show_comparison)

scenario = sr.run_roi_scenario(cost_parameters, st.session_state.s6_roi_parameters, pv_parameters, pv_battery_results,
                                cost_lcoe_results, land_cost_options, annual_demand_wh)
cashflow = scenario["cashflow"]
yearly_opex_eur = float(scenario["om_cash_flow"][0]) if len(scenario["om_cash_flow"]) else 0.0

st.divider()

# --- 4. ROI results ---
ui.section_header("📈", "ROI, Payback & Investment Results", color=ui.ACCENT_COLORS["blue"])
with st.container(border=True):
    ui.stat_tiles([
        ("🧾", "Yearly operating cost (Year 1)", _fmt(yearly_opex_eur), ui.ACCENT_COLORS["orange"]),
        ("💶", "NPV", _fmt(cashflow["npv_eur"]), ui.ACCENT_COLORS["purple"]),
        ("⏳", "Simple payback", f"{cashflow['simple_payback_years']:.1f} yr" if cashflow["simple_payback_years"] else f"never ({project_lifetime}yr)", ui.ACCENT_COLORS["aqua"]),
        ("⏳", "Discounted payback", f"{cashflow['discounted_payback_years']:.1f} yr" if cashflow["discounted_payback_years"] else f"never ({project_lifetime}yr)", ui.ACCENT_COLORS["blue"]),
    ])

    gauge_col, chart_col = st.columns([1, 2])
    with gauge_col:
        roi_pct = cashflow["roi_pct"]
        gauge_color = ui.ACCENT_COLORS["aqua"] if roi_pct >= 0 else ui.ACCENT_COLORS["orange"]
        # Gauge is bounded for readability — very negative/positive ROI still shows the exact % in the center label.
        gauge_max = max(50, abs(roi_pct) * 1.2)
        st_echarts(options=charts.gauge_chart(roi_pct, "Lifetime ROI", unit="%", max_value=gauge_max, color=gauge_color), height="280px")
        st.caption("Off-grid rural electrification projects like this one are usually **not** profitable on tariff revenue alone — "
                   "a negative ROI here is the expected, typical result, not a bug.")
    with chart_col:
        chart_scenarios = [{
            "label": f"{cl.get_param(st.session_state.s6_roi_parameters, 'electricity_tariff_eur_per_kwh'):.3f} EUR/kWh",
            "yearly": cashflow["yearly"], "color": ui.ACCENT_COLORS["blue"], "discounted_payback_years": cashflow["discounted_payback_years"],
        }]
        compare_params = None
        if show_comparison:
            compare_params = st.session_state.s6_roi_parameters.copy()
            compare_params.loc[compare_params["parameter"] == "electricity_tariff_eur_per_kwh", "value"] *= compare_pct / 100
            compare_scenario = sr.run_roi_scenario(cost_parameters, compare_params, pv_parameters, pv_battery_results,
                                                    cost_lcoe_results, land_cost_options, annual_demand_wh)
            chart_scenarios.append({
                "label": f"{cl.get_param(compare_params, 'electricity_tariff_eur_per_kwh'):.3f} EUR/kWh ({compare_pct}%)",
                "yearly": compare_scenario["cashflow"]["yearly"], "color": ui.ACCENT_COLORS["orange"],
                "discounted_payback_years": compare_scenario["cashflow"]["discounted_payback_years"],
            })
        st_echarts(options=charts.cumulative_cashflow_chart(chart_scenarios), height="360px")

with st.expander("Why might 'tariff = LCOE' not show NPV = 0?"):
    st.markdown(
        "Financials' LCOE is a blended figure — it discounts O&M to a present value but leaves capex, replacement "
        "costs, and land undiscounted, then divides by **generation**. This cash-flow model uses the full nominal "
        "(escalating) O&M series and only earns revenue on energy **demanded**, not everything generated. Both are "
        "legitimate views, they just don't coincide by default — don't read too much into a negative NPV at the "
        "break-even placeholder tariff; it's an artifact of using LCOE as a stand-in price, not a statement the "
        "project loses money. Replace the tariff with your real assumption for a meaningful answer."
    )

with st.expander("Full cash-flow table (primary scenario, EUR)"):
    st.dataframe(cashflow["yearly"], width="stretch")

st.divider()

ui.section_header("📄", "Master summary — every step's key result", color=ui.ACCENT_COLORS["gray"])
master_summary = sr.build_master_summary(connected_load, annual_demand_wh, pv_parameters, pv_battery_results,
                                          cost_lcoe_results, cost_parameters, st.session_state.s6_roi_parameters, cashflow)
st.dataframe(master_summary, width="stretch")

col1, col2 = st.columns(2)
with col1:
    if st.button("💾 Save ROI parameters + master summary", type="primary"):
        sr.save_results(st.session_state.s6_roi_parameters, master_summary, cashflow)
        st.success("Saved.")
with col2:
    buf = io.BytesIO()
    sr.export_project_summary_report(master_summary, cashflow["yearly"], st.session_state.s6_roi_parameters, buf)
    st.download_button("📄 Download Project Summary Report (.xlsx)", buf.getvalue(), file_name="Project_Summary_Report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
