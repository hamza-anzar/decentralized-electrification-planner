"""Step 4 — Solar Resource & PV/Battery Sizing.

Ported from notebooks/04_Solar_Resource_and_PV_Battery_Sizing.ipynb (Egen/battery formulas validated
there against the source workbook's Annex-IV: Egen 3,839,823,405 Wh; battery 8,000 kWh; zero-yield
hours 384 at the workbook's own demand+0.90 factor). Live PVGIS/NASA POWER calls are included as in
the notebook — this cloud sandbox can't reach either (see docs/PROJECT_LOG.md), so both need
confirming on a normal-internet machine; the default/offline dataset and Excel upload always work.
"""
import pandas as pd
import numpy as np
import requests

from .paths import DATA_DIR

# Default project site: Shamspir (Shams Pir Island), Keamari, Karachi — only a starting default; the
# whole point of this page is that the user can change lat/lon to their own project site.
DEFAULT_LAT = 24.843
DEFAULT_LON = 66.919

SOLAR_API_CONFIG_PATH = DATA_DIR / "solar-api.txt"

_YEAR_DATES = pd.date_range("2026-01-01", periods=365, freq="D")
MONTH_DAY_HOUR_TO_HOUR_OF_YEAR = {
    (d.month, d.day, h): (i * 24) + h + 1
    for i, d in enumerate(_YEAR_DATES) for h in range(24)
}


def load_default_irradiance() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_irradiance_2026.csv")


def load_default_pv_parameters() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "default_pv_parameters.csv")


def get_param(parameters_df: pd.DataFrame, name: str):
    """Look up one parameter's value by name from a parameters table (default or user-edited)."""
    return parameters_df.loc[parameters_df["parameter"] == name, "value"].iloc[0]


def standardize_to_project_year(df: pd.DataFrame, month_col: str, day_col: str, hour_col: str, value_col: str) -> pd.DataFrame:
    """Map a (month, day, hour, value) table from any real calendar year onto this project's hour_of_year (1-8760).
    Feb 29 (leap years) is dropped; values for the same (month, day, hour) are averaged if more than one year is present."""
    df = df[~((df[month_col] == 2) & (df[day_col] == 29))].copy()
    df["hour_of_year"] = df.apply(lambda r: MONTH_DAY_HOUR_TO_HOUR_OF_YEAR.get((r[month_col], r[day_col], r[hour_col])), axis=1)
    df = df.dropna(subset=["hour_of_year"])
    df["hour_of_year"] = df["hour_of_year"].astype(int)
    return df.groupby("hour_of_year", as_index=False)[value_col].mean()


def fetch_pvgis_hourly(lat: float, lon: float, year: int = 2020, timeout: int = 30) -> dict:
    """Fetch one year of hourly global irradiance G(i), in W/m2, from PVGIS for the given site."""
    url = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
    params = {"lat": lat, "lon": lon, "startyear": year, "endyear": year, "components": 0, "outputformat": "json"}

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as e:
        return {"data": None, "errors": [f"PVGIS request failed: {e}"]}
    except ValueError as e:
        return {"data": None, "errors": [f"PVGIS returned an unparseable response: {e}"]}

    hourly = payload.get("outputs", {}).get("hourly")
    if not hourly:
        return {"data": None, "errors": ["PVGIS response had no 'outputs.hourly' data — check lat/lon are within its coverage area"]}

    raw = pd.DataFrame(hourly)
    time_parts = raw["time"].str.extract(r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2}):(?P<hour>\d{2})")
    raw["month"] = time_parts["month"].astype(int)
    raw["day"] = time_parts["day"].astype(int)
    raw["hour"] = time_parts["hour"].astype(int)
    raw["ghi_wm2"] = raw["G(i)"]

    standardized = standardize_to_project_year(raw, "month", "day", "hour", "ghi_wm2")
    return {"data": standardized, "errors": []}


def fetch_nasa_power_hourly(lat: float, lon: float, year: int = 2020, timeout: int = 60) -> dict:
    """Fetch one year of hourly all-sky surface shortwave irradiance (W/m2) from NASA POWER for the given site."""
    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN", "community": "RE",
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
        series = payload["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    except KeyError:
        return {"data": None, "errors": ["NASA POWER response was missing the expected data — check lat/lon are valid"]}

    raw = pd.DataFrame({"timestamp": list(series.keys()), "ghi_wm2": list(series.values())})
    raw["month"] = raw["timestamp"].str.slice(4, 6).astype(int)
    raw["day"] = raw["timestamp"].str.slice(6, 8).astype(int)
    raw["hour"] = raw["timestamp"].str.slice(8, 10).astype(int)
    raw = raw[raw["ghi_wm2"] > -900]  # NASA POWER uses -999 as a "no data" fill value

    standardized = standardize_to_project_year(raw, "month", "day", "hour", "ghi_wm2")
    return {"data": standardized, "errors": []}


def load_custom_api_config(path=None) -> dict:
    """Parse the simple 'key = value' config file used for a custom solar-irradiance API."""
    path = path or SOLAR_API_CONFIG_PATH
    if not path.exists():
        return {}
    config = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        config[key.strip()] = value.strip()
    return config


def get_solar_resource(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, year: int = 2020,
                        source: str = "pvgis", fallback_to_default: bool = True) -> dict:
    """
    Get an 8,760-hour irradiance profile [hour_of_year, ghi_wm2] for (lat, lon).
    source: "pvgis" (default), "nasa_power", "custom" (reads data/solar-api.txt), or "default" (the bundled dataset, no network).
    """
    errors = []
    default_irradiance = load_default_irradiance()

    if source == "default":
        return {"data": default_irradiance.copy(), "source_used": "default (bundled)", "errors": []}
    elif source == "pvgis":
        result = fetch_pvgis_hourly(lat, lon, year)
    elif source == "nasa_power":
        result = fetch_nasa_power_hourly(lat, lon, year)
    elif source == "custom":
        config = load_custom_api_config()
        if not config.get("base_url") or not config.get("api_key"):
            result = {"data": None, "errors": ["No custom API configured — fill in data/solar-api.txt (base_url and api_key) first"]}
        else:
            try:
                response = requests.get(config["base_url"], params={"api_key": config["api_key"], "latitude": lat, "longitude": lon}, timeout=30)
                response.raise_for_status()
                result = {"data": None, "errors": [f"Custom API '{config.get('provider_name', 'unknown')}' responded, but this project doesn't yet know how to parse its response format — add a small parser once you've signed up and can see a real response."]}
            except requests.exceptions.RequestException as e:
                result = {"data": None, "errors": [f"Custom API request failed: {e}"]}
    else:
        result = {"data": None, "errors": [f"Unknown source '{source}'. Choose one of: pvgis, nasa_power, custom, default"]}

    if result["data"] is not None:
        return {"data": result["data"], "source_used": source, "errors": result["errors"]}

    errors.extend(result["errors"])
    if fallback_to_default:
        errors.append(f"Falling back to the bundled default irradiance dataset (source '{source}' was unavailable).")
        return {"data": default_irradiance.copy(), "source_used": "default (fallback)", "errors": errors}
    return {"data": None, "source_used": None, "errors": errors}


def compute_egen(ghi_wm2: pd.Series, ppeak_w: float, Q: float, Iqc: float) -> pd.Series:
    """Hourly PV generation (Wh), per Annex-IV's model: Ppeak(W) x [G(i)/1000 kW/m2] x Q / Iqc."""
    return ppeak_w * (ghi_wm2 / 1000) * Q / Iqc


def compute_delta_e_and_blocks(demand_wh: pd.Series, egen_wh: pd.Series) -> pd.DataFrame:
    """
    Compute hourly Delta-E (generation - demand) and group consecutive same-sign hours into 'blocks'
    (Annex-IV's Sign/Block-ID/SDE columns O/P/M). Returns delta_e_wh, sign, and block_id columns.
    """
    delta_e_wh = (egen_wh - demand_wh).reset_index(drop=True)
    sign = np.sign(delta_e_wh)

    block_id = np.empty(len(sign), dtype=int)
    block_id[0] = 1
    for i in range(1, len(sign)):
        block_id[i] = block_id[i - 1] + (1 if sign.iloc[i] != sign.iloc[i - 1] else 0)

    return pd.DataFrame({"delta_e_wh": delta_e_wh, "sign": sign, "block_id": block_id})


def block_sums(blocks_df: pd.DataFrame) -> pd.Series:
    """Sum delta_e_wh within each contiguous block (Annex-IV's SDE column M, one value per block)."""
    return blocks_df.groupby("block_id")["delta_e_wh"].sum()


def mround(value: float, multiple: float) -> float:
    """Round to the nearest multiple (Excel's MROUND, which Python's builtin round() doesn't do)."""
    return multiple * round(value / multiple)


def size_battery(worst_deficit_wh: float, dod: float, quality_factor: float) -> float:
    """Battery capacity (kWh) from the worst single-block deficit, rounded to the nearest 1,000 kWh."""
    deficit_kwh = -worst_deficit_wh / 1000
    return mround(deficit_kwh / dod * quality_factor, 1000)


def simulate_battery_soc(delta_e_wh: pd.Series, capacity_kwh: float) -> np.ndarray:
    """
    Simulate battery state-of-charge (Wh) hour by hour: SOC clipped between 0 (empty) and full capacity,
    starting from a full battery. Inherently sequential because of the clipping (can't vectorize with cumsum).
    """
    capacity_wh = capacity_kwh * 1000
    delta_e_wh = delta_e_wh.reset_index(drop=True).values
    soc = np.empty(len(delta_e_wh))
    soc[0] = max(0, min(capacity_wh, capacity_wh + delta_e_wh[0]))
    for i in range(1, len(delta_e_wh)):
        soc[i] = max(0, min(capacity_wh, soc[i - 1] + delta_e_wh[i]))
    return soc


def count_zero_yield_hours(soc_wh: np.ndarray) -> int:
    """Hours where the battery is fully depleted (SOC == 0) — unserved demand."""
    return int((soc_wh == 0).sum())


def battery_size_sensitivity(delta_e_wh: pd.Series, candidate_sizes_kwh) -> pd.DataFrame:
    """For each candidate battery size (kWh), simulate the full year and report the resulting zero-yield-hours count."""
    results = []
    for size_kwh in candidate_sizes_kwh:
        soc = simulate_battery_soc(delta_e_wh, size_kwh)
        results.append({"battery_kwh": size_kwh, "zero_yield_hours": count_zero_yield_hours(soc)})
    return pd.DataFrame(results)


def run_pv_battery_sizing(hourly_profile_df: pd.DataFrame, irradiance_df: pd.DataFrame, pv_parameters_df: pd.DataFrame) -> dict:
    """End-to-end Step 4 pipeline: demand + irradiance + parameters -> Egen, deficit blocks, battery size, SOC, zero-yield hours."""
    demand = hourly_profile_df.set_index("hour_of_year")["total_wh"]
    ghi = irradiance_df.set_index("hour_of_year")["ghi_wm2"]

    Q = get_param(pv_parameters_df, "performance_ratio_Q")
    Iqc = get_param(pv_parameters_df, "reference_irradiance_iqc_kwm2")
    ppeak_w = get_param(pv_parameters_df, "ppeak_w")
    dod = get_param(pv_parameters_df, "battery_dod")
    quality_factor = get_param(pv_parameters_df, "battery_quality_factor")

    egen = compute_egen(ghi, ppeak_w, Q, Iqc)
    blocks = compute_delta_e_and_blocks(demand, egen)
    sums = block_sums(blocks)
    worst_block = sums.min()

    battery_kwh = size_battery(worst_block, dod, quality_factor)
    soc = simulate_battery_soc(blocks["delta_e_wh"], battery_kwh)
    zero_hours = count_zero_yield_hours(soc)

    simulation = pd.DataFrame({
        "hour_of_year": demand.index,
        "demand_wh": demand.values,
        "ghi_wm2": ghi.values,
        "egen_wh": egen.values,
        "delta_e_wh": blocks["delta_e_wh"].values,
        "block_id": blocks["block_id"].values,
        "battery_soc_wh": soc,
    })

    sizing_results = {
        "annual_egen_wh": egen.sum(), "annual_demand_wh": demand.sum(),
        "worst_deficit_block_wh": worst_block, "battery_capacity_kwh": battery_kwh,
        "zero_yield_hours": zero_hours,
    }
    return {"simulation": simulation, "results": sizing_results, "blocks": blocks}


def save_results(simulation: pd.DataFrame, results: dict) -> None:
    simulation.to_csv(DATA_DIR / "pv_battery_simulation_2026.csv", index=False)
    pv_battery_sizing_results = pd.DataFrame([
        {"result": "annual_egen_wh", "value": results["annual_egen_wh"], "unit": "Wh", "description": "Total annual PV generation at the selected Ppeak"},
        {"result": "annual_demand_wh", "value": results["annual_demand_wh"], "unit": "Wh", "description": "Total annual demand"},
        {"result": "worst_deficit_block_wh", "value": results["worst_deficit_block_wh"], "unit": "Wh", "description": "Worst single contiguous deficit run — drives battery sizing"},
        {"result": "battery_capacity_kwh", "value": results["battery_capacity_kwh"], "unit": "kWh", "description": "Sized battery capacity"},
        {"result": "zero_yield_hours", "value": results["zero_yield_hours"], "unit": "hours/year", "description": "Hours per year the battery is fully depleted (unserved demand) at the sized capacity"},
    ])
    pv_battery_sizing_results.to_csv(DATA_DIR / "pv_battery_sizing_results_2026.csv", index=False)


# --- Excel round-trip: irradiance ---

def export_irradiance_template(irradiance_df: pd.DataFrame, output_path) -> None:
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "One row per hour of the year (hour_of_year 1-8760, matching every other hourly table in this project).",
            "ghi_wm2 is the global horizontal irradiance for that hour, in W/m2 (0 at night, up to ~1000+ at solar noon on a clear day).",
            "Do not add/remove rows or rename columns — the app matches them by name on re-upload.",
            "Save the file, then re-upload it in the app to use this data instead of the default or a live API fetch.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        irradiance_df.to_excel(writer, sheet_name="Irradiance", index=False)

        for sheet_name, df in [("Instructions", instructions), ("Irradiance", irradiance_df)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                ws.set_column(col_idx, col_idx, max(12, len(str(col_name)) + 2))


def import_irradiance_template(input_path) -> dict:
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)

    if "Irradiance" not in sheets:
        return {"data": None, "errors": ["Missing required sheet: 'Irradiance'"]}

    df = sheets["Irradiance"]
    required_cols = ["hour_of_year", "ghi_wm2"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        errors.append(f"'Irradiance' sheet is missing column(s): {missing}")

    if not errors:
        if len(df) != 8760:
            errors.append(f"Expected 8760 rows (one per hour of the year), found {len(df)}")
        if df["hour_of_year"].duplicated().any():
            errors.append("Duplicate hour_of_year value(s) found")
        if set(df["hour_of_year"]) != set(range(1, 8761)):
            errors.append("hour_of_year does not cover exactly 1-8760 with no gaps")
        if (df["ghi_wm2"] < 0).any():
            errors.append("Some ghi_wm2 value(s) are negative, which isn't physically valid")

    if errors:
        return {"data": None, "errors": errors}
    return {"data": df[["hour_of_year", "ghi_wm2"]].sort_values("hour_of_year").reset_index(drop=True), "errors": []}


# --- Excel round-trip: PV parameters ---

def export_pv_parameters_template(parameters_df: pd.DataFrame, output_path) -> None:
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "Edit the 'value' column only — do not add/remove/rename parameter rows, the app matches them by name on re-upload.",
            "performance_ratio_Q and battery_quality_factor are two DIFFERENT parameters that happen to share the same default (0.85) — see each row's description.",
            "Save the file, then re-upload it in the app to use these values instead of the defaults.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        parameters_df.to_excel(writer, sheet_name="PV Parameters", index=False)

        for sheet_name, df in [("Instructions", instructions), ("PV Parameters", parameters_df)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                ws.set_column(col_idx, col_idx, max(14, len(str(col_name)) + 2))


def import_pv_parameters_template(input_path) -> dict:
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)
    if "PV Parameters" not in sheets:
        return {"data": None, "errors": ["Missing required sheet: 'PV Parameters'"]}

    df = sheets["PV Parameters"]
    required_cols = ["parameter", "value", "unit", "description"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        errors.append(f"'PV Parameters' sheet is missing column(s): {missing}")

    if not errors:
        default_pv_parameters = load_default_pv_parameters()
        expected_params = set(default_pv_parameters["parameter"])
        if set(df["parameter"]) != expected_params:
            errors.append(f"'parameter' column must contain exactly these rows: {sorted(expected_params)}")
        if (df["value"] <= 0).any():
            errors.append("All parameter values must be positive")
        fraction_params = {"performance_ratio_Q", "battery_dod", "battery_quality_factor"}
        bad_fractions = df[df["parameter"].isin(fraction_params) & (df["value"] > 1)]
        if len(bad_fractions) > 0:
            errors.append(f"These fraction-type parameters must be <= 1: {bad_fractions['parameter'].tolist()}")

    if errors:
        return {"data": None, "errors": errors}
    return {"data": df[required_cols], "errors": []}
