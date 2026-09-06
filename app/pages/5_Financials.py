import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from core import cost_lcoe as cl
from core import charts
from core import ui
from core.paths import DATA_DIR

st.set_page_config(page_title="Financials", page_icon="💰", layout="wide")
ui.inject_theme()
ui.page_header_image("financials", "Financials",
                      "Bill of quantities, O&M present value, and levelized cost of energy (LCOE), built on Solar Design's PV/battery sizing. "
                      "All figures are in EUR by default.")

pv_results_path = DATA_DIR / "pv_battery_sizing_results_2026.csv"
pv_params_path = DATA_DIR / "default_pv_parameters.csv"
if not pv_results_path.exists():
    st.warning("No saved PV/battery sizing yet — visit Solar Design and save results first.")
    st.stop()
pv_battery_results = pd.read_csv(pv_results_path).set_index("result")["value"]
pv_parameters = pd.read_csv(pv_params_path).set_index("parameter")["value"]
ppeak_w = pv_parameters["ppeak_w"]
battery_capacity_kwh = pv_battery_results["battery_capacity_kwh"]
annual_egen_wh = pv_battery_results["annual_egen_wh"]
st.caption(f"From Solar Design — Ppeak: {ppeak_w:,.0f} W, battery: {battery_capacity_kwh:,.0f} kWh, annual generation: {annual_egen_wh:,.0f} Wh")

if "s5_boq_items" not in st.session_state:
    d5 = cl.load_defaults()
    st.session_state.s5_boq_items = d5["boq_items"]
    st.session_state.s5_land_cost_options = d5["land_cost_options"]
    st.session_state.s5_cost_parameters = d5["cost_parameters"]

with st.expander("📥 Download template / 📤 Upload edited version"):
    col1, col2 = st.columns(2)
    with col1:
        buf = io.BytesIO()
        cl.export_cost_template(st.session_state.s5_boq_items, st.session_state.s5_land_cost_options,
                                 st.session_state.s5_cost_parameters, buf)
        st.download_button("Download current tables as .xlsx", buf.getvalue(), file_name="Cost_BOQ_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        uploaded = st.file_uploader("Upload an edited .xlsx", type=["xlsx"], key="s5_upload")
        if uploaded is not None:
            result = cl.import_cost_template(uploaded)
            if result["errors"]:
                for e in result["errors"]:
                    st.error(e)
            else:
                st.session_state.s5_boq_items = result["boq_items"]
                st.session_state.s5_land_cost_options = result["land_cost_options"]
                st.session_state.s5_cost_parameters = result["cost_parameters"]
                st.success("Uploaded tables applied below.")

ui.section_header("📋", "1. Bill of Quantities (BOQ)", color=ui.ACCENT_COLORS["blue"])
st.caption("'Solar Panels' and 'Battery System' rows are recomputed live from Solar Design + the unit-cost parameters below — edits to their total_cost_eur here are reference only. All values in EUR.")
st.session_state.s5_boq_items = st.data_editor(st.session_state.s5_boq_items, num_rows="fixed", width="stretch", key="s5_boq_editor")

ui.section_header("🌍", "2. Land cost options", color=ui.ACCENT_COLORS["aqua"])
st.session_state.s5_land_cost_options = st.data_editor(st.session_state.s5_land_cost_options, num_rows="fixed", width="stretch", key="s5_land_editor")

ui.section_header("⚙️", "3. Cost parameters", color=ui.ACCENT_COLORS["gray"])
st.session_state.s5_cost_parameters = st.data_editor(
    st.session_state.s5_cost_parameters, num_rows="fixed", width="stretch", key="s5_costparam_editor",
    disabled=["parameter", "unit", "description"],
)
st.session_state.s5_cost_parameters["value"] = cl.coerce_numeric_column(st.session_state.s5_cost_parameters["value"])

result = cl.run_cost_lcoe_pipeline(st.session_state.s5_boq_items, st.session_state.s5_land_cost_options,
                                    st.session_state.s5_cost_parameters, ppeak_w, battery_capacity_kwh, annual_egen_wh)

st.divider()
ui.section_header("📊", "Results", color=ui.ACCENT_COLORS["gray"])

currency = st.radio("Show figures in", ["EUR", "PKR", "USD"], horizontal=True, key="s5_currency")
eur_rate = cl.get_param(st.session_state.s5_cost_parameters, "eur_to_pkr_rate")
usd_rate = cl.get_param(st.session_state.s5_cost_parameters, "eur_to_usd_rate")


def _fmt(eur_value):
    return f"{cl.convert_currency(eur_value, currency, eur_rate, usd_rate):,.2f} {currency}"


ui.stat_tiles([
    ("💶", "Capital cost", _fmt(result["capital_cost_eur"]), ui.ACCENT_COLORS["blue"]),
    ("🧾", "Total Opex (30yr PV)", _fmt(result["opex"]["total_opex_eur"]), ui.ACCENT_COLORS["orange"]),
    ("💰", "Total cost", _fmt(result["lcoe"]["total_cost_eur"]), ui.ACCENT_COLORS["aqua"]),
])
lcoe_display = cl.convert_currency(result["lcoe"]["lcoe_eur_per_kwh"], currency, eur_rate, usd_rate)
ui.stat_tiles([("⚡", "LCOE (generation-based)", f"{lcoe_display:.4f} {currency}/kWh", ui.ACCENT_COLORS["purple"])])

st_echarts(options=charts.boq_cost_breakdown_pie_chart(result["boq"]["items"], currency="EUR"), height="420px")

with st.expander("Live BOQ (Solar Panels / Battery System recomputed)"):
    st.dataframe(result["boq"]["items"], width="stretch")
with st.expander("O&M yearly cash flow (30-year table, EUR)"):
    st.dataframe(result["om"]["yearly_table"], width="stretch")

if st.button("💾 Save these results (used by Results page)", type="primary"):
    cl.save_results(result)
    st.session_state.s5_boq_items.to_csv(DATA_DIR / "default_boq_items.csv", index=False)
    st.session_state.s5_land_cost_options.to_csv(DATA_DIR / "default_land_cost_options.csv", index=False)
    st.session_state.s5_cost_parameters.to_csv(DATA_DIR / "default_cost_parameters.csv", index=False)
    st.success(f"Saved. LCOE: {result['lcoe']['lcoe_eur_per_kwh']:.4f} EUR/kWh")
