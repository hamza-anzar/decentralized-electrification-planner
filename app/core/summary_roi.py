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


def build_default_roi_parameters(lcoe_eur_per_kwh: float) -> pd.DataFrame:
    """The break-even placeholder tariff (= LCOE), 0% escalation, replacement at year 12 — same as the notebook."""
    return pd.DataFrame([
        {"parameter": "electricity_tariff_eur_per_kwh", "value": lcoe_eur_per_kwh, "unit": "EUR/kWh",
         "description": "PLACEHOLDER — defaults to break-even (= LCOE). Replace with a real planned tariff or avoided-cost figure for a meaningful ROI."},
        {"parameter": "revenue_escalation_rate", "value": 0.0, "unit": "fraction/year", "description": "Annual growth rate applied to the tariff/revenue (0 = flat)"},
        {"parameter": "replacement_year", "value": 12, "unit": "year", "description": "Year the battery and inverter replacement costs hit as a one-time outflow"},
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
    Payback figures are None if never reached within `years`.
    """
    tariff = get_param(roi_parameters_df, "electricity_tariff_eur_per_kwh")
    escalation = get_param(roi_parameters_df, "revenue_escalation_rate")
    replacement_year = int(get_param(roi_parameters_df, "replacement_year"))

    years_arr = np.arange(1, years + 1)
    revenue = annual_energy_served_kwh * tariff * (1 + escalation) ** (years_arr - 1)
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
                          land_cost_options_df: pd.DataFrame) -> dict:
    """Recompute the few extra pieces (battery capex, inverter replacement, land annual cost) Step 5's pipeline
    derives internally, needed again here for the year-by-year cash flow (Step 5 only saved the totals)."""
    battery_capacity_kwh = pv_battery_results["battery_capacity_kwh"]
    battery_capex_eur = (battery_capacity_kwh / 1000) * get_param(cost_parameters_df, "battery_unit_cost_eur_per_mwh")
    inverter_replacement_eur = get_param(cost_parameters_df, "inverter_replacement_pct") * (cost_lcoe_results["capital_cost_eur"] - battery_capex_eur)
    land_approach = get_param(cost_parameters_df, "land_cost_approach")
    land_total_eur = 0 if land_approach in ("none", "buy") else land_cost_options_df.loc[land_cost_options_df["approach"] == land_approach, "total_cost_eur"].iloc[0]
    years = int(get_param(cost_parameters_df, "project_lifetime_years"))
    return {"battery_capex_eur": battery_capex_eur, "inverter_replacement_eur": inverter_replacement_eur,
            "land_annual_cost_eur": land_total_eur / years, "years": years}


def run_roi_scenario(cost_parameters_df: pd.DataFrame, roi_parameters_df: pd.DataFrame, pv_parameters: pd.Series,
                      pv_battery_results: pd.Series, cost_lcoe_results: pd.Series, land_cost_options_df: pd.DataFrame,
                      annual_demand_wh: float) -> dict:
    """One full ROI/cash-flow run for a given set of ROI parameters (tariff, escalation, replacement year)."""
    cost_parameters_df = cost_parameters_df.copy()
    cost_parameters_df["value"] = coerce_numeric_column(cost_parameters_df["value"])

    extras = get_boq_land_battery(cost_parameters_df, pv_battery_results, cost_lcoe_results, land_cost_options_df)
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


def save_results(roi_parameters: pd.DataFrame, master_summary: pd.DataFrame, cashflow: dict) -> None:
    roi_parameters.to_csv(DATA_DIR / "default_roi_parameters.csv", index=False)
    master_summary.to_csv(DATA_DIR / "master_summary_2026.csv", index=False)
    roi_results = pd.DataFrame([{
        "tariff_eur_per_kwh": get_param(roi_parameters, "electricity_tariff_eur_per_kwh"),
        "npv_eur": cashflow["npv_eur"], "roi_pct": cashflow["roi_pct"],
        "simple_payback_years": cashflow["simple_payback_years"], "discounted_payback_years": cashflow["discounted_payback_years"],
    }])
    roi_results.to_csv(DATA_DIR / "roi_results_2026.csv", index=False)


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


def export_project_summary_report(master_summary_df, cashflow_yearly, roi_parameters_df, output_path) -> None:
    """Consolidate every step's key results into one formatted .xlsx — the project's headline deliverable."""
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})
        note_fmt = workbook.add_format({"italic": True, "font_color": "#898781"})

        sheets = {
            "Key Results": master_summary_df,
            "Cash Flow": cashflow_yearly,
            "ROI Parameters": roi_parameters_df,
        }
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                ws.set_column(col_idx, col_idx, max(14, len(str(col_name)) + 2))
            ws.write(len(df) + 2, 0, "Note: all figures are in EUR (the app's base currency) unless labeled otherwise. "
                                     "ROI/cash-flow figures assume the tariff in 'ROI Parameters' — see the app's "
                                     "Results & Summary page for why the break-even default is a placeholder, not a "
                                     "researched market rate.", note_fmt)
