import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from core import solar_pv as spv
from core import charts
from core import ui
from core.paths import DATA_DIR

st.set_page_config(page_title="Solar Design", page_icon="🔋", layout="wide")
ui.inject_theme()
ui.page_header_image("solar_design", "Solar Design",
                      "Solar PV with Battery System — site solar resource, PV generation, and battery sizing against the demand profile. "
                      "(A future version of this page will let you couple the PV system with a diesel generator instead of, or alongside, the battery.)")

hourly_path = DATA_DIR / "hourly_load_profile_2026.csv"
if not hourly_path.exists():
    st.warning("No saved hourly profile yet — visit Demand Profile and save a profile first.")
    st.stop()
hourly_profile = pd.read_csv(hourly_path)

# --- Session state init ---
if "s4_irradiance" not in st.session_state:
    st.session_state.s4_irradiance = spv.load_default_irradiance()
    st.session_state.s4_irradiance_source = "default (bundled)"
    st.session_state.s4_pv_parameters = spv.load_default_pv_parameters()

ui.section_header("☀️", "1. Solar resource (site irradiance)", color=ui.ACCENT_COLORS["yellow"])
col1, col2, col3 = st.columns(3)
lat = col1.number_input("Latitude", value=spv.DEFAULT_LAT, format="%.4f")
lon = col2.number_input("Longitude", value=spv.DEFAULT_LON, format="%.4f")
source = col3.selectbox("Source", ["default", "pvgis", "nasa_power", "custom"],
                         help="'default' is this project's bundled site data (no network needed). "
                              "'pvgis'/'nasa_power' need internet access — see the note below.")

if st.button("Fetch / use this source"):
    result = spv.get_solar_resource(lat, lon, source=source)
    st.session_state.s4_irradiance = result["data"]
    st.session_state.s4_irradiance_source = result["source_used"]
    for e in result["errors"]:
        st.warning(e)
    st.success(f"Using source: {result['source_used']}")

st.caption(f"Current source: **{st.session_state.s4_irradiance_source}**. "
           "Note: PVGIS/NASA POWER need outbound internet access to their APIs — confirm they work from wherever you run this app.")

with st.expander("📥 Download irradiance template / 📤 Upload your own"):
    col1, col2 = st.columns(2)
    with col1:
        buf = io.BytesIO()
        spv.export_irradiance_template(st.session_state.s4_irradiance, buf)
        st.download_button("Download current irradiance as .xlsx", buf.getvalue(), file_name="Irradiance_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        uploaded = st.file_uploader("Upload an edited/replacement .xlsx", type=["xlsx"], key="s4_irr_upload")
        if uploaded is not None:
            result = spv.import_irradiance_template(uploaded)
            if result["errors"]:
                for e in result["errors"]:
                    st.error(e)
            else:
                st.session_state.s4_irradiance = result["data"]
                st.session_state.s4_irradiance_source = "uploaded"
                st.success("Uploaded irradiance applied.")

ui.section_header("🔧", "2. PV system parameters", color=ui.ACCENT_COLORS["blue"])
with st.expander("📥 Download PV parameters template / 📤 Upload edited version"):
    col1, col2 = st.columns(2)
    with col1:
        buf = io.BytesIO()
        spv.export_pv_parameters_template(st.session_state.s4_pv_parameters, buf)
        st.download_button("Download current PV parameters as .xlsx", buf.getvalue(), file_name="PV_Parameters_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        uploaded_pv = st.file_uploader("Upload an edited .xlsx", type=["xlsx"], key="s4_pv_upload")
        if uploaded_pv is not None:
            result_pv = spv.import_pv_parameters_template(uploaded_pv)
            if result_pv["errors"]:
                for e in result_pv["errors"]:
                    st.error(e)
            else:
                st.session_state.s4_pv_parameters = result_pv["data"]
                st.success("Uploaded PV parameters applied.")

st.session_state.s4_pv_parameters = st.data_editor(
    st.session_state.s4_pv_parameters, num_rows="fixed", width="stretch", key="s4_pv_editor",
    disabled=["parameter", "unit", "description"],
)

with st.expander("📐 Formulas used for PV generation & battery sizing"):
    st.markdown("**PV hourly generation (Egen):**")
    st.latex(r"E_{gen} = P_{peak} \times \frac{G(i)}{1000} \times \frac{Q}{I_{qc}}")
    st.caption("Ppeak = PV array nameplate capacity (W) · G(i) = hourly global irradiance (W/m²) · "
               "Q = performance ratio / derating factor · Iqc = reference (STC) irradiance (kW/m²).")

    st.markdown("**Hourly generation-minus-demand imbalance, grouped into contiguous surplus/deficit blocks:**")
    st.latex(r"\Delta E_h = E_{gen,h} - Demand_h")
    st.caption("Consecutive hours with the same sign of ΔE are grouped into one block; the block with the "
               "most negative sum is the worst (longest/deepest) deficit run of the year.")

    st.markdown("**Battery capacity, sized from the worst deficit block:**")
    st.latex(r"Battery_{kWh} = \mathrm{MROUND}\left(\frac{-SDE_{worst}/1000}{DoD} \times QualityFactor,\ 1000\right)")
    st.caption("SDE_worst = worst block's summed deficit (Wh, negative) · DoD = battery max depth of discharge · "
               "QualityFactor = battery derating factor · MROUND rounds to the nearest 1,000 kWh.")

# --- Compute ---
step4 = spv.run_pv_battery_sizing(hourly_profile, st.session_state.s4_irradiance, st.session_state.s4_pv_parameters)
results = step4["results"]

st.divider()
ui.section_header("📊", "Results", color=ui.ACCENT_COLORS["gray"])
ui.stat_tiles([
    ("☀️", "Annual generation (Egen)", f"{results['annual_egen_wh']/1e9:.6f} GWh", ui.ACCENT_COLORS["yellow"]),
    ("🔋", "Battery capacity", f"{results['battery_capacity_kwh']:,.0f} kWh", ui.ACCENT_COLORS["blue"]),
    ("⏱️", "Zero-yield hours", f"{results['zero_yield_hours']:.0f} h/year", ui.ACCENT_COLORS["orange"]),
])

ui.section_header("🔋", "Battery size sensitivity", color=ui.ACCENT_COLORS["blue"])
candidate_sizes = list(range(1000, 16001, 1000))
sensitivity = spv.battery_size_sensitivity(step4["blocks"]["delta_e_wh"], candidate_sizes)
st_echarts(options=charts.battery_sensitivity_chart(sensitivity, results["battery_capacity_kwh"], results["zero_yield_hours"]), height="420px")

ui.section_header("📈", "Demand vs. generation vs. battery SOC (one week)", color=ui.ACCENT_COLORS["aqua"])
max_day = 365 - 6
start_day = st.slider("Week starting on day of year", 1, max_day, 1, key="s4_week_slider")
st_echarts(options=charts.egen_vs_demand_chart(step4["simulation"], start_day), height="420px")

ui.section_header("☀️", "Hourly irradiance vs. demand profile", color=ui.ACCENT_COLORS["yellow"])
irr_days = st.slider("Number of days to show", 1, 14, 7, key="s4_irr_days")
st_echarts(options=charts.irradiance_vs_demand_chart(step4["simulation"], start_day, days=irr_days), height="420px")

ui.section_header("🦆", "Duck curve (net load = demand − PV generation)", color=ui.ACCENT_COLORS["purple"])
duck_mode = st.radio("View", ["Annual average day", "A specific day"], horizontal=True, key="s4_duck_mode")
if duck_mode == "A specific day":
    duck_day = st.slider("Day of year", 1, 365, 172, key="s4_duck_day")
    st_echarts(options=charts.duck_curve_chart(step4["simulation"], day=duck_day), height="420px")
else:
    st_echarts(options=charts.duck_curve_chart(step4["simulation"], day=None), height="420px")
st.caption("The midday dip is PV generation offsetting demand; the steep evening ramp is demand staying up while the sun sets — "
           "the classic 'duck curve' shape that drives battery-sizing needs.")

if st.button("💾 Save these results (used by Financials & Results)", type="primary"):
    spv.save_results(step4["simulation"], results)
    st.session_state.s4_pv_parameters.to_csv(DATA_DIR / "default_pv_parameters.csv", index=False)
    st.session_state.s4_irradiance.to_csv(DATA_DIR / "default_irradiance_2026.csv", index=False)
    st.success(f"Saved. Battery: {results['battery_capacity_kwh']:,.0f} kWh, zero-yield hours: {results['zero_yield_hours']:.0f}")
