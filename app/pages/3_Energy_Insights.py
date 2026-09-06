import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from core import charts
from core import ui
from core.paths import DATA_DIR

st.set_page_config(page_title="Energy Insights", page_icon="📊", layout="wide")
ui.inject_theme()
ui.page_header_image("energy_insights", "Energy Insights",
                      "Hourly, daily, weekly, monthly, and annual views of the demand profile computed (or uploaded) in Demand Profile.")

hourly_path = DATA_DIR / "hourly_load_profile_2026.csv"
if not hourly_path.exists():
    st.warning("No saved hourly profile yet — visit Demand Profile and save a profile first.")
    st.stop()
hourly_profile = pd.read_csv(hourly_path)
hourly_profile["date"] = pd.to_datetime(hourly_profile["date"]).dt.date

unit = st.selectbox("Display unit", ["kWh", "MWh", "TWh"], index=1)


def _show_stats(window_wh: pd.Series):
    stats = charts.load_stats(window_wh, unit)
    ui.stat_tiles([
        ("🔺", "Peak load", f"{stats['peak']:,.3f} {unit}", ui.ACCENT_COLORS["orange"]),
        ("📏", "Average load", f"{stats['average']:,.3f} {unit}", ui.ACCENT_COLORS["aqua"]),
        ("Σ", "Total (this view)", f"{stats['total']:,.3f} {unit}", ui.ACCENT_COLORS["blue"]),
    ])


tab_hourly, tab_daily, tab_weekly, tab_monthly, tab_yearly = st.tabs(["Hourly", "Daily", "Weekly", "Monthly", "Yearly"])

with tab_hourly:
    day = st.slider("Day of year", 1, 365, 1, key="s3_hourly_day")
    st_echarts(options=charts.hourly_profile_chart(hourly_profile, day, unit), height="420px")
    _show_stats(hourly_profile[hourly_profile["day"] == day]["total_wh"])

with tab_daily:
    month = st.selectbox("Month (or All)", ["All"] + list(range(1, 13)), key="s3_daily_month",
                          format_func=lambda m: m if m == "All" else pd.Timestamp(2026, m, 1).strftime("%B"))
    month_arg = None if month == "All" else month
    st_echarts(options=charts.daily_profile_chart(hourly_profile, unit, month=month_arg), height="420px")
    df_tmp = hourly_profile.copy()
    df_tmp["month"] = pd.to_datetime(df_tmp["date"]).dt.month
    _show_stats(df_tmp[df_tmp["month"] == month_arg]["total_wh"] if month_arg else df_tmp["total_wh"])

with tab_weekly:
    max_day = int(hourly_profile["day"].max()) - 6
    start_day = st.slider("Week starting on day of year", 1, max_day, 1, key="s3_week_slider")
    st_echarts(options=charts.weekly_profile_chart(hourly_profile, start_day, unit), height="420px")
    window = hourly_profile[(hourly_profile["day"] >= start_day) & (hourly_profile["day"] < start_day + 7)]["total_wh"]
    _show_stats(window)

with tab_monthly:
    st_echarts(options=charts.monthly_totals_chart(hourly_profile, unit), height="420px")
    _show_stats(hourly_profile["total_wh"])

with tab_yearly:
    st_echarts(options=charts.yearly_overview_chart(hourly_profile, unit), height="420px")
    _show_stats(hourly_profile["total_wh"])

with st.expander("Raw hourly data"):
    st.dataframe(hourly_profile, width="stretch")
