"""Step 5 — Cost / BOQ / LCOE.

Ported from notebooks/05_Cost_BOQ_LCOE.ipynb (validated there against the source workbook's
Annex-VI, in PKR: capital cost 604,000,000 PKR; O&M PV 85,257,391.43 PKR; demand-based LCOE
10.7879 PKR/kWh). The app uses the generation-based LCOE (project decision #3), same as the
notebook's final default.

The app itself is EUR-based (converted from the notebook's PKR figures once, at 330 PKR/EUR) —
every function here works in EUR; PKR/USD are display-only conversions via convert_currency().
The notebooks remain PKR-based and are not affected by this.
"""
import pandas as pd
import numpy as np

from .paths import DATA_DIR


def load_defaults() -> dict:
    cost_parameters = pd.read_csv(DATA_DIR / "default_cost_parameters.csv")
    # CSV round-tripping loses dtypes: the "value" column mixes numbers with the string "govt_lease", so it
    # comes back as all-strings. Coerce it back here, once, so every caller gets numeric values for free.
    cost_parameters["value"] = coerce_numeric_column(cost_parameters["value"])
    return {
        "boq_items": pd.read_csv(DATA_DIR / "default_boq_items.csv"),
        "land_cost_options": pd.read_csv(DATA_DIR / "default_land_cost_options.csv"),
        "cost_parameters": cost_parameters,
    }


def get_param(parameters_df: pd.DataFrame, name: str):
    """Look up one parameter's value by name from a parameters table — same helper as Step 4's."""
    return parameters_df.loc[parameters_df["parameter"] == name, "value"].iloc[0]


def coerce_numeric_column(series: pd.Series) -> pd.Series:
    """CSV round-tripping loses dtypes — a 'value' column mixing numbers and strings (like 'govt_lease') comes
    back as all-strings. Convert anything that parses as a number back to one; leave genuine strings alone."""
    def _coerce(value):
        try:
            return float(value) if not isinstance(value, (int, float)) else value
        except (TypeError, ValueError):
            return value
    return series.apply(_coerce)


def compute_boq_total(boq_items_df: pd.DataFrame, ppeak_w: float, battery_capacity_kwh: float,
                       panel_unit_cost_per_w: float, battery_unit_cost_per_mwh: float) -> dict:
    """
    Recompute the BOQ grand total, replacing the 'Solar Panels' and 'Battery System' rows' stored total_cost_eur
    with a live calculation from the current Ppeak / battery size — everything else uses the table's own values.
    """
    items = boq_items_df.copy()
    panel_cost = panel_unit_cost_per_w * ppeak_w
    battery_cost = (battery_capacity_kwh / 1000) * battery_unit_cost_per_mwh

    items.loc[items["description"] == "Solar Panels (590 W rated)", "total_cost_eur"] = panel_cost
    items.loc[items["description"] == "Battery System", "total_cost_eur"] = battery_cost

    return {"items": items, "capital_cost_eur": items["total_cost_eur"].sum()}


def compute_om_present_value(capital_cost_eur: float, insurance_pct: float, om_eur_per_kw: float, ppeak_kw: float,
                              inflation_rate: float, discount_rate: float, years: int = 30) -> dict:
    """
    Year-1 cash flow = (insurance_pct x capital cost) + (O&M EUR/kW/yr x system kW), inflated at
    inflation_rate/yr and discounted back to present value at discount_rate/yr, summed over `years`.
    """
    insurance_yr1 = insurance_pct * capital_cost_eur
    om_yr1 = om_eur_per_kw * ppeak_kw
    cfo_year1 = insurance_yr1 + om_yr1

    years_arr = np.arange(1, years + 1)
    cash_flow = cfo_year1 * (1 + inflation_rate) ** (years_arr - 1)
    present_value = cash_flow / (1 + discount_rate) ** years_arr

    yearly_table = pd.DataFrame({"year": years_arr, "cash_flow_eur": cash_flow, "present_value_eur": present_value})
    return {"cfo_year1_eur": cfo_year1, "present_value_eur": present_value.sum(), "yearly_table": yearly_table}


def compute_total_opex(om_present_value_eur: float, battery_capex_eur: float, capital_cost_eur: float,
                        inverter_replacement_pct: float, land_cost_eur: float) -> dict:
    """
    Total 30-year operating cost = O&M/insurance present value + a one-time battery replacement (undiscounted) +
    inverter replacement (a percentage of the non-battery capital cost) + the chosen land-cost line.
    """
    inverter_replacement_eur = inverter_replacement_pct * (capital_cost_eur - battery_capex_eur)
    breakdown = {
        "om_insurance_present_value_eur": om_present_value_eur,
        "battery_replacement_eur": battery_capex_eur,
        "inverter_replacement_eur": inverter_replacement_eur,
        "land_cost_eur": land_cost_eur,
    }
    return {"total_opex_eur": sum(breakdown.values()), "breakdown": breakdown}


def compute_lcoe(capital_cost_eur: float, total_opex_eur: float, annual_energy_wh: float, years: int = 30) -> dict:
    """Total cost (Capex+Opex) / Total energy over `years` years, in EUR/kWh. Pass annual PV GENERATION (not demand)."""
    total_cost_eur = capital_cost_eur + total_opex_eur
    total_energy_kwh = (annual_energy_wh / 1000) * years
    return {"total_cost_eur": total_cost_eur, "total_energy_kwh": total_energy_kwh, "lcoe_eur_per_kwh": total_cost_eur / total_energy_kwh}


def convert_currency(eur_value: float, currency: str, eur_to_pkr_rate: float, eur_to_usd_rate: float) -> float:
    """Convert a EUR amount (the app's base currency) to EUR / PKR / USD for display."""
    if currency == "EUR":
        return eur_value
    elif currency == "PKR":
        return eur_value * eur_to_pkr_rate
    elif currency == "USD":
        return eur_value * eur_to_usd_rate
    raise ValueError(f"Unknown currency '{currency}'. Choose one of: EUR, PKR, USD")


def run_cost_lcoe_pipeline(boq_items_df: pd.DataFrame, land_cost_options_df: pd.DataFrame, cost_parameters_df: pd.DataFrame,
                            ppeak_w: float, battery_capacity_kwh: float, annual_egen_wh: float) -> dict:
    """
    The full Step 5 pipeline: BOQ -> (optional lump-sum override) -> O&M present value -> total Opex (incl. the
    chosen land-cost line) -> LCOE, using annual PV GENERATION as the energy denominator (decision #3).
    All figures are in EUR, the app's base currency.
    """
    panel_cost = get_param(cost_parameters_df, "panel_unit_cost_eur_per_w")
    battery_cost = get_param(cost_parameters_df, "battery_unit_cost_eur_per_mwh")
    boq_result = compute_boq_total(boq_items_df, ppeak_w, battery_capacity_kwh, panel_cost, battery_cost)
    battery_capex_eur = (battery_capacity_kwh / 1000) * battery_cost

    use_lump_sum = bool(get_param(cost_parameters_df, "use_lump_sum_capex"))
    capital_cost_eur = get_param(cost_parameters_df, "lump_sum_capex_eur") if use_lump_sum else boq_result["capital_cost_eur"]

    land_approach = get_param(cost_parameters_df, "land_cost_approach")
    if land_approach == "none":
        land_cost_eur = 0
    else:
        land_cost_eur = land_cost_options_df.loc[land_cost_options_df["approach"] == land_approach, "total_cost_eur"].iloc[0]
    if land_approach == "buy":
        capital_cost_eur += land_cost_eur
        land_cost_for_opex = 0
    else:
        land_cost_for_opex = land_cost_eur

    ppeak_kw = ppeak_w / 1000
    om_result = compute_om_present_value(
        capital_cost_eur, get_param(cost_parameters_df, "insurance_pct_per_year"), get_param(cost_parameters_df, "om_eur_per_kw_per_year"),
        ppeak_kw, get_param(cost_parameters_df, "inflation_rate"),
        get_param(cost_parameters_df, "discount_rate"), years=int(get_param(cost_parameters_df, "project_lifetime_years")),
    )
    opex_result = compute_total_opex(om_result["present_value_eur"], battery_capex_eur, capital_cost_eur,
                                      get_param(cost_parameters_df, "inverter_replacement_pct"), land_cost_for_opex)
    lcoe_result = compute_lcoe(capital_cost_eur, opex_result["total_opex_eur"], annual_egen_wh,
                                years=int(get_param(cost_parameters_df, "project_lifetime_years")))

    return {"boq": boq_result, "capital_cost_eur": capital_cost_eur, "om": om_result, "opex": opex_result, "lcoe": lcoe_result}


def save_results(result: dict) -> None:
    cost_lcoe_results = pd.DataFrame([
        {"result": "capital_cost_eur", "value": result["capital_cost_eur"], "unit": "EUR"},
        {"result": "total_opex_eur", "value": result["opex"]["total_opex_eur"], "unit": "EUR"},
        {"result": "total_cost_eur", "value": result["lcoe"]["total_cost_eur"], "unit": "EUR"},
        {"result": "total_energy_kwh_30yr", "value": result["lcoe"]["total_energy_kwh"], "unit": "kWh"},
        {"result": "lcoe_eur_per_kwh", "value": result["lcoe"]["lcoe_eur_per_kwh"], "unit": "EUR/kWh"},
    ])
    cost_lcoe_results.to_csv(DATA_DIR / "cost_lcoe_results_2026.csv", index=False)


# --- Excel round-trip: BOQ / land / cost parameters ---

def export_cost_template(boq_items_df: pd.DataFrame, land_cost_options_df: pd.DataFrame, cost_parameters_df: pd.DataFrame, output_path) -> None:
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "All costs are in EUR, the app's base currency.",
            "BOQ Items: edit total_cost_eur for any line. The 'Solar Panels' and 'Battery System' rows are recomputed live from Step 4 and the unit-cost parameters below, so their values here are for reference only and will be overridden.",
            "Land Cost Options: edit total_cost_eur for any of the three approaches; which one is actually used is chosen by the land_cost_approach parameter.",
            "Cost Parameters: edit the 'value' column only — do not add/remove/rename rows.",
            "Save the file, then re-upload it in the app to use these values instead of the defaults.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        boq_items_df.to_excel(writer, sheet_name="BOQ Items", index=False)
        land_cost_options_df.to_excel(writer, sheet_name="Land Cost Options", index=False)
        cost_parameters_df.to_excel(writer, sheet_name="Cost Parameters", index=False)

        for sheet_name, df in [("Instructions", instructions), ("BOQ Items", boq_items_df),
                                ("Land Cost Options", land_cost_options_df), ("Cost Parameters", cost_parameters_df)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                ws.set_column(col_idx, col_idx, max(14, len(str(col_name)) + 2))


def import_cost_template(input_path) -> dict:
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)
    required_sheets = ["BOQ Items", "Land Cost Options", "Cost Parameters"]
    missing_sheets = [s for s in required_sheets if s not in sheets]
    if missing_sheets:
        return {"boq_items": None, "land_cost_options": None, "cost_parameters": None, "errors": [f"Missing required sheet(s): {missing_sheets}"]}

    boq_items, land_cost_options, cost_parameters = sheets["BOQ Items"], sheets["Land Cost Options"], sheets["Cost Parameters"]
    defaults = load_defaults()

    if set(boq_items.get("item_no", [])) != set(defaults["boq_items"]["item_no"]):
        errors.append("'BOQ Items' must contain exactly the same 17 item_no rows as the default")
    if (boq_items.get("total_cost_eur", pd.Series(dtype=float)) < 0).any():
        errors.append("BOQ total_cost_eur values must not be negative")
    if set(land_cost_options.get("approach", [])) != set(defaults["land_cost_options"]["approach"]):
        errors.append("'Land Cost Options' must contain exactly the same 3 approach rows as the default")
    if set(cost_parameters.get("parameter", [])) != set(defaults["cost_parameters"]["parameter"]):
        errors.append("'Cost Parameters' must contain exactly the same parameter rows as the default")
    valid_land_approaches = {"buy", "private_lease", "govt_lease", "none"}
    _land_choice = cost_parameters.loc[cost_parameters["parameter"] == "land_cost_approach", "value"]
    if not _land_choice.empty and _land_choice.iloc[0] not in valid_land_approaches:
        errors.append(f"land_cost_approach must be one of {sorted(valid_land_approaches)}")

    if errors:
        return {"boq_items": None, "land_cost_options": None, "cost_parameters": None, "errors": errors}
    cost_parameters["value"] = coerce_numeric_column(cost_parameters["value"])
    return {"boq_items": boq_items, "land_cost_options": land_cost_options, "cost_parameters": cost_parameters, "errors": []}
