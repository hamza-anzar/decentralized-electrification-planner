"""Step 6 — Summary Table, ROI and payback.

Ported from notebooks/06_Summary_Table.ipynb. ROI/payback is built from scratch (the source workbook
has no revenue model, only LCOE) — electricity_tariff_eur_per_kwh defaults to an explicit break-even
placeholder (= LCOE), clearly flagged in the page as the one input the user should replace with a
real planning assumption.

The app is EUR-based throughout (see cost_lcoe.py); the notebook remains PKR-based and is unaffected.
"""
import pandas as pd
import numpy as np

from .paths import DATA_DIR
from .cost_lcoe import get_param, coerce_numeric_column, convert_currency


def load_defaults() -> dict:
    return {"roi_parameters": pd.read_csv(DATA_DIR / "default_roi_parameters.csv")}


def build_default_roi_parameters(lcoe_eur_per_kwh: float, system_type: str = "battery") -> pd.DataFrame:
    """The break-even placeholder tariff (= LCOE), 0% escalation, replacement at year 12, 3%/yr load
    growth — same as the notebook plus the load-growth addition. `replacement_year`'s description
    names whichever component actually gets replaced for this scenario."""
    is_diesel = system_type in ("diesel", "wind_diesel")
    source_label = "Wind" if system_type in ("wind_battery", "wind_diesel") else "PV"
    replacement_desc = (
        "Year the generator overhaul cost hits as a one-time outflow" if is_diesel
        else "Year the battery and inverter replacement costs hit as a one-time outflow"
    )
    return pd.DataFrame([
        {"parameter": "electricity_tariff_eur_per_kwh", "value": lcoe_eur_per_kwh, "unit": "EUR/kWh",
         "description": "PLACEHOLDER — defaults to break-even (= LCOE). Replace with a real planned tariff or avoided-cost figure for a meaningful ROI."},
        {"parameter": "revenue_escalation_rate", "value": 0.0, "unit": "fraction/year", "description": "Annual growth rate applied to the tariff/revenue (0 = flat)"},
        {"parameter": "replacement_year", "value": 12, "unit": "year", "description": replacement_desc},
        {"parameter": "annual_load_growth_pct", "value": 3.0, "unit": "%/year",
         "description": "Compound annual demand growth applied to the cash-flow's energy served (Energy(year n) = Energy(year 1) x "
                         "(1+g)^(n-1)) — depends on population growth, income/economic growth, increasing connection rate, and "
                         f"productive-use uptake. Typical mini-grid range 3-8%/year; does not resize the physical {source_label}/"
                         f"{'generator' if is_diesel else 'battery'} system."},
    ])


def compute_om_cash_flow(capital_cost_eur, insurance_pct, om_eur_per_kw, ppeak_kw, inflation_rate, years=30):
    """Year-by-year nominal O&M+insurance cash flow (EUR) — same formula as Step 5's compute_om_present_value(),
    restated here to get the yearly (not just total) series."""
    cfo_year1 = insurance_pct * capital_cost_eur + om_eur_per_kw * ppeak_kw
    years_arr = np.arange(1, years + 1)
    return cfo_year1 * (1 + inflation_rate) ** (years_arr - 1)


def simulate_project_cashflow(capital_cost_eur: float, annual_energy_served_kwh: float, battery_capex_eur: float,
                               inverter_replacement_eur: float, land_annual_cost_eur: float,
                               om_cash_flow_by_year: np.ndarray, roi_parameters_df: pd.DataFrame, discount_rate: float,
                               years: int = 30) -> dict:
    """
    Build the full year-by-year project cash flow and derive simple payback, discounted payback, NPV, and lifetime ROI.
    Payback figures are None if never reached within `years`. Revenue compounds two independent
    drivers: the tariff (price) escalates at `revenue_escalation_rate`, and the energy served
    (quantity) grows at `annual_load_growth_pct` — see build_default_roi_parameters()'s description of
    what the latter should depend on. This only affects the cash-flow's revenue; it does not
    re-simulate the PV/battery/generator system's physical performance for future years (that stays
    based on Year-1's hourly profile throughout this app).
    """
    tariff = get_param(roi_parameters_df, "electricity_tariff_eur_per_kwh")
    escalation = get_param(roi_parameters_df, "revenue_escalation_rate")
    replacement_year = int(get_param(roi_parameters_df, "replacement_year"))
    load_growth_rate = get_param(roi_parameters_df, "annual_load_growth_pct") / 100

    years_arr = np.arange(1, years + 1)
    energy_served_by_year = annual_energy_served_kwh * (1 + load_growth_rate) ** (years_arr - 1)
    revenue = energy_served_by_year * tariff * (1 + escalation) ** (years_arr - 1)
    replacement_cost = np.where(years_arr == replacement_year, battery_capex_eur + inverter_replacement_eur, 0.0)
    net_cash_flow = revenue - om_cash_flow_by_year - land_annual_cost_eur - replacement_cost

    cumulative_nominal = np.cumsum(net_cash_flow) - capital_cost_eur
    discounted_cash_flow = net_cash_flow / (1 + discount_rate) ** years_arr
    cumulative_discounted = np.cumsum(discounted_cash_flow) - capital_cost_eur

    yearly = pd.DataFrame({
        "year": years_arr, "revenue_eur": revenue, "om_cost_eur": om_cash_flow_by_year, "land_cost_eur": land_annual_cost_eur,
        "replacement_cost_eur": replacement_cost, "net_cash_flow_eur": net_cash_flow,
        "cumulative_nominal_eur": cumulative_nominal, "cumulative_discounted_eur": cumulative_discounted,
    })

    def _first_crossing_year(cumulative: np.ndarray):
        positive = np.where(cumulative >= 0)[0]
        if len(positive) == 0:
            return None
        i = positive[0]
        if i == 0:
            return 1.0
        prev, curr = cumulative[i - 1], cumulative[i]
        return i + (-prev) / (curr - prev)

    simple_payback_years = _first_crossing_year(cumulative_nominal)
    discounted_payback_years = _first_crossing_year(cumulative_discounted)
    npv_eur = cumulative_discounted[-1]
    roi_pct = (net_cash_flow.sum() - capital_cost_eur) / capital_cost_eur * 100

    return {"yearly": yearly, "simple_payback_years": simple_payback_years, "discounted_payback_years": discounted_payback_years,
            "npv_eur": npv_eur, "roi_pct": roi_pct}


def get_boq_land_battery(cost_parameters_df: pd.DataFrame, pv_battery_results: pd.Series, cost_lcoe_results: pd.Series,
                          land_cost_options_df: pd.DataFrame, boq_items_df: pd.DataFrame) -> dict:
    """Recompute the few extra pieces (battery capex, inverter replacement, land annual cost) Step 5's pipeline
    derives internally, needed again here for the year-by-year cash flow (Step 5 only saved the totals).
    The battery's per-MWh rate lives on its own BOQ row now (lumpsum_unit_cost_eur), not in cost_parameters_df."""
    battery_capacity_kwh = pv_battery_results["battery_capacity_kwh"]
    battery_unit_cost_eur_per_mwh = boq_items_df.loc[boq_items_df["description"] == "Battery System", "lumpsum_unit_cost_eur"].iloc[0]
    battery_capex_eur = (battery_capacity_kwh / 1000) * battery_unit_cost_eur_per_mwh
    inverter_replacement_eur = get_param(cost_parameters_df, "inverter_replacement_pct") * (cost_lcoe_results["capital_cost_eur"] - battery_capex_eur)
    land_approach = get_param(cost_parameters_df, "land_cost_approach")
    land_total_eur = 0 if land_approach in ("none", "buy") else land_cost_options_df.loc[land_cost_options_df["approach"] == land_approach, "total_cost_eur"].iloc[0]
    years = int(get_param(cost_parameters_df, "project_lifetime_years"))
    return {"battery_capex_eur": battery_capex_eur, "inverter_replacement_eur": inverter_replacement_eur,
            "land_annual_cost_eur": land_total_eur / years, "years": years}


def run_roi_scenario(cost_parameters_df: pd.DataFrame, roi_parameters_df: pd.DataFrame, pv_parameters: pd.Series,
                      pv_battery_results: pd.Series, cost_lcoe_results: pd.Series, land_cost_options_df: pd.DataFrame,
                      annual_demand_wh: float, boq_items_df: pd.DataFrame) -> dict:
    """One full ROI/cash-flow run for a given set of ROI parameters (tariff, escalation, replacement year)."""
    cost_parameters_df = cost_parameters_df.copy()
    cost_parameters_df["value"] = coerce_numeric_column(cost_parameters_df["value"])

    extras = get_boq_land_battery(cost_parameters_df, pv_battery_results, cost_lcoe_results, land_cost_options_df, boq_items_df)
    om_cash_flow = compute_om_cash_flow(
        cost_lcoe_results["capital_cost_eur"], get_param(cost_parameters_df, "insurance_pct_per_year"),
        get_param(cost_parameters_df, "om_eur_per_kw_per_year"), pv_parameters["ppeak_w"] / 1000,
        get_param(cost_parameters_df, "inflation_rate"), years=extras["years"],
    )
    annual_energy_served_kwh = annual_demand_wh / 1000  # simplification: treats all demand as served

    cashflow = simulate_project_cashflow(
        cost_lcoe_results["capital_cost_eur"], annual_energy_served_kwh,
        extras["battery_capex_eur"], extras["inverter_replacement_eur"], extras["land_annual_cost_eur"],
        om_cash_flow, roi_parameters_df, get_param(cost_parameters_df, "discount_rate"), years=extras["years"],
    )
    return {"cashflow": cashflow, "extras": extras, "om_cash_flow": om_cash_flow, "annual_energy_served_kwh": annual_energy_served_kwh}


def build_master_summary(connected_load: pd.Series, annual_demand_wh: float, pv_parameters: pd.Series,
                          pv_battery_results: pd.Series, cost_lcoe_results: pd.Series, cost_parameters_df: pd.DataFrame,
                          roi_parameters_df: pd.DataFrame, cashflow: dict) -> pd.DataFrame:
    """Every step's headline figure, pulled into one table. Costs default to EUR (the app's base currency)."""
    eur_to_pkr = get_param(cost_parameters_df, "eur_to_pkr_rate")
    eur_to_usd = get_param(cost_parameters_df, "eur_to_usd_rate")
    tariff = get_param(roi_parameters_df, "electricity_tariff_eur_per_kwh")

    return pd.DataFrame([
        {"section": "Load", "metric": "Total connected load", "value": connected_load["total_connected_load_mw"], "unit": "MW"},
        {"section": "Load", "metric": "Annual demand", "value": annual_demand_wh / 1e9, "unit": "GWh/year"},
        {"section": "PV / Battery", "metric": "PV array size (Ppeak)", "value": pv_parameters["ppeak_w"] / 1e6, "unit": "MW"},
        {"section": "PV / Battery", "metric": "Annual generation (Egen)", "value": pv_battery_results["annual_egen_wh"] / 1e9, "unit": "GWh/year"},
        {"section": "PV / Battery", "metric": "Battery capacity", "value": pv_battery_results["battery_capacity_kwh"], "unit": "kWh"},
        {"section": "PV / Battery", "metric": "Zero-yield hours", "value": pv_battery_results["zero_yield_hours"], "unit": "h/year"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": cost_lcoe_results["capital_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": convert_currency(cost_lcoe_results["capital_cost_eur"], "USD", eur_to_pkr, eur_to_usd), "unit": "USD"},
        {"section": "Cost", "metric": "Total Opex (30yr, present value basis)", "value": cost_lcoe_results["total_opex_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Total cost (Capex+Opex)", "value": cost_lcoe_results["total_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "LCOE (generation-based)", "value": cost_lcoe_results["lcoe_eur_per_kwh"], "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "Tariff used", "value": tariff, "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "NPV", "value": cashflow["npv_eur"], "unit": "EUR"},
        {"section": "ROI", "metric": "Lifetime ROI", "value": cashflow["roi_pct"], "unit": "%"},
        {"section": "ROI", "metric": "Simple payback", "value": cashflow["simple_payback_years"], "unit": "years"},
        {"section": "ROI", "metric": "Discounted payback", "value": cashflow["discounted_payback_years"], "unit": "years"},
    ])


_MISC_ITEMS_ORDER = ["Hospital", "Street Light", "Cold Storage", "School", "Others"]


def compute_billing_summary(item_annual_wh_df: pd.DataFrame, household_categories_df: pd.DataFrame,
                             lcoe_eur_per_kwh: float, tariff_markup_pct: float) -> dict:
    """
    Estimated monthly bill per customer type, at tariff = LCOE x (1 + markup%) — separate from (and
    simpler than) the ROI cash-flow's own electricity_tariff_eur_per_kwh, which is a real planning
    assumption used for NPV/payback. This is a quick "what would category X pay" estimate.

    Household categories (A/B/C) -> average bill PER HOUSEHOLD in that category.
    Misc/community loads (Hospital, School, Street Light, Cold Storage, Others) -> ONE total monthly
    bill for that whole shared load (e.g. all 50 street lights together, not per-lamp).
    """
    tariff_eur_per_kwh = lcoe_eur_per_kwh * (1 + tariff_markup_pct / 100)
    hh_counts = household_categories_df.set_index("category")["household_count"]

    rows = []
    for cat in ["A", "B", "C"]:
        cat_annual_wh = item_annual_wh_df.loc[item_annual_wh_df["category"] == cat, "annual_wh"].sum()
        household_count = hh_counts.get(cat, 1) or 1
        avg_monthly_kwh = (cat_annual_wh / household_count) / 1000 / 12
        rows.append({
            "label": f"Household Category {cat}", "kind": "per_household",
            "avg_monthly_kwh": avg_monthly_kwh, "avg_monthly_bill_eur": avg_monthly_kwh * tariff_eur_per_kwh,
        })

    misc = item_annual_wh_df[item_annual_wh_df["category"] == "Misc"].set_index("item")["annual_wh"]
    for item in _MISC_ITEMS_ORDER:
        if item not in misc.index:
            continue
        monthly_kwh = misc[item] / 1000 / 12
        rows.append({
            "label": item, "kind": "community_load",
            "avg_monthly_kwh": monthly_kwh, "avg_monthly_bill_eur": monthly_kwh * tariff_eur_per_kwh,
        })

    return {"tariff_eur_per_kwh": tariff_eur_per_kwh, "rows": rows}


def save_results(roi_parameters: pd.DataFrame, master_summary: pd.DataFrame, cashflow: dict) -> None:
    roi_parameters.to_csv(DATA_DIR / "default_roi_parameters.csv", index=False)
    master_summary.to_csv(DATA_DIR / "master_summary_2026.csv", index=False)
    roi_results = pd.DataFrame([{
        "tariff_eur_per_kwh": get_param(roi_parameters, "electricity_tariff_eur_per_kwh"),
        "npv_eur": cashflow["npv_eur"], "roi_pct": cashflow["roi_pct"],
        "simple_payback_years": cashflow["simple_payback_years"], "discounted_payback_years": cashflow["discounted_payback_years"],
    }])
    roi_results.to_csv(DATA_DIR / "roi_results_2026.csv", index=False)


# ---------------------------------------------------------------------------
# Solar + Diesel Generator scenario — same cash-flow engine, generator/fuel-specific inputs
# ---------------------------------------------------------------------------

def compute_fuel_cash_flow(annual_fuel_cost_eur: float, inflation_rate: float, years: int = 30) -> np.ndarray:
    """Year-by-year nominal fuel cash flow (EUR), inflated — same escalation pattern as compute_om_cash_flow()."""
    years_arr = np.arange(1, years + 1)
    return annual_fuel_cost_eur * (1 + inflation_rate) ** (years_arr - 1)


def get_boq_land_diesel_extras(cost_parameters_df: pd.DataFrame, pv_diesel_results: pd.Series,
                                cost_lcoe_results: pd.Series, land_cost_options_df: pd.DataFrame,
                                boq_items_df: pd.DataFrame) -> dict:
    """Diesel-scenario analog of get_boq_land_battery(): a one-time generator overhaul (instead of
    battery replacement + inverter replacement) plus the shared land-cost annualization. The
    generator's per-kW rate lives on its own BOQ row now (lumpsum_unit_cost_eur), not in cost_parameters_df."""
    installed_capacity_kw = pv_diesel_results["installed_capacity_kw"]
    generator_unit_cost_eur_per_kw = boq_items_df.loc[boq_items_df["description"] == "Diesel Generator(s)", "lumpsum_unit_cost_eur"].iloc[0]
    generator_capex_eur = installed_capacity_kw * generator_unit_cost_eur_per_kw
    overhaul_eur = get_param(cost_parameters_df, "generator_overhaul_pct") * generator_capex_eur
    land_approach = get_param(cost_parameters_df, "land_cost_approach")
    land_total_eur = 0 if land_approach in ("none", "buy") else land_cost_options_df.loc[land_cost_options_df["approach"] == land_approach, "total_cost_eur"].iloc[0]
    years = int(get_param(cost_parameters_df, "project_lifetime_years"))
    return {"replacement_capex_eur": overhaul_eur, "land_annual_cost_eur": land_total_eur / years, "years": years}


def run_diesel_roi_scenario(cost_parameters_df: pd.DataFrame, roi_parameters_df: pd.DataFrame,
                             pv_diesel_results: pd.Series, cost_lcoe_results: pd.Series,
                             land_cost_options_df: pd.DataFrame, annual_energy_served_wh: float,
                             boq_items_df: pd.DataFrame) -> dict:
    """Diesel-scenario analog of run_roi_scenario(): same simulate_project_cashflow() engine, but O&M is
    based on installed generator capacity (not PV Ppeak) and the recurring fuel cost is added on top."""
    cost_parameters_df = cost_parameters_df.copy()
    cost_parameters_df["value"] = coerce_numeric_column(cost_parameters_df["value"])

    extras = get_boq_land_diesel_extras(cost_parameters_df, pv_diesel_results, cost_lcoe_results, land_cost_options_df, boq_items_df)
    installed_capacity_kw = pv_diesel_results["installed_capacity_kw"]
    om_cash_flow = compute_om_cash_flow(
        cost_lcoe_results["capital_cost_eur"], get_param(cost_parameters_df, "insurance_pct_per_year"),
        get_param(cost_parameters_df, "om_eur_per_kw_per_year"), installed_capacity_kw,
        get_param(cost_parameters_df, "inflation_rate"), years=extras["years"],
    )
    fuel_cash_flow = compute_fuel_cash_flow(
        pv_diesel_results["annual_fuel_cost_eur"], get_param(cost_parameters_df, "inflation_rate"), years=extras["years"],
    )
    total_recurring_cash_flow = om_cash_flow + fuel_cash_flow
    annual_energy_served_kwh = annual_energy_served_wh / 1000

    cashflow = simulate_project_cashflow(
        cost_lcoe_results["capital_cost_eur"], annual_energy_served_kwh,
        extras["replacement_capex_eur"], 0.0, extras["land_annual_cost_eur"],
        total_recurring_cash_flow, roi_parameters_df, get_param(cost_parameters_df, "discount_rate"), years=extras["years"],
    )
    return {"cashflow": cashflow, "extras": extras, "om_cash_flow": total_recurring_cash_flow,
            "annual_energy_served_kwh": annual_energy_served_kwh}


def build_diesel_master_summary(connected_load: pd.Series, annual_demand_wh: float, pv_parameters: pd.Series,
                                 pv_diesel_results: pd.Series, cost_lcoe_results: pd.Series, cost_parameters_df: pd.DataFrame,
                                 roi_parameters_df: pd.DataFrame, cashflow: dict) -> pd.DataFrame:
    """Diesel-scenario analog of build_master_summary(): swaps the battery/zero-yield rows for
    generator-capacity/unmet-hours rows; everything else is structurally identical."""
    eur_to_pkr = get_param(cost_parameters_df, "eur_to_pkr_rate")
    eur_to_usd = get_param(cost_parameters_df, "eur_to_usd_rate")
    tariff = get_param(roi_parameters_df, "electricity_tariff_eur_per_kwh")

    return pd.DataFrame([
        {"section": "Load", "metric": "Total connected load", "value": connected_load["total_connected_load_mw"], "unit": "MW"},
        {"section": "Load", "metric": "Annual demand", "value": annual_demand_wh / 1e9, "unit": "GWh/year"},
        {"section": "PV / Generator", "metric": "PV array size (Ppeak)", "value": pv_parameters["ppeak_w"] / 1e6, "unit": "MW"},
        {"section": "PV / Generator", "metric": "Annual PV generation (Egen)", "value": pv_diesel_results["annual_egen_wh"] / 1e9, "unit": "GWh/year"},
        {"section": "PV / Generator", "metric": "Installed generator capacity", "value": pv_diesel_results["installed_capacity_kw"], "unit": "kW"},
        {"section": "PV / Generator", "metric": "Annual fuel consumption", "value": pv_diesel_results["annual_fuel_liters"], "unit": "L/year"},
        {"section": "PV / Generator", "metric": "Unmet-demand hours", "value": pv_diesel_results["unmet_hours"], "unit": "h/year"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": cost_lcoe_results["capital_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": convert_currency(cost_lcoe_results["capital_cost_eur"], "USD", eur_to_pkr, eur_to_usd), "unit": "USD"},
        {"section": "Cost", "metric": "Total Opex (30yr, present value basis)", "value": cost_lcoe_results["total_opex_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Total cost (Capex+Opex)", "value": cost_lcoe_results["total_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "LCOE", "value": cost_lcoe_results["lcoe_eur_per_kwh"], "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "Tariff used", "value": tariff, "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "NPV", "value": cashflow["npv_eur"], "unit": "EUR"},
        {"section": "ROI", "metric": "Lifetime ROI", "value": cashflow["roi_pct"], "unit": "%"},
        {"section": "ROI", "metric": "Simple payback", "value": cashflow["simple_payback_years"], "unit": "years"},
        {"section": "ROI", "metric": "Discounted payback", "value": cashflow["discounted_payback_years"], "unit": "years"},
    ])


def save_diesel_roi_results(roi_parameters: pd.DataFrame, master_summary: pd.DataFrame, cashflow: dict) -> None:
    roi_parameters.to_csv(DATA_DIR / "default_roi_parameters_diesel.csv", index=False)
    master_summary.to_csv(DATA_DIR / "master_summary_diesel_2026.csv", index=False)
    roi_results = pd.DataFrame([{
        "tariff_eur_per_kwh": get_param(roi_parameters, "electricity_tariff_eur_per_kwh"),
        "npv_eur": cashflow["npv_eur"], "roi_pct": cashflow["roi_pct"],
        "simple_payback_years": cashflow["simple_payback_years"], "discounted_payback_years": cashflow["discounted_payback_years"],
    }])
    roi_results.to_csv(DATA_DIR / "roi_results_diesel_2026.csv", index=False)


# ---------------------------------------------------------------------------
# Wind Turbine + Battery / Wind Turbine + Diesel Generator scenarios — same cash-flow engine as their
# solar counterparts. get_boq_land_battery()/get_boq_land_diesel_extras()/compute_om_cash_flow()/
# compute_fuel_cash_flow()/simulate_project_cashflow() are all reused completely unchanged (already
# generation-technology-agnostic); only the O&M capacity basis (installed turbine kW instead of PV
# Ppeak) and the master-summary labels differ.
# ---------------------------------------------------------------------------

def run_wind_roi_scenario(cost_parameters_df: pd.DataFrame, roi_parameters_df: pd.DataFrame,
                           wind_battery_results: pd.Series, cost_lcoe_results: pd.Series,
                           land_cost_options_df: pd.DataFrame, annual_demand_wh: float,
                           boq_items_df: pd.DataFrame) -> dict:
    """Wind+Battery analog of run_roi_scenario(): O&M scales off installed turbine kW (from the sizing
    results) instead of PV Ppeak; battery/inverter replacement reuse get_boq_land_battery() unchanged."""
    cost_parameters_df = cost_parameters_df.copy()
    cost_parameters_df["value"] = coerce_numeric_column(cost_parameters_df["value"])

    extras = get_boq_land_battery(cost_parameters_df, wind_battery_results, cost_lcoe_results, land_cost_options_df, boq_items_df)
    installed_capacity_kw = wind_battery_results["installed_capacity_kw"]
    om_cash_flow = compute_om_cash_flow(
        cost_lcoe_results["capital_cost_eur"], get_param(cost_parameters_df, "insurance_pct_per_year"),
        get_param(cost_parameters_df, "om_eur_per_kw_per_year"), installed_capacity_kw,
        get_param(cost_parameters_df, "inflation_rate"), years=extras["years"],
    )
    annual_energy_served_kwh = annual_demand_wh / 1000  # simplification: treats all demand as served

    cashflow = simulate_project_cashflow(
        cost_lcoe_results["capital_cost_eur"], annual_energy_served_kwh,
        extras["battery_capex_eur"], extras["inverter_replacement_eur"], extras["land_annual_cost_eur"],
        om_cash_flow, roi_parameters_df, get_param(cost_parameters_df, "discount_rate"), years=extras["years"],
    )
    return {"cashflow": cashflow, "extras": extras, "om_cash_flow": om_cash_flow, "annual_energy_served_kwh": annual_energy_served_kwh}


def build_wind_battery_master_summary(connected_load: pd.Series, annual_demand_wh: float, wind_parameters: pd.Series,
                                       wind_battery_results: pd.Series, cost_lcoe_results: pd.Series, cost_parameters_df: pd.DataFrame,
                                       roi_parameters_df: pd.DataFrame, cashflow: dict) -> pd.DataFrame:
    """Wind+Battery analog of build_master_summary(): swaps the PV-array/Egen rows for turbine-count/
    installed-capacity rows; everything else is structurally identical."""
    eur_to_pkr = get_param(cost_parameters_df, "eur_to_pkr_rate")
    eur_to_usd = get_param(cost_parameters_df, "eur_to_usd_rate")
    tariff = get_param(roi_parameters_df, "electricity_tariff_eur_per_kwh")

    return pd.DataFrame([
        {"section": "Load", "metric": "Total connected load", "value": connected_load["total_connected_load_mw"], "unit": "MW"},
        {"section": "Load", "metric": "Annual demand", "value": annual_demand_wh / 1e9, "unit": "GWh/year"},
        {"section": "Wind / Battery", "metric": "Turbine count", "value": wind_battery_results["turbine_count"], "unit": "units"},
        {"section": "Wind / Battery", "metric": "Installed turbine capacity", "value": wind_battery_results["installed_capacity_kw"], "unit": "kW"},
        {"section": "Wind / Battery", "metric": "Annual generation (Egen)", "value": wind_battery_results["annual_egen_wh"] / 1e9, "unit": "GWh/year"},
        {"section": "Wind / Battery", "metric": "Battery capacity", "value": wind_battery_results["battery_capacity_kwh"], "unit": "kWh"},
        {"section": "Wind / Battery", "metric": "Zero-yield hours", "value": wind_battery_results["zero_yield_hours"], "unit": "h/year"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": cost_lcoe_results["capital_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": convert_currency(cost_lcoe_results["capital_cost_eur"], "USD", eur_to_pkr, eur_to_usd), "unit": "USD"},
        {"section": "Cost", "metric": "Total Opex (30yr, present value basis)", "value": cost_lcoe_results["total_opex_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Total cost (Capex+Opex)", "value": cost_lcoe_results["total_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "LCOE (generation-based)", "value": cost_lcoe_results["lcoe_eur_per_kwh"], "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "Tariff used", "value": tariff, "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "NPV", "value": cashflow["npv_eur"], "unit": "EUR"},
        {"section": "ROI", "metric": "Lifetime ROI", "value": cashflow["roi_pct"], "unit": "%"},
        {"section": "ROI", "metric": "Simple payback", "value": cashflow["simple_payback_years"], "unit": "years"},
        {"section": "ROI", "metric": "Discounted payback", "value": cashflow["discounted_payback_years"], "unit": "years"},
    ])


def save_wind_battery_roi_results(roi_parameters: pd.DataFrame, master_summary: pd.DataFrame, cashflow: dict) -> None:
    roi_parameters.to_csv(DATA_DIR / "default_roi_parameters_wind_battery.csv", index=False)
    master_summary.to_csv(DATA_DIR / "master_summary_wind_battery_2026.csv", index=False)
    roi_results = pd.DataFrame([{
        "tariff_eur_per_kwh": get_param(roi_parameters, "electricity_tariff_eur_per_kwh"),
        "npv_eur": cashflow["npv_eur"], "roi_pct": cashflow["roi_pct"],
        "simple_payback_years": cashflow["simple_payback_years"], "discounted_payback_years": cashflow["discounted_payback_years"],
    }])
    roi_results.to_csv(DATA_DIR / "roi_results_wind_battery_2026.csv", index=False)


def run_wind_diesel_roi_scenario(cost_parameters_df: pd.DataFrame, roi_parameters_df: pd.DataFrame,
                                  wind_diesel_results: pd.Series, cost_lcoe_results: pd.Series,
                                  land_cost_options_df: pd.DataFrame, annual_energy_served_wh: float,
                                  boq_items_df: pd.DataFrame) -> dict:
    """Wind+Diesel analog of run_diesel_roi_scenario(): O&M scales off combined turbine+generator
    installed kW; recurring fuel cost and the one-time generator overhaul reuse
    get_boq_land_diesel_extras()/compute_fuel_cash_flow() unchanged."""
    cost_parameters_df = cost_parameters_df.copy()
    cost_parameters_df["value"] = coerce_numeric_column(cost_parameters_df["value"])

    extras = get_boq_land_diesel_extras(cost_parameters_df, wind_diesel_results, cost_lcoe_results, land_cost_options_df, boq_items_df)
    total_installed_kw = wind_diesel_results["wind_installed_capacity_kw"] + wind_diesel_results["installed_capacity_kw"]
    om_cash_flow = compute_om_cash_flow(
        cost_lcoe_results["capital_cost_eur"], get_param(cost_parameters_df, "insurance_pct_per_year"),
        get_param(cost_parameters_df, "om_eur_per_kw_per_year"), total_installed_kw,
        get_param(cost_parameters_df, "inflation_rate"), years=extras["years"],
    )
    fuel_cash_flow = compute_fuel_cash_flow(
        wind_diesel_results["annual_fuel_cost_eur"], get_param(cost_parameters_df, "inflation_rate"), years=extras["years"],
    )
    total_recurring_cash_flow = om_cash_flow + fuel_cash_flow
    annual_energy_served_kwh = annual_energy_served_wh / 1000

    cashflow = simulate_project_cashflow(
        cost_lcoe_results["capital_cost_eur"], annual_energy_served_kwh,
        extras["replacement_capex_eur"], 0.0, extras["land_annual_cost_eur"],
        total_recurring_cash_flow, roi_parameters_df, get_param(cost_parameters_df, "discount_rate"), years=extras["years"],
    )
    return {"cashflow": cashflow, "extras": extras, "om_cash_flow": total_recurring_cash_flow,
            "annual_energy_served_kwh": annual_energy_served_kwh}


def build_wind_diesel_master_summary(connected_load: pd.Series, annual_demand_wh: float, wind_parameters: pd.Series,
                                      wind_diesel_results: pd.Series, cost_lcoe_results: pd.Series, cost_parameters_df: pd.DataFrame,
                                      roi_parameters_df: pd.DataFrame, cashflow: dict) -> pd.DataFrame:
    """Wind+Diesel analog of build_diesel_master_summary(): turbine-count/installed-capacity rows in
    place of the PV-array rows; everything else is structurally identical."""
    eur_to_pkr = get_param(cost_parameters_df, "eur_to_pkr_rate")
    eur_to_usd = get_param(cost_parameters_df, "eur_to_usd_rate")
    tariff = get_param(roi_parameters_df, "electricity_tariff_eur_per_kwh")

    return pd.DataFrame([
        {"section": "Load", "metric": "Total connected load", "value": connected_load["total_connected_load_mw"], "unit": "MW"},
        {"section": "Load", "metric": "Annual demand", "value": annual_demand_wh / 1e9, "unit": "GWh/year"},
        {"section": "Wind / Generator", "metric": "Turbine count", "value": wind_diesel_results["turbine_count"], "unit": "units"},
        {"section": "Wind / Generator", "metric": "Installed turbine capacity", "value": wind_diesel_results["wind_installed_capacity_kw"], "unit": "kW"},
        {"section": "Wind / Generator", "metric": "Annual wind generation (Egen)", "value": wind_diesel_results["annual_egen_wh"] / 1e9, "unit": "GWh/year"},
        {"section": "Wind / Generator", "metric": "Installed generator capacity", "value": wind_diesel_results["installed_capacity_kw"], "unit": "kW"},
        {"section": "Wind / Generator", "metric": "Annual fuel consumption", "value": wind_diesel_results["annual_fuel_liters"], "unit": "L/year"},
        {"section": "Wind / Generator", "metric": "Unmet-demand hours", "value": wind_diesel_results["unmet_hours"], "unit": "h/year"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": cost_lcoe_results["capital_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Capital cost (Capex)", "value": convert_currency(cost_lcoe_results["capital_cost_eur"], "USD", eur_to_pkr, eur_to_usd), "unit": "USD"},
        {"section": "Cost", "metric": "Total Opex (30yr, present value basis)", "value": cost_lcoe_results["total_opex_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "Total cost (Capex+Opex)", "value": cost_lcoe_results["total_cost_eur"], "unit": "EUR"},
        {"section": "Cost", "metric": "LCOE", "value": cost_lcoe_results["lcoe_eur_per_kwh"], "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "Tariff used", "value": tariff, "unit": "EUR/kWh"},
        {"section": "ROI", "metric": "NPV", "value": cashflow["npv_eur"], "unit": "EUR"},
        {"section": "ROI", "metric": "Lifetime ROI", "value": cashflow["roi_pct"], "unit": "%"},
        {"section": "ROI", "metric": "Simple payback", "value": cashflow["simple_payback_years"], "unit": "years"},
        {"section": "ROI", "metric": "Discounted payback", "value": cashflow["discounted_payback_years"], "unit": "years"},
    ])


def save_wind_diesel_roi_results(roi_parameters: pd.DataFrame, master_summary: pd.DataFrame, cashflow: dict) -> None:
    roi_parameters.to_csv(DATA_DIR / "default_roi_parameters_wind_diesel.csv", index=False)
    master_summary.to_csv(DATA_DIR / "master_summary_wind_diesel_2026.csv", index=False)
    roi_results = pd.DataFrame([{
        "tariff_eur_per_kwh": get_param(roi_parameters, "electricity_tariff_eur_per_kwh"),
        "npv_eur": cashflow["npv_eur"], "roi_pct": cashflow["roi_pct"],
        "simple_payback_years": cashflow["simple_payback_years"], "discounted_payback_years": cashflow["discounted_payback_years"],
    }])
    roi_results.to_csv(DATA_DIR / "roi_results_wind_diesel_2026.csv", index=False)


# --- Excel round-trip: ROI parameters ---

def export_roi_template(roi_parameters_df: pd.DataFrame, output_path) -> None:
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "Edit the 'value' column only — do not add/remove/rename rows.",
            "electricity_tariff_eur_per_kwh defaults to break-even (= LCOE) as a placeholder. Replace it with a real planned tariff, subsidy, or avoided-cost figure for a meaningful ROI.",
            "Save the file, then re-upload it in the app to use these values instead of the defaults.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        roi_parameters_df.to_excel(writer, sheet_name="ROI Parameters", index=False)

        for sheet_name, df in [("Instructions", instructions), ("ROI Parameters", roi_parameters_df)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                ws.set_column(col_idx, col_idx, max(14, len(str(col_name)) + 2))


def import_roi_template(input_path) -> dict:
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)
    if "ROI Parameters" not in sheets:
        return {"roi_parameters": None, "errors": ["Missing required sheet: 'ROI Parameters'"]}

    roi_parameters = sheets["ROI Parameters"]
    defaults = load_defaults()
    if set(roi_parameters.get("parameter", [])) != set(defaults["roi_parameters"]["parameter"]):
        errors.append("'ROI Parameters' must contain exactly the same parameter rows as the default")
    tariff_val = roi_parameters.loc[roi_parameters["parameter"] == "electricity_tariff_eur_per_kwh", "value"]
    if not tariff_val.empty and tariff_val.iloc[0] <= 0:
        errors.append("electricity_tariff_eur_per_kwh must be positive")

    if errors:
        return {"roi_parameters": None, "errors": errors}
    return {"roi_parameters": roi_parameters, "errors": []}


