import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from core import load_estimation as le
from core import site_info as si
from core import charts
from core import ui
from core.paths import DATA_DIR

st.set_page_config(page_title="Load Setup", page_icon="🔌", layout="wide")
ui.inject_theme()
ui.page_header_image("load_setup", "Load Setup",
                      "Site details, household categories, per-category appliances, and community loads → total connected load.")

# --- Session state init ---
if "s1_household_categories" not in st.session_state:
    defaults = le.load_defaults()
    st.session_state.s1_household_categories = defaults["household_categories"]
    st.session_state.s1_appliances = defaults["appliances"]
    st.session_state.s1_misc_loads = defaults["misc_loads"]
if "s1_site_info" not in st.session_state:
    st.session_state.s1_site_info = si.load_defaults()
if "s1_total_houses" not in st.session_state:
    st.session_state.s1_total_houses = int(st.session_state.s1_household_categories["household_count"].sum())

# --- 0. Site / location info (context only — not used in the calculations below) ---
ui.section_header("📍", "Site & location info", color=ui.ACCENT_COLORS["purple"])
st.caption("Context for later socio-economic analysis and per-capita figures — these fields don't feed the load/generation calculations.")

with st.container(border=True):
    site = si.as_dict(st.session_state.s1_site_info)
    row1 = st.columns(3)
    project_name = row1[0].text_input("Project name", value=str(site.get("project_name", "")))
    country = row1[1].text_input("Country", value=str(site.get("country", "")))
    region = row1[2].text_input("City / village / region", value=str(site.get("region_city_village", "")))

    row2 = st.columns(4)
    lat = row2[0].number_input("Latitude", value=float(site.get("latitude", 0.0)), format="%.4f")
    lon = row2[1].number_input("Longitude", value=float(site.get("longitude", 0.0)), format="%.4f")
    population = row2[2].number_input("Population (people)", min_value=0, value=int(float(site.get("population", 0))), step=50)
    area_km2 = row2[3].number_input("Area (km²)", min_value=0.0, value=float(site.get("area_km2", 0.0)), step=0.05, format="%.2f")

    row3 = st.columns(4)
    weather_type = row3[0].text_input("Weather / climate type", value=str(site.get("weather_type", "")))
    socioeconomic_class = row3[1].text_input("Socio-economic class", value=str(site.get("socioeconomic_class", "")))
    gdp_per_capita = row3[2].number_input("GDP per capita (USD/person/year)", min_value=0.0, value=float(site.get("gdp_per_capita_usd", 0.0)), step=50.0)
    electrification_pct = row3[3].number_input("Current electrification (%)", min_value=0.0, max_value=100.0, value=float(site.get("electrification_pct", 0.0)), step=1.0)

    if st.button("💾 Save site info"):
        st.session_state.s1_site_info = pd.DataFrame([
            {"field": "project_name", "value": project_name, "unit": "", "description": "Name of the project / site"},
            {"field": "country", "value": country, "unit": "", "description": "Country"},
            {"field": "region_city_village", "value": region, "unit": "", "description": "City / village / region name"},
            {"field": "latitude", "value": lat, "unit": "degrees N", "description": "Site latitude (also used by the Solar PV page)"},
            {"field": "longitude", "value": lon, "unit": "degrees E", "description": "Site longitude (also used by the Solar PV page)"},
            {"field": "population", "value": population, "unit": "people", "description": "Total population at the site (independent of household count — used for per-capita figures)"},
            {"field": "area_km2", "value": area_km2, "unit": "km2", "description": "Approximate site/service area"},
            {"field": "weather_type", "value": weather_type, "unit": "", "description": "General climate classification (e.g. coastal, arid, temperate)"},
            {"field": "socioeconomic_class", "value": socioeconomic_class, "unit": "", "description": "Broad socio-economic description of the served population"},
            {"field": "gdp_per_capita_usd", "value": gdp_per_capita, "unit": "USD/person/year", "description": "Reference GDP per capita, for later socio-economic analysis"},
            {"field": "electrification_pct", "value": electrification_pct, "unit": "%", "description": "Current grid electrification rate at the site before this project (0 = fully off-grid)"},
        ])
        si.save(st.session_state.s1_site_info)
        st.success("Site info saved.")

st.divider()

# --- Excel upload / download (appliances / household categories / misc loads) ---
with st.expander("📥 Download appliance template / 📤 Upload edited version", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        buf = io.BytesIO()
        le.export_appliance_template(st.session_state.s1_household_categories, st.session_state.s1_appliances,
                                      st.session_state.s1_misc_loads, buf)
        st.download_button("Download current tables as .xlsx", buf.getvalue(), file_name="Connected_Load_Input_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        uploaded = st.file_uploader("Upload an edited .xlsx", type=["xlsx"], key="s1_upload")
        if uploaded is not None:
            result = le.import_appliance_template(uploaded)
            if result["errors"]:
                for e in result["errors"]:
                    st.error(e)
            else:
                st.session_state.s1_household_categories = result["household_categories"]
                st.session_state.s1_appliances = result["appliances"]
                st.session_state.s1_misc_loads = result["misc_loads"]
                st.session_state.s1_total_houses = int(result["household_categories"]["household_count"].sum())
                st.success("Uploaded tables applied below.")

# --- 1. Household categories: total houses + % split -> household_count computed live ---
ui.section_header("🏘️", "Household categories", color=ui.ACCENT_COLORS["orange"])
st.caption("Enter the total number of houses in the area and each category's % split — the household count per category is computed for you, live.")

with st.container(border=True):
    hh = st.session_state.s1_household_categories.copy()
    total_houses = st.number_input("Total number of houses in the area", min_value=0,
                                    value=int(st.session_state.s1_total_houses), step=10, key="s1_total_houses_input")

    pct_cols = st.columns(len(hh))
    new_pct = []
    for col, (_, row) in zip(pct_cols, hh.iterrows()):
        with col:
            st.markdown(f"**{row['label']}**")
            pct = st.number_input("% split", min_value=0.0, max_value=100.0, value=float(row["pct_split"]),
                                   step=1.0, key=f"s1_pct_{row['category']}")
            new_pct.append(pct)
    hh["pct_split"] = new_pct
    pct_total = sum(new_pct)
    if abs(pct_total - 100.0) > 0.01:
        st.warning(f"% split adds up to {pct_total:.1f}%, not 100%. The household counts below are still computed directly from these percentages.")

    hh = le.apply_total_houses_split(hh, total_houses)
    st.session_state.s1_household_categories = hh
    st.session_state.s1_total_houses = total_houses

    tiles = [("🏠", f"{row['label']}", f"{int(row['household_count']):,} houses", ui.category_color(row["category"]))
             for _, row in hh.iterrows()]
    ui.stat_tiles(tiles)
    st.caption(f"Total: {int(hh['household_count'].sum()):,} houses (target: {int(total_houses):,})")
    st_echarts(options=charts.household_split_pie_chart(hh), height="360px")

st.divider()

ui.section_header("🔌", "Appliances per household, by category", color=ui.ACCENT_COLORS["blue"])
with st.container(border=True):
    st.session_state.s1_appliances = st.data_editor(
        st.session_state.s1_appliances, num_rows="dynamic", width="stretch", key="s1_appl_editor"
    )

ui.section_header("🏢", "Miscellaneous / community loads", color=ui.ACCENT_COLORS["aqua"])
with st.container(border=True):
    st.session_state.s1_misc_loads = st.data_editor(
        st.session_state.s1_misc_loads, num_rows="dynamic", width="stretch", key="s1_misc_editor"
    )

# --- Compute ---
result = le.compute_connected_load(st.session_state.s1_appliances, st.session_state.s1_household_categories, st.session_state.s1_misc_loads)
total_w = result["total_w"]

st.divider()
ui.section_header("📊", "Results", color=ui.ACCENT_COLORS["gray"])
ui.stat_tiles([
    ("⚡", "Total connected load", f"{total_w:,.0f} W", ui.ACCENT_COLORS["blue"]),
    ("⚡", "Total connected load", f"{total_w/1000:,.2f} kW", ui.ACCENT_COLORS["orange"]),
    ("⚡", "Total connected load", f"{total_w/1_000_000:,.5f} MW", ui.ACCENT_COLORS["aqua"]),
])

col_a, col_b = st.columns(2)
with col_a:
    st_echarts(options=charts.connected_load_by_category_chart(result["by_category"]), height="420px")
with col_b:
    st_echarts(options=charts.top_contributors_chart(result["lines"]), height="420px")

with st.expander("Full line-by-line breakdown"):
    st.dataframe(result["lines"], width="stretch")

if st.button("💾 Save these results (used by the Results page)", type="primary"):
    le.save_results(total_w, result["by_category"])
    st.session_state.s1_household_categories.to_csv(DATA_DIR / "default_household_categories.csv", index=False)
    st.session_state.s1_appliances.to_csv(DATA_DIR / "default_appliances.csv", index=False)
    st.session_state.s1_misc_loads.to_csv(DATA_DIR / "default_misc_loads.csv", index=False)
    st.success(f"Saved. Total connected load: {total_w/1_000_000:.5f} MW")
