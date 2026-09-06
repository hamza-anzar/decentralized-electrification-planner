"""Rural Electrification Planning App — Home / overview page.

Run with:  streamlit run app/Home.py
(from the project root, with the venv activated — see docs/Local-VSCode-Setup.md)
"""
import sys
from pathlib import Path

# Make the "core" package importable from every page, regardless of Streamlit's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from core.paths import DATA_DIR
from core import ui
from core import cost_lcoe as cl

st.set_page_config(page_title="Rural Electrification Planning", page_icon="☀️", layout="wide")
ui.inject_theme()

st.title("☀️ Rural Electrification Planning — Solar PV")
st.caption("Based on the project's reference workbook (Base-Calculations-00.xlsx), Solar PV only for now.")

ui.disclaimer_banner()

st.markdown(
    """
This app walks through six steps, each building on the last. Use the sidebar to move between them —
every step's editable inputs and results carry forward automatically to the next. All cost figures are
in **EUR** by default, with PKR/USD available as display-only alternates.

1. **Load Setup** — site & location info, household categories, appliances, and community loads → total connected load (W).
2. **Demand Profile** — a fully editable 365-day calendar (seasons, holidays, festivals) → the 8,760-hour annual demand profile.
3. **Energy Insights** — hourly / daily / weekly / monthly / yearly views of that demand profile, with a unit switcher (kWh/MWh/TWh).
4. **Solar Design** — site solar resource (default dataset, live API, or your own upload), PV sizing, battery sizing, irradiance-vs-demand and duck-curve charts.
5. **Financials** — bill of quantities, O&M, and levelized cost of energy (EUR by default).
6. **Results** — every step's results in one place, plus payback/NPV/ROI (a placeholder tariff you should replace with a real one).

Every editable table can be downloaded as an Excel template, edited, and re-uploaded — nothing here requires
touching the underlying data files directly.
"""
)

st.divider()
ui.section_header("📊", "Current saved results (from the last time each step was run)", color=ui.ACCENT_COLORS["gray"])


def _try_read(path, index_col=None):
    p = DATA_DIR / path
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df.set_index(index_col)["value"] if index_col else df


connected_load = _try_read("connected_load_results.csv", "result")
pv_battery = _try_read("pv_battery_sizing_results_2026.csv", "result")
cost_lcoe = _try_read("cost_lcoe_results_2026.csv", "result")

hourly = DATA_DIR / "hourly_load_profile_2026.csv"
annual_gwh_str = "—"
if hourly.exists():
    annual_gwh_str = f"{pd.read_csv(hourly)['total_wh'].sum() / 1e9:.3f} GWh"

capital_cost_str, lcoe_str = "—", "—"
if cost_lcoe is not None:
    capital_cost_str = f"{cost_lcoe['capital_cost_eur']:,.0f} EUR"
    lcoe_str = f"{cost_lcoe['lcoe_eur_per_kwh']:.4f} EUR/kWh"

ui.stat_tiles([
    ("🔌", "Connected load", f"{connected_load['total_connected_load_mw']:.3f} MW" if connected_load is not None else "—", ui.ACCENT_COLORS["blue"]),
    ("⚡", "Annual demand", annual_gwh_str, ui.ACCENT_COLORS["aqua"]),
    ("🔋", "Battery size", f"{pv_battery['battery_capacity_kwh']:,.0f} kWh" if pv_battery is not None else "—", ui.ACCENT_COLORS["orange"]),
])
ui.stat_tiles([
    ("⏱️", "Zero-yield hours", f"{pv_battery['zero_yield_hours']:.0f} h/yr" if pv_battery is not None else "—", ui.ACCENT_COLORS["purple"]),
    ("💶", "Capital cost", capital_cost_str, ui.ACCENT_COLORS["blue"]),
    ("🧾", "LCOE", lcoe_str, ui.ACCENT_COLORS["gray"]),
])

st.info("Open a step from the sidebar to view or edit its inputs and recompute its results.", icon="👈")
