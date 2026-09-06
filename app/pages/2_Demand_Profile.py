import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts

from core import load_profile as lp
from core import load_estimation as le
from core import charts
from core import ui
from core.paths import DATA_DIR

st.set_page_config(page_title="Demand Profile", page_icon="📅", layout="wide")
ui.inject_theme()
ui.page_header_image("demand_profile", "Demand Profile",
                      "A fully editable 365-day calendar (seasons, holidays, festivals) drives the 8,760-hour annual demand profile.")

# --- Session state init ---
if "s2_season_periods" not in st.session_state:
    d2 = lp.load_defaults()
    st.session_state.s2_season_periods = d2["season_periods"]
    st.session_state.s2_public_holidays = d2["public_holidays"]
    st.session_state.s2_festival_holidays = d2["festival_holidays"]
    st.session_state.s2_daytype_profiles = d2["daytype_profiles"]
    st.session_state.s2_custom_profile = None

mode = st.radio("Demand profile source", ["Computed from calendar rules (default)", "Fully custom upload (bypass calendar)"], horizontal=True)

if mode == "Fully custom upload (bypass calendar)":
    st.subheader("Custom hourly profile")
    col1, col2 = st.columns(2)
    with col1:
        buf = io.BytesIO()
        lp.export_hourly_profile_template(buf)
        st.download_button("Download blank Date/Hour/Load_kWh template", buf.getvalue(), file_name="Hourly_Load_Profile_Template.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        uploaded = st.file_uploader("Upload your filled-in template", type=["xlsx"], key="s2_hourly_upload")
        if uploaded is not None:
            result = lp.import_hourly_profile(uploaded)
            if result["errors"]:
                for e in result["errors"]:
                    st.error(e)
            else:
                st.session_state.s2_custom_profile = result["hourly_profile"]
                st.success("Custom profile loaded.")

    if st.session_state.s2_custom_profile is not None:
        hourly_profile = st.session_state.s2_custom_profile
        annual_gwh = hourly_profile["total_wh"].sum() / 1e9
        st.metric("Annual demand (custom)", f"{annual_gwh:.6f} GWh")
        if st.button("💾 Save this custom profile as the project's demand profile", type="primary"):
            hourly_profile.to_csv(DATA_DIR / "hourly_load_profile_2026.csv", index=False)
            st.success("Saved to data/hourly_load_profile_2026.csv")
    else:
        st.info("Upload a filled-in template above to use a fully custom hourly profile.")

else:
    with st.expander("📥 Download calendar-rules template / 📤 Upload edited version", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            buf = io.BytesIO()
            lp.export_calendar_rules_template(st.session_state.s2_season_periods, st.session_state.s2_public_holidays,
                                               st.session_state.s2_festival_holidays, buf)
            st.download_button("Download current calendar rules as .xlsx", buf.getvalue(), file_name="Calendar_Rules_Template.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col2:
            uploaded = st.file_uploader("Upload an edited .xlsx", type=["xlsx"], key="s2_calendar_upload")
            if uploaded is not None:
                result = lp.import_calendar_rules_template(uploaded)
                if result["errors"]:
                    for e in result["errors"]:
                        st.error(e)
                else:
                    st.session_state.s2_season_periods = result["season_periods"]
                    st.session_state.s2_public_holidays = result["public_holidays"]
                    st.session_state.s2_festival_holidays = result["festival_holidays"]
                    st.success("Uploaded calendar rules applied below.")

    ui.section_header("🗓️", "Season periods", color=ui.ACCENT_COLORS["blue"])
    st.caption("Must cover all 365 days exactly once (MM-DD dates, no year). weekday/weekend day-type selects the usage pattern.")
    st.session_state.s2_season_periods = st.data_editor(
        st.session_state.s2_season_periods, num_rows="dynamic", width="stretch", key="s2_season_editor"
    )
    period_errors = lp.validate_season_periods(st.session_state.s2_season_periods)
    if period_errors:
        for e in period_errors:
            st.error(e)
    else:
        st.success("Season periods cover all 365 days with no gaps or overlaps.")

    col1, col2 = st.columns(2)
    with col1:
        ui.section_header("🎌", "Public holidays", color=ui.ACCENT_COLORS["aqua"])
        st.session_state.s2_public_holidays = st.data_editor(
            st.session_state.s2_public_holidays, num_rows="dynamic", width="stretch", key="s2_holidays_editor"
        )
    with col2:
        ui.section_header("🎉", "Festival holidays", color=ui.ACCENT_COLORS["orange"])
        st.session_state.s2_festival_holidays = st.data_editor(
            st.session_state.s2_festival_holidays, num_rows="dynamic", width="stretch", key="s2_festivals_editor"
        )

    with st.expander("Day-type usage profiles (advanced — 456 rows, one per day-type x hour)"):
        with st.expander("📥 Download day-type template / 📤 Upload edited version", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                buf = io.BytesIO()
                lp.export_daytype_template(st.session_state.s2_daytype_profiles, buf)
                st.download_button("Download day-type profiles as .xlsx", buf.getvalue(), file_name="Day_Type_Profiles_Template.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with col2:
                uploaded_dt = st.file_uploader("Upload an edited .xlsx", type=["xlsx"], key="s2_daytype_upload")
                if uploaded_dt is not None:
                    result_dt = lp.import_daytype_template(uploaded_dt)
                    if result_dt["errors"]:
                        for e in result_dt["errors"]:
                            st.error(e)
                    else:
                        st.session_state.s2_daytype_profiles = result_dt["daytype_profiles"]
                        st.success("Uploaded day-type profiles applied.")
        st.dataframe(st.session_state.s2_daytype_profiles, width="stretch")

    if not period_errors:
        defaults1 = le.load_defaults()
        household_categories = st.session_state.get("s1_household_categories", defaults1["household_categories"])
        appliances = st.session_state.get("s1_appliances", defaults1["appliances"])
        misc_loads = st.session_state.get("s1_misc_loads", defaults1["misc_loads"])

        full = lp.compute_full_profile(2026, st.session_state.s2_season_periods, st.session_state.s2_public_holidays,
                                        st.session_state.s2_festival_holidays, st.session_state.s2_daytype_profiles,
                                        appliances, misc_loads, household_categories)
        hourly_profile = full["hourly_profile"]

        st.divider()
        ui.section_header("📊", "Results", color=ui.ACCENT_COLORS["gray"])
        annual_gwh = hourly_profile["total_wh"].sum() / 1e9
        ui.stat_tiles([("⚡", "Annual demand", f"{annual_gwh:.6f} GWh", ui.ACCENT_COLORS["blue"])])

        granularity = st.selectbox("Load profile granularity", ["Hourly", "Daily", "Weekly", "Monthly", "Annual"], index=4, key="s2_granularity")
        unit = st.selectbox("Display unit", ["kWh", "MWh", "TWh"], index=1, key="s2_unit")

        if granularity == "Hourly":
            day = st.slider("Day of year", 1, 365, 1, key="s2_hourly_day")
            fig = charts.hourly_profile_chart(hourly_profile, day, unit)
            window = hourly_profile[hourly_profile["day"] == day]["total_wh"]
        elif granularity == "Daily":
            month = st.selectbox("Month (or All)", ["All"] + list(range(1, 13)), key="s2_daily_month",
                                  format_func=lambda m: m if m == "All" else pd.Timestamp(2026, m, 1).strftime("%B"))
            month_arg = None if month == "All" else month
            fig = charts.daily_profile_chart(hourly_profile, unit, month=month_arg)
            df_tmp = hourly_profile.copy()
            df_tmp["month"] = pd.to_datetime(df_tmp["date"]).dt.month
            window = df_tmp[df_tmp["month"] == month_arg]["total_wh"] if month_arg else df_tmp["total_wh"]
        elif granularity == "Weekly":
            max_day = 365 - 6
            start_day = st.slider("Week starting on day of year", 1, max_day, 1, key="s2_week_slider")
            fig = charts.weekly_profile_chart(hourly_profile, start_day, unit)
            window = hourly_profile[(hourly_profile["day"] >= start_day) & (hourly_profile["day"] < start_day + 7)]["total_wh"]
        elif granularity == "Monthly":
            fig = charts.monthly_totals_chart(hourly_profile, unit)
            window = hourly_profile["total_wh"]
        else:
            fig = charts.yearly_overview_chart(hourly_profile, unit)
            window = hourly_profile["total_wh"]

        st_echarts(options=fig, height="420px")
        stats = charts.load_stats(window, unit)
        ui.stat_tiles([
            ("🔺", "Peak load", f"{stats['peak']:,.3f} {unit}", ui.ACCENT_COLORS["orange"]),
            ("📏", "Average load", f"{stats['average']:,.3f} {unit}", ui.ACCENT_COLORS["aqua"]),
            ("Σ", "Total (this view)", f"{stats['total']:,.3f} {unit}", ui.ACCENT_COLORS["blue"]),
        ])

        if st.button("💾 Save this calendar + profile (used by Energy Insights onward)", type="primary"):
            lp.save_results(full["calendar"], hourly_profile)
            st.session_state.s2_season_periods.to_csv(DATA_DIR / "default_season_periods.csv", index=False)
            st.session_state.s2_public_holidays.to_csv(DATA_DIR / "default_public_holidays.csv", index=False)
            st.session_state.s2_festival_holidays.to_csv(DATA_DIR / "default_festival_holidays.csv", index=False)
            st.session_state.s2_daytype_profiles.to_csv(DATA_DIR / "default_daytype_profiles.csv", index=False)
            st.success(f"Saved. Annual demand: {annual_gwh:.6f} GWh")
