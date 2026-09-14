"""Wind Turbine + Battery / Wind Turbine + Diesel Generator sizing.

Mirrors core/solar_pv.py's structure exactly, but the generation source is a wind turbine's power
curve instead of a solar irradiance model. The battery-sizing math (compute_delta_e_and_blocks,
size_battery, simulate_battery_soc, count_zero_yield_hours) and the generator-sizing math
(compute_deficit_wh, recommend_generator_size, dispatch_generator, compute_fuel_liters_and_cost,
deficit_load_duration) are already fully generic in solar_pv.py -- they take a plain demand/egen
series and never reference irradiance/Ppeak -- so they're imported and reused unchanged rather than
duplicated. Only the wind-generation step itself (wind speed -> power, via a turbine power curve) is
new.

Wind speed default dataset: extracted directly from the source workbook's Annex-V column H (raw
pasted hourly wind speed, no formula), the same provenance as core/solar_pv.py's
default_irradiance_2026.csv (from Annex-IV). See docs/Workbook-Methodology-Reference.md section 8.
"""
import numpy as np
import pandas as pd
import requests

from .paths import DATA_DIR
from . import solar_pv as spv

DEFAULT_LAT = spv.DEFAULT_LAT
DEFAULT_LON = spv.DEFAULT_LON

get_param = spv.get_param  # shared helper, no need to duplicate


def load_default_wind_speed() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_wind_speed_2026.csv")


def load_default_wind_parameters() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_wind_parameters.csv")


def load_default_wind_parameters_diesel() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_wind_parameters_diesel.csv")


def load_default_diesel_generator_parameters_wind() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_diesel_generator_parameters_wind.csv")


def load_wind_turbine_library() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_wind_turbines.csv")


def load_wind_turbine_power_curves() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_wind_turbine_power_curves.csv")


def power_curve_for_model(model: str) -> pd.DataFrame:
    """The (wind_speed_ms, power_kw) curve for one library turbine model."""
    curves = load_wind_turbine_power_curves()
    curve = curves[curves["model"] == model][["wind_speed_ms", "power_kw"]]
    if curve.empty:
        raise ValueError(f"Unknown turbine model '{model}' -- not found in the turbine library")
    return curve.reset_index(drop=True)


def fetch_nasa_power_wind_hourly(lat: float, lon: float, year: int = 2020, timeout: int = 60) -> dict:
    """Fetch one year of hourly wind speed at 10m (m/s, NASA POWER's WS10M) for the given site --
    the same no-signup source and standardize_to_project_year() pipeline already used for solar
    irradiance in core/solar_pv.py."""
    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    params = {
        "parameters": "WS10M", "community": "RE",
        "latitude": lat, "longitude": lon,
        "start": f"{year}0101", "end": f"{year}1231",
        "format": "JSON",
    }

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as e:
        return {"data": None, "errors": [f"NASA POWER request failed: {e}"]}
    except ValueError as e:
        return {"data": None, "errors": [f"NASA POWER returned an unparseable response: {e}"]}

    try:
        series = payload["properties"]["parameter"]["WS10M"]
    except KeyError:
        return {"data": None, "errors": ["NASA POWER response was missing the expected data — check lat/lon are valid"]}

    raw = pd.DataFrame({"timestamp": list(series.keys()), "wind_speed_ms": list(series.values())})
    raw["month"] = raw["timestamp"].str.slice(4, 6).astype(int)
    raw["day"] = raw["timestamp"].str.slice(6, 8).astype(int)
    raw["hour"] = raw["timestamp"].str.slice(8, 10).astype(int)
    raw = raw[raw["wind_speed_ms"] > -900]  # NASA POWER uses -999 as a "no data" fill value

    standardized = spv.standardize_to_project_year(raw, "month", "day", "hour", "wind_speed_ms")
    return {"data": standardized, "errors": []}


def get_wind_resource(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, year: int = 2020,
                       source: str = "nasa_power", fallback_to_default: bool = True) -> dict:
    """Get an 8,760-hour wind-speed profile [hour_of_year, wind_speed_ms] (at the 10m reference
    height) for (lat, lon). source: "nasa_power" (default, live) or "default" (bundled dataset)."""
    errors = []
    default_wind_speed = load_default_wind_speed()

    if source == "default":
        return {"data": default_wind_speed.copy(), "source_used": "default (bundled)", "errors": []}
    elif source == "nasa_power":
        result = fetch_nasa_power_wind_hourly(lat, lon, year)
    else:
        result = {"data": None, "errors": [f"Unknown source '{source}'. Choose one of: nasa_power, default"]}

    if result["data"] is not None:
        return {"data": result["data"], "source_used": source, "errors": result["errors"]}

    errors.extend(result["errors"])
    if fallback_to_default:
        errors.append(f"Falling back to the bundled default wind-speed dataset (source '{source}' was unavailable).")
        return {"data": default_wind_speed.copy(), "source_used": "default (fallback)", "errors": errors}
    return {"data": None, "source_used": None, "errors": errors}


def apply_hub_height_shear(wind_speed_ms: pd.Series, hub_height_m: float, reference_height_m: float,
                            alpha: float) -> pd.Series:
    """Wind-shear power-law correction: v(hub) = v(ref) x (hub_height/reference_height)^alpha. The
    source workbook used raw reference-height wind speed directly against the turbine hub; skipping
    this understates real yield since wind speed increases with height. alpha=0.14 is a typical
    Hellman exponent for open/coastal terrain (user-editable)."""
    return wind_speed_ms * (hub_height_m / reference_height_m) ** alpha


def compute_wind_egen(wind_speed_ms: pd.Series, power_curve_df: pd.DataFrame, turbine_count: float) -> pd.Series:
    """Hourly wind-turbine generation (Wh): linear interpolation of the turbine's own power curve
    (wind_speed_ms -> power_kw) at each hour's (already shear-corrected) wind speed, x turbine count.
    Zero below cut-in and above cut-out (both already 0 kW in every library curve)."""
    curve = power_curve_df.sort_values("wind_speed_ms")
    power_kw = np.interp(wind_speed_ms.values, curve["wind_speed_ms"].values, curve["power_kw"].values, left=0, right=0)
    return pd.Series(power_kw * 1000 * turbine_count, index=wind_speed_ms.index)


def recommend_turbine_count(demand_wh: pd.Series, single_turbine_egen_wh: pd.Series, max_count: int = 10) -> dict:
    """Recommend the smallest turbine count whose annual generation meets or exceeds annual demand --
    a sizing heuristic in the same spirit as the source project's own decision rule for wind ("checked
    the zero yield hours, went with the least ones"). Always manually overridable, same as every other
    sizing recommendation in this app (Ppeak, battery size, generator size)."""
    annual_demand_wh = float(demand_wh.sum())
    annual_single_turbine_wh = float(single_turbine_egen_wh.sum())
    if annual_single_turbine_wh <= 0:
        recommended = 1
    else:
        recommended = max_count
        for count in range(1, max_count + 1):
            if annual_single_turbine_wh * count >= annual_demand_wh:
                recommended = count
                break
    return {
        "recommended_count": recommended,
        "annual_demand_wh": annual_demand_wh,
        "annual_single_turbine_wh": annual_single_turbine_wh,
    }


def _wind_speed_at_hub(hourly_profile_df: pd.DataFrame, wind_speed_df: pd.DataFrame,
                        wind_parameters_df: pd.DataFrame):
    demand = hourly_profile_df.set_index("hour_of_year")["total_wh"]
    wind_speed_ref = wind_speed_df.set_index("hour_of_year")["wind_speed_ms"]

    hub_height_m = float(get_param(wind_parameters_df, "hub_height_m"))
    reference_height_m = float(get_param(wind_parameters_df, "reference_height_m"))
    alpha = float(get_param(wind_parameters_df, "shear_exponent_alpha"))
    wind_speed_hub = apply_hub_height_shear(wind_speed_ref, hub_height_m, reference_height_m, alpha)
    return demand, wind_speed_hub


def run_wind_battery_sizing(hourly_profile_df: pd.DataFrame, wind_speed_df: pd.DataFrame,
                             wind_parameters_df: pd.DataFrame, power_curve_df: pd.DataFrame,
                             manual_battery_kwh: float = None) -> dict:
    """End-to-end Wind+Battery pipeline: demand + wind speed + turbine/parameters -> shear-corrected
    wind speed, turbine generation, deficit blocks, battery size, SOC, zero-yield hours. Reuses the
    exact same generic battery-sizing math as Solar+Battery (core.solar_pv), just fed by wind
    generation instead of solar generation."""
    demand, wind_speed_hub = _wind_speed_at_hub(hourly_profile_df, wind_speed_df, wind_parameters_df)
    turbine_count = float(get_param(wind_parameters_df, "turbine_count"))
    dod = float(get_param(wind_parameters_df, "battery_dod"))
    quality_factor = float(get_param(wind_parameters_df, "battery_quality_factor"))
    rated_power_kw = float(power_curve_df["power_kw"].max())
    installed_capacity_kw = rated_power_kw * turbine_count

    egen = compute_wind_egen(wind_speed_hub, power_curve_df, turbine_count)
    blocks = spv.compute_delta_e_and_blocks(demand, egen)
    sums = spv.block_sums(blocks)
    worst_block = sums.min()

    auto_battery_kwh = spv.size_battery(worst_block, dod, quality_factor)
    battery_kwh = manual_battery_kwh if manual_battery_kwh is not None else auto_battery_kwh
    soc = spv.simulate_battery_soc(blocks["delta_e_wh"], battery_kwh)
    zero_hours = spv.count_zero_yield_hours(soc)

    simulation = pd.DataFrame({
        "hour_of_year": demand.index,
        "demand_wh": demand.values,
        "wind_speed_ms": wind_speed_hub.values,
        "egen_wh": egen.values,
        "delta_e_wh": blocks["delta_e_wh"].values,
        "block_id": blocks["block_id"].values,
        "battery_soc_wh": soc,
    })

    sizing_results = {
        "annual_egen_wh": float(egen.sum()), "annual_demand_wh": float(demand.sum()),
        "worst_deficit_block_wh": float(worst_block), "battery_capacity_kwh": battery_kwh,
        "auto_battery_capacity_kwh": auto_battery_kwh, "is_manual_battery_size": manual_battery_kwh is not None,
        "zero_yield_hours": zero_hours, "turbine_count": turbine_count,
        "rated_power_kw": rated_power_kw, "installed_capacity_kw": installed_capacity_kw,
    }
    return {"simulation": simulation, "results": sizing_results, "blocks": blocks}


def save_wind_battery_results(simulation: pd.DataFrame, results: dict) -> None:
    simulation.to_csv(DATA_DIR / "wind_battery_simulation_2026.csv", index=False)
    df = pd.DataFrame([
        {"result": "annual_egen_wh", "value": results["annual_egen_wh"], "unit": "Wh", "description": "Total annual wind generation at the selected turbine count"},
        {"result": "annual_demand_wh", "value": results["annual_demand_wh"], "unit": "Wh", "description": "Total annual demand"},
        {"result": "worst_deficit_block_wh", "value": results["worst_deficit_block_wh"], "unit": "Wh", "description": "Worst single contiguous deficit run — drives battery sizing"},
        {"result": "battery_capacity_kwh", "value": results["battery_capacity_kwh"], "unit": "kWh", "description": "Sized battery capacity"},
        {"result": "zero_yield_hours", "value": results["zero_yield_hours"], "unit": "hours/year", "description": "Hours per year the battery is fully depleted (unserved demand) at the sized capacity"},
        {"result": "turbine_count", "value": results["turbine_count"], "unit": "units", "description": "Number of turbines, as configured"},
        {"result": "rated_power_kw", "value": results["rated_power_kw"], "unit": "kW", "description": "Selected turbine's rated (plateau) power, per unit"},
        {"result": "installed_capacity_kw", "value": results["installed_capacity_kw"], "unit": "kW", "description": "Total installed turbine capacity (rated power x turbine count) — drives the BOQ's Wind Turbine(s) line and O&M"},
    ])
    df.to_csv(DATA_DIR / "wind_battery_sizing_results_2026.csv", index=False)


def run_wind_diesel_sizing(hourly_profile_df: pd.DataFrame, wind_speed_df: pd.DataFrame,
                            wind_parameters_df: pd.DataFrame, power_curve_df: pd.DataFrame,
                            generator_parameters_df: pd.DataFrame) -> dict:
    """End-to-end Wind+Diesel pipeline — reuses the exact same generic deficit-driven generator-sizing
    math as Solar+Diesel (core.solar_pv), just fed by wind generation instead of solar generation."""
    demand, wind_speed_hub = _wind_speed_at_hub(hourly_profile_df, wind_speed_df, wind_parameters_df)
    turbine_count = float(get_param(wind_parameters_df, "turbine_count"))
    rated_power_kw = float(power_curve_df["power_kw"].max())
    wind_installed_capacity_kw = rated_power_kw * turbine_count
    egen = compute_wind_egen(wind_speed_hub, power_curve_df, turbine_count)
    deficit = spv.compute_deficit_wh(demand, egen)

    unit_size_kw = float(get_param(generator_parameters_df, "generator_unit_size_kw"))
    count = float(get_param(generator_parameters_df, "generator_count"))
    margin_pct = float(get_param(generator_parameters_df, "capacity_margin_pct"))
    rounding_increment_kw = float(get_param(generator_parameters_df, "rounding_increment_kw"))
    fuel_l_per_kwh = float(get_param(generator_parameters_df, "fuel_consumption_l_per_kwh"))
    fuel_price = float(get_param(generator_parameters_df, "fuel_price_eur_per_liter"))

    sizing = spv.recommend_generator_size(deficit, margin_pct, rounding_increment_kw)
    installed_capacity_kw = unit_size_kw * count
    dispatch = spv.dispatch_generator(deficit, installed_capacity_kw)
    fuel = spv.compute_fuel_liters_and_cost(dispatch["generator_output_wh"], fuel_l_per_kwh, fuel_price)

    simulation = pd.DataFrame({
        "hour_of_year": demand.index,
        "demand_wh": demand.values,
        "wind_speed_ms": wind_speed_hub.values,
        "egen_wh": egen.values,
        "deficit_wh": deficit.values,
        "generator_output_wh": dispatch["generator_output_wh"].values,
    })

    sizing_results = {
        "annual_egen_wh": float(egen.sum()), "annual_demand_wh": float(demand.sum()),
        "peak_deficit_w": float(sizing["peak_deficit_w"]), "recommended_generator_kw": sizing["recommended_generator_kw"],
        "generator_unit_size_kw": unit_size_kw, "generator_count": count, "installed_capacity_kw": installed_capacity_kw,
        "unmet_hours": dispatch["unmet_hours"], "unserved_energy_wh": float(dispatch["unserved_energy_wh"]),
        "annual_generator_output_wh": float(dispatch["generator_output_wh"].sum()),
        "annual_fuel_liters": fuel["annual_fuel_liters"], "annual_fuel_cost_eur": fuel["annual_fuel_cost_eur"],
        "turbine_count": turbine_count, "rated_power_kw": rated_power_kw,
        "wind_installed_capacity_kw": wind_installed_capacity_kw,
    }
    return {"simulation": simulation, "results": sizing_results, "deficit": deficit}


def save_wind_diesel_sizing_results(simulation: pd.DataFrame, results: dict) -> None:
    simulation.to_csv(DATA_DIR / "wind_diesel_simulation_2026.csv", index=False)
    df = pd.DataFrame([
        {"result": "annual_egen_wh", "value": results["annual_egen_wh"], "unit": "Wh", "description": "Total annual wind generation at the selected turbine count"},
        {"result": "annual_demand_wh", "value": results["annual_demand_wh"], "unit": "Wh", "description": "Total annual demand"},
        {"result": "peak_deficit_w", "value": results["peak_deficit_w"], "unit": "W", "description": "Worst single-hour shortfall wind alone can't cover — drives generator sizing"},
        {"result": "recommended_generator_kw", "value": results["recommended_generator_kw"], "unit": "kW", "description": "Recommended total generator capacity (peak deficit + safety margin, rounded up)"},
        {"result": "generator_unit_size_kw", "value": results["generator_unit_size_kw"], "unit": "kW", "description": "Size of a single generator unit, as configured"},
        {"result": "generator_count", "value": results["generator_count"], "unit": "units", "description": "Number of generator units, as configured"},
        {"result": "installed_capacity_kw", "value": results["installed_capacity_kw"], "unit": "kW", "description": "Total installed GENERATOR capacity (unit size x count)"},
        {"result": "unmet_hours", "value": results["unmet_hours"], "unit": "hours/year", "description": "Hours per year where wind + generator together still can't cover demand (unserved) — the diesel scenario's equivalent of zero-yield hours"},
        {"result": "unserved_energy_wh", "value": results["unserved_energy_wh"], "unit": "Wh", "description": "Total annual energy shortfall during unmet hours"},
        {"result": "annual_generator_output_wh", "value": results["annual_generator_output_wh"], "unit": "Wh", "description": "Total annual generator output"},
        {"result": "annual_fuel_liters", "value": results["annual_fuel_liters"], "unit": "L", "description": "Total annual diesel fuel consumption"},
        {"result": "annual_fuel_cost_eur", "value": results["annual_fuel_cost_eur"], "unit": "EUR", "description": "Total annual diesel fuel cost"},
        {"result": "turbine_count", "value": results["turbine_count"], "unit": "units", "description": "Number of turbines, as configured"},
        {"result": "rated_power_kw", "value": results["rated_power_kw"], "unit": "kW", "description": "Selected turbine's rated (plateau) power, per unit"},
        {"result": "wind_installed_capacity_kw", "value": results["wind_installed_capacity_kw"], "unit": "kW", "description": "Total installed TURBINE capacity (rated power x turbine count) — drives the BOQ's Wind Turbine(s) line and part of O&M"},
    ])
    df.to_csv(DATA_DIR / "wind_diesel_sizing_results_2026.csv", index=False)


# --- Excel round-trip: custom power curve ---

def export_custom_curve_template(output_path) -> None:
    template = pd.DataFrame({"wind_speed_ms": np.arange(0, 25.5, 0.5), "power_kw": [None] * 51})
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "Fill in power_kw for each wind_speed_ms row with your own turbine's published power curve (kW output at that wind speed).",
            "Leave power_kw blank for any wind speed your turbine doesn't reach (e.g. below cut-in or above cut-out) — it will be treated as 0 kW.",
            "Do not add/remove rows or rename columns — the app matches them by name on re-upload.",
            "Save the file, then upload it in the app to use this curve instead of a library turbine.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        template.to_excel(writer, sheet_name="Power Curve", index=False)

        for sheet_name, df in [("Instructions", instructions), ("Power Curve", template)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                ws.set_column(col_idx, col_idx, max(14, len(str(col_name)) + 2))


def import_custom_curve_template(input_path) -> dict:
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)
    if "Power Curve" not in sheets:
        return {"data": None, "errors": ["Missing required sheet: 'Power Curve'"]}

    df = sheets["Power Curve"]
    required_cols = ["wind_speed_ms", "power_kw"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        errors.append(f"'Power Curve' sheet is missing column(s): {missing}")

    if not errors:
        df["power_kw"] = df["power_kw"].fillna(0)
        if (df["power_kw"] < 0).any():
            errors.append("Some power_kw value(s) are negative, which isn't physically valid")
        if (df["wind_speed_ms"] < 0).any():
            errors.append("Some wind_speed_ms value(s) are negative, which isn't physically valid")
        if df["wind_speed_ms"].duplicated().any():
            errors.append("Duplicate wind_speed_ms value(s) found")

    if errors:
        return {"data": None, "errors": errors}
    return {"data": df[required_cols].sort_values("wind_speed_ms").reset_index(drop=True), "errors": []}
