"""REST API for the Rural Electrification Planner, wrapping the pure-pandas calculation modules in
backend/core/ (ported unchanged from the original notebooks/Streamlit app's app/core/) so a React
frontend can drive the same validated engineering/financial calculations. Every endpoint accepts and
returns plain JSON (list-of-row-dicts for tables), converted via backend/utils.native()/clean_records().
"""
import io
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core import load_estimation as le
from core import load_profile as lp
from core import solar_pv as spv
from core import cost_lcoe as cl
from core import summary_roi as sr
from core import site_info as si
from core import export_report as er
from core.paths import DATA_DIR
from utils import native, clean_records

router = APIRouter(prefix="/api")

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(build_fn, filename: str) -> StreamingResponse:
    """Run an export_*_template(..., output_path)-style function against an in-memory buffer and
    stream it back as a file download."""
    buffer = io.BytesIO()
    build_fn(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# ---------------------------------------------------------------------------
# Site info
# ---------------------------------------------------------------------------

_SITE_FIELD_META = {
    "project_name": ("", "Name of the project / site"),
    "country": ("", "Country"),
    "region_city_village": ("", "City / village / region name"),
    "latitude": ("degrees N", "Site latitude (also used by the Solar Design page)"),
    "longitude": ("degrees E", "Site longitude (also used by the Solar Design page)"),
    "population": ("people", "Total population at the site (independent of household count — used for per-capita figures)"),
    "area_km2": ("km2", "Approximate site/service area"),
    "weather_type": ("", "General climate classification (e.g. coastal, arid, temperate)"),
    "socioeconomic_class": ("", "Broad socio-economic description of the served population"),
    "gdp_per_capita_usd": ("USD/person/year", "Reference GDP per capita, for later socio-economic analysis"),
    "electrification_pct": ("%", "Current grid electrification rate at the site before this project (0 = fully off-grid)"),
}


@router.get("/site-info")
def get_site_info():
    return si.as_dict(si.load_defaults())


@router.post("/site-info")
def save_site_info(payload: dict[str, Any]):
    rows = [
        {"field": k, "value": v, "unit": _SITE_FIELD_META.get(k, ("", ""))[0], "description": _SITE_FIELD_META.get(k, ("", ""))[1]}
        for k, v in payload.items()
    ]
    df = pd.DataFrame(rows)
    si.save(df)
    return si.as_dict(df)


# ---------------------------------------------------------------------------
# 1. Load Setup
# ---------------------------------------------------------------------------

class LoadSetupPayload(BaseModel):
    householdCategories: list[dict[str, Any]]
    appliances: list[dict[str, Any]]
    miscLoads: list[dict[str, Any]]


@router.get("/load-setup/defaults")
def load_setup_defaults():
    d = le.load_defaults()
    return {
        "householdCategories": clean_records(d["household_categories"]),
        "appliances": clean_records(d["appliances"]),
        "miscLoads": clean_records(d["misc_loads"]),
    }


def _compute_load_setup(payload: LoadSetupPayload):
    hh = pd.DataFrame(payload.householdCategories)
    appl = pd.DataFrame(payload.appliances)
    misc = pd.DataFrame(payload.miscLoads)
    result = le.compute_connected_load(appl, hh, misc)
    return hh, appl, misc, result


@router.post("/load-setup/compute")
def load_setup_compute(payload: LoadSetupPayload):
    _, _, _, result = _compute_load_setup(payload)
    return native(result)


@router.post("/load-setup/save")
def load_setup_save(payload: LoadSetupPayload):
    hh, appl, misc, result = _compute_load_setup(payload)
    le.save_results(result["total_w"], result["by_category"])
    hh.to_csv(DATA_DIR / "default_household_categories.csv", index=False)
    appl.to_csv(DATA_DIR / "default_appliances.csv", index=False)
    misc.to_csv(DATA_DIR / "default_misc_loads.csv", index=False)
    return native(result)


# ---------------------------------------------------------------------------
# 2. Demand Profile
# ---------------------------------------------------------------------------

class DemandProfilePayload(BaseModel):
    seasonPeriods: list[dict[str, Any]]
    publicHolidays: list[dict[str, Any]]
    festivalHolidays: list[dict[str, Any]]
    daytypeProfiles: list[dict[str, Any]]
    appliances: list[dict[str, Any]]
    miscLoads: list[dict[str, Any]]
    householdCategories: list[dict[str, Any]]
    demandSettings: dict[str, Any] = {"project_start_year": 2026, "project_duration_years": 30, "annual_load_growth_pct": 3.0}


@router.get("/demand-profile/defaults")
def demand_profile_defaults():
    d = lp.load_defaults()
    return {
        "daytypeProfiles": clean_records(d["daytype_profiles"]),
        "seasonPeriods": clean_records(d["season_periods"]),
        "publicHolidays": clean_records(d["public_holidays"]),
        "festivalHolidays": clean_records(d["festival_holidays"]),
        "demandSettings": d["demand_settings"],
    }


@router.post("/demand-profile/validate")
def demand_profile_validate(payload: dict[str, Any]):
    sp = pd.DataFrame(payload["seasonPeriods"])
    year = int(payload.get("projectStartYear") or 2026)
    errors = lp.validate_season_periods(sp, year)
    period_day_counts = [] if errors else clean_records(lp.count_period_daytype_days(sp, year))
    return {"errors": errors, "periodDayCounts": period_day_counts}


_HOURLY_COLUMNS = ["hour_of_year", "day", "date", "A_wh", "B_wh", "C_wh", "Misc_wh", "total_wh"]


def _compute_demand_profile(payload: DemandProfilePayload):
    sp = pd.DataFrame(payload.seasonPeriods)
    year = int(payload.demandSettings.get("project_start_year") or 2026)
    errors = lp.validate_season_periods(sp, year)
    if errors:
        raise HTTPException(400, {"errors": errors})
    ph = pd.DataFrame(payload.publicHolidays)
    fh = pd.DataFrame(payload.festivalHolidays)
    dtp = pd.DataFrame(payload.daytypeProfiles)
    appl = pd.DataFrame(payload.appliances)
    misc = pd.DataFrame(payload.miscLoads)
    hh = pd.DataFrame(payload.householdCategories)
    full = lp.compute_full_profile(year, sp, ph, fh, dtp, appl, misc, hh)
    return sp, ph, fh, dtp, full


@router.post("/demand-profile/compute")
def demand_profile_compute(payload: DemandProfilePayload):
    _, _, _, _, full = _compute_demand_profile(payload)
    hourly = full["hourly_profile"]
    cols = [c for c in _HOURLY_COLUMNS if c in hourly.columns]
    return {"hourlyProfile": clean_records(hourly[cols]), "annualWh": native(hourly["total_wh"].sum())}


@router.post("/demand-profile/save")
def demand_profile_save(payload: DemandProfilePayload):
    sp, ph, fh, dtp, full = _compute_demand_profile(payload)
    hourly = full["hourly_profile"]
    lp.save_results(full["calendar"], hourly)
    sp.to_csv(DATA_DIR / "default_season_periods.csv", index=False)
    ph.to_csv(DATA_DIR / "default_public_holidays.csv", index=False)
    fh.to_csv(DATA_DIR / "default_festival_holidays.csv", index=False)
    dtp.to_csv(DATA_DIR / "default_daytype_profiles.csv", index=False)
    lp.save_demand_settings(payload.demandSettings)
    cols = [c for c in _HOURLY_COLUMNS if c in hourly.columns]
    return {"hourlyProfile": clean_records(hourly[cols]), "annualWh": native(hourly["total_wh"].sum())}


@router.get("/demand-profile/hourly")
def demand_profile_hourly():
    """The last-saved hourly profile (used by Energy Insights / Solar Design without recomputing)."""
    path = DATA_DIR / "hourly_load_profile_2026.csv"
    if not path.exists():
        raise HTTPException(400, {"errors": ["No saved demand profile yet — visit Demand Profile and save one first."]})
    hourly = pd.read_csv(path)
    cols = [c for c in _HOURLY_COLUMNS if c in hourly.columns]
    settings = lp.load_demand_settings()
    return {
        "hourlyProfile": clean_records(hourly[cols]),
        "annualWh": native(hourly["total_wh"].sum()),
        "settings": {
            "projectStartYear": settings["project_start_year"],
            "projectDurationYears": settings["project_duration_years"],
            "annualLoadGrowthPct": settings["annual_load_growth_pct"],
        },
    }


@router.get("/demand-profile/hourly-template")
def demand_profile_hourly_template():
    """Blank Date/Hour/Load_kWh workbook — fill in your own 8,760-hour profile and re-upload it below
    to bypass season/day-type/calendar entirely."""
    return _xlsx_response(lambda buf: lp.export_hourly_profile_template(buf), "Hourly_Load_Profile_Template.xlsx")


@router.post("/demand-profile/hourly-upload")
def demand_profile_hourly_upload(file: UploadFile = File(...)):
    """Upload a filled-in hourly-profile workbook and use it directly, in place of the computed
    season/day-type profile. Saves immediately (no separate Save step, since there's nothing else to
    compute) — every category-level breakdown (e.g. Results' per-category billing estimate) is
    unavailable against an uploaded profile, since it carries only a total per hour, not a per-category one."""
    result = lp.import_hourly_profile(io.BytesIO(file.file.read()))
    if result["errors"]:
        raise HTTPException(400, {"errors": result["errors"]})
    hourly = lp.finalize_uploaded_hourly_profile(result["hourly_profile"])
    hourly.to_csv(DATA_DIR / "hourly_load_profile_2026.csv", index=False)
    cols = [c for c in _HOURLY_COLUMNS if c in hourly.columns]
    return {"hourlyProfile": clean_records(hourly[cols]), "annualWh": native(hourly["total_wh"].sum()), "errors": []}


# ---------------------------------------------------------------------------
# 4. Solar Design
# ---------------------------------------------------------------------------

class FetchResourcePayload(BaseModel):
    lat: float
    lon: float
    source: str


class SolarComputePayload(BaseModel):
    pvParameters: list[dict[str, Any]]
    irradiance: Optional[list[dict[str, Any]]] = None
    manualBatteryKwh: Optional[float] = None


@router.get("/solar-design/defaults")
def solar_design_defaults():
    return {
        "irradiance": clean_records(spv.load_default_irradiance()),
        "pvParameters": clean_records(spv.load_default_pv_parameters()),
        "lat": spv.DEFAULT_LAT,
        "lon": spv.DEFAULT_LON,
    }


@router.post("/solar-design/fetch-resource")
def solar_design_fetch_resource(payload: FetchResourcePayload):
    result = spv.get_solar_resource(payload.lat, payload.lon, source=payload.source)
    return {
        "irradiance": clean_records(result["data"]) if result["data"] is not None else None,
        "sourceUsed": result["source_used"],
        "errors": result["errors"],
    }


@router.get("/solar-design/irradiance-template")
def solar_design_irradiance_template():
    """Blank hour_of_year/ghi_wm2 workbook, pre-filled with the currently-selected irradiance data."""
    irr = spv.load_default_irradiance()
    return _xlsx_response(lambda buf: spv.export_irradiance_template(irr, buf), "Irradiance_Template.xlsx")


@router.post("/solar-design/irradiance-upload")
def solar_design_irradiance_upload(file: UploadFile = File(...)):
    """Upload a filled-in irradiance workbook — same response shape as fetch-resource so the frontend
    can reuse its state-setting logic."""
    result = spv.import_irradiance_template(io.BytesIO(file.file.read()))
    if result["errors"]:
        return {"irradiance": None, "sourceUsed": None, "errors": result["errors"]}
    return {"irradiance": clean_records(result["data"]), "sourceUsed": "uploaded", "errors": []}


@router.get("/solar-design/recommended-size")
def solar_design_recommended_size():
    """Suggest a Ppeak from the saved connected-load and hourly-demand results (see solar_pv.recommend_ppeak_w)."""
    cl_path = DATA_DIR / "connected_load_results.csv"
    hourly_path = DATA_DIR / "hourly_load_profile_2026.csv"
    missing = [f.name for f in (cl_path, hourly_path) if not f.exists()]
    if missing:
        raise HTTPException(400, {"errors": [f"Missing saved result(s): {missing} — visit and save Load Setup and Demand Profile first."]})
    connected_load_w = pd.read_csv(cl_path).set_index("result")["value"]["total_connected_load_w"]
    peak_demand_w = pd.read_csv(hourly_path)["total_wh"].max()
    Q = spv.get_param(spv.load_default_pv_parameters(), "performance_ratio_Q")
    return native(spv.recommend_ppeak_w(connected_load_w, peak_demand_w, Q))


def _load_hourly_for_solar():
    path = DATA_DIR / "hourly_load_profile_2026.csv"
    if not path.exists():
        raise HTTPException(400, {"errors": ["No saved demand profile yet — visit Demand Profile and save one first."]})
    return pd.read_csv(path)


def _run_solar(payload: SolarComputePayload):
    hourly = _load_hourly_for_solar()
    irr = pd.DataFrame(payload.irradiance) if payload.irradiance else spv.load_default_irradiance()
    pvp = pd.DataFrame(payload.pvParameters)
    step4 = spv.run_pv_battery_sizing(hourly, irr, pvp, manual_battery_kwh=payload.manualBatteryKwh)
    candidate_sizes = list(range(1000, 16001, 1000))
    sensitivity = spv.battery_size_sensitivity(step4["blocks"]["delta_e_wh"], candidate_sizes)
    return irr, pvp, step4, sensitivity


@router.post("/solar-design/compute")
def solar_design_compute(payload: SolarComputePayload):
    _, _, step4, sensitivity = _run_solar(payload)
    sim_cols = ["hour_of_year", "demand_wh", "ghi_wm2", "egen_wh", "delta_e_wh", "battery_soc_wh"]
    return native({
        "simulation": step4["simulation"][sim_cols],
        "results": step4["results"],
        "sensitivity": sensitivity,
    })


@router.post("/solar-design/save")
def solar_design_save(payload: SolarComputePayload):
    irr, pvp, step4, sensitivity = _run_solar(payload)
    spv.save_results(step4["simulation"], step4["results"])
    pvp.to_csv(DATA_DIR / "default_pv_parameters.csv", index=False)
    irr.to_csv(DATA_DIR / "default_irradiance_2026.csv", index=False)
    sim_cols = ["hour_of_year", "demand_wh", "ghi_wm2", "egen_wh", "delta_e_wh", "battery_soc_wh"]
    return native({
        "simulation": step4["simulation"][sim_cols],
        "results": step4["results"],
        "sensitivity": sensitivity,
    })


# ---------------------------------------------------------------------------
# 4b. Solar Design — Diesel Generator scenario (irradiance is shared with 4. above)
# ---------------------------------------------------------------------------

class DieselPvComputePayload(BaseModel):
    pvParameters: list[dict[str, Any]]
    generatorParameters: list[dict[str, Any]]
    irradiance: Optional[list[dict[str, Any]]] = None


@router.get("/solar-diesel/defaults")
def solar_diesel_defaults():
    return {
        "pvParameters": clean_records(spv.load_default_pv_parameters_diesel()),
        "generatorParameters": clean_records(spv.load_default_diesel_generator_parameters()),
    }


@router.get("/solar-diesel/recommended-ppeak")
def solar_diesel_recommended_ppeak():
    """See solar_pv.recommend_ppeak_diesel_w() for the sizing methodology (sized to average daytime
    demand, since excess PV generation is curtailed without a battery)."""
    hourly = _load_hourly_for_solar()
    irr = spv.load_default_irradiance()
    pvp = spv.load_default_pv_parameters_diesel()
    Q = spv.get_param(pvp, "performance_ratio_Q")
    Iqc = spv.get_param(pvp, "reference_irradiance_iqc_kwm2")
    return native(spv.recommend_ppeak_diesel_w(hourly, irr, Q, Iqc))


def _run_diesel_solar(payload: DieselPvComputePayload):
    hourly = _load_hourly_for_solar()
    irr = pd.DataFrame(payload.irradiance) if payload.irradiance else spv.load_default_irradiance()
    pvp = pd.DataFrame(payload.pvParameters)
    genp = pd.DataFrame(payload.generatorParameters)
    step = spv.run_pv_diesel_sizing(hourly, irr, pvp, genp)
    return irr, pvp, genp, step


@router.post("/solar-diesel/compute")
def solar_diesel_compute(payload: DieselPvComputePayload):
    _, _, _, step = _run_diesel_solar(payload)
    return native({
        "simulation": step["simulation"],
        "results": step["results"],
        "loadDurationCurve": spv.deficit_load_duration(step["deficit"]),
    })


@router.post("/solar-diesel/save")
def solar_diesel_save(payload: DieselPvComputePayload):
    irr, pvp, genp, step = _run_diesel_solar(payload)
    spv.save_diesel_sizing_results(step["simulation"], step["results"])
    pvp.to_csv(DATA_DIR / "default_pv_parameters_diesel.csv", index=False)
    genp.to_csv(DATA_DIR / "default_diesel_generator_parameters.csv", index=False)
    irr.to_csv(DATA_DIR / "default_irradiance_2026.csv", index=False)
    return native({
        "simulation": step["simulation"],
        "results": step["results"],
        "loadDurationCurve": spv.deficit_load_duration(step["deficit"]),
    })


# ---------------------------------------------------------------------------
# 5. Financials
# ---------------------------------------------------------------------------

class FinancialsPayload(BaseModel):
    boqItems: list[dict[str, Any]]
    landCostOptions: list[dict[str, Any]]
    costParameters: list[dict[str, Any]]


@router.get("/financials/defaults")
def financials_defaults():
    d = cl.load_defaults()
    return {
        "boqItems": clean_records(d["boq_items"]),
        "landCostOptions": clean_records(d["land_cost_options"]),
        "costParameters": clean_records(d["cost_parameters"]),
    }


@router.get("/financials/template")
def financials_template():
    """BOQ + Land Cost Options + Cost Parameters in one workbook, pre-filled with the current defaults."""
    d = cl.load_defaults()
    return _xlsx_response(
        lambda buf: cl.export_cost_template(d["boq_items"], d["land_cost_options"], d["cost_parameters"], buf),
        "Cost_BOQ_Template.xlsx",
    )


@router.post("/financials/upload")
def financials_upload(file: UploadFile = File(...)):
    result = cl.import_cost_template(io.BytesIO(file.file.read()))
    if result["errors"]:
        return {"boqItems": None, "landCostOptions": None, "costParameters": None, "errors": result["errors"]}
    return {
        "boqItems": clean_records(result["boq_items"]),
        "landCostOptions": clean_records(result["land_cost_options"]),
        "costParameters": clean_records(result["cost_parameters"]),
        "errors": [],
    }


def _load_pv_context_for_financials():
    pv_results_path = DATA_DIR / "pv_battery_sizing_results_2026.csv"
    pv_params_path = DATA_DIR / "default_pv_parameters.csv"
    if not pv_results_path.exists():
        raise HTTPException(400, {"errors": ["No saved PV/battery sizing yet — visit Solar Design and save results first."]})
    pv_results = pd.read_csv(pv_results_path).set_index("result")["value"]
    pv_params = pd.read_csv(pv_params_path).set_index("parameter")["value"]
    return pv_results, pv_params


def _run_financials(payload: FinancialsPayload):
    boq = pd.DataFrame(payload.boqItems)
    land = pd.DataFrame(payload.landCostOptions)
    cost_params = pd.DataFrame(payload.costParameters)
    cost_params["value"] = cl.coerce_numeric_column(cost_params["value"])
    pv_results, pv_params = _load_pv_context_for_financials()
    result = cl.run_cost_lcoe_pipeline(boq, land, cost_params, pv_params["ppeak_w"],
                                        pv_results["battery_capacity_kwh"], pv_results["annual_egen_wh"])
    return boq, land, cost_params, result


@router.post("/financials/compute")
def financials_compute(payload: FinancialsPayload):
    _, _, cost_params, result = _run_financials(payload)
    eur_to_pkr = cl.get_param(cost_params, "eur_to_pkr_rate")
    eur_to_usd = cl.get_param(cost_params, "eur_to_usd_rate")
    return native({**result, "eurToPkr": eur_to_pkr, "eurToUsd": eur_to_usd})


@router.post("/financials/save")
def financials_save(payload: FinancialsPayload):
    boq, land, cost_params, result = _run_financials(payload)
    cl.save_results(result)
    boq.to_csv(DATA_DIR / "default_boq_items.csv", index=False)
    land.to_csv(DATA_DIR / "default_land_cost_options.csv", index=False)
    cost_params.to_csv(DATA_DIR / "default_cost_parameters.csv", index=False)
    eur_to_pkr = cl.get_param(cost_params, "eur_to_pkr_rate")
    eur_to_usd = cl.get_param(cost_params, "eur_to_usd_rate")
    return native({**result, "eurToPkr": eur_to_pkr, "eurToUsd": eur_to_usd})


# ---------------------------------------------------------------------------
# 5b. Financials — Diesel Generator scenario (land cost options are the shared file above)
# ---------------------------------------------------------------------------

class DieselFinancialsPayload(BaseModel):
    boqItems: list[dict[str, Any]]
    costParameters: list[dict[str, Any]]


@router.get("/financials-diesel/defaults")
def financials_diesel_defaults():
    d = cl.load_diesel_defaults()
    return {"boqItems": clean_records(d["boq_items"]), "costParameters": clean_records(d["cost_parameters"])}


@router.get("/financials-diesel/template")
def financials_diesel_template():
    d = cl.load_diesel_defaults()
    return _xlsx_response(
        lambda buf: cl.export_diesel_cost_template(d["boq_items"], d["cost_parameters"], buf),
        "Diesel_Cost_BOQ_Template.xlsx",
    )


@router.post("/financials-diesel/upload")
def financials_diesel_upload(file: UploadFile = File(...)):
    result = cl.import_diesel_cost_template(io.BytesIO(file.file.read()))
    if result["errors"]:
        return {"boqItems": None, "costParameters": None, "errors": result["errors"]}
    return {"boqItems": clean_records(result["boq_items"]), "costParameters": clean_records(result["cost_parameters"]), "errors": []}


def _load_diesel_pv_context_for_financials():
    pv_results_path = DATA_DIR / "pv_diesel_sizing_results_2026.csv"
    pv_params_path = DATA_DIR / "default_pv_parameters_diesel.csv"
    if not pv_results_path.exists():
        raise HTTPException(400, {"errors": ["No saved Solar+Diesel sizing yet — visit Solar Design's Diesel tab and save results first."]})
    pv_results = pd.read_csv(pv_results_path).set_index("result")["value"]
    pv_params = pd.read_csv(pv_params_path).set_index("parameter")["value"]
    return pv_results, pv_params


def _run_diesel_financials(payload: DieselFinancialsPayload):
    boq = pd.DataFrame(payload.boqItems)
    cost_params = pd.DataFrame(payload.costParameters)
    cost_params["value"] = cl.coerce_numeric_column(cost_params["value"])
    pv_diesel_results, pv_params = _load_diesel_pv_context_for_financials()
    land = pd.read_csv(DATA_DIR / "default_land_cost_options.csv")  # shared with the Battery scenario

    installed_capacity_kw = float(pv_diesel_results["installed_capacity_kw"])
    annual_fuel_cost_eur = float(pv_diesel_results["annual_fuel_cost_eur"])
    annual_energy_served_wh = float(pv_diesel_results["annual_demand_wh"]) - float(pv_diesel_results["unserved_energy_wh"])

    result = cl.run_diesel_cost_lcoe_pipeline(boq, land, cost_params, pv_params["ppeak_w"], installed_capacity_kw, annual_fuel_cost_eur, annual_energy_served_wh)
    return boq, cost_params, result


@router.post("/financials-diesel/compute")
def financials_diesel_compute(payload: DieselFinancialsPayload):
    _, cost_params, result = _run_diesel_financials(payload)
    eur_to_pkr = cl.get_param(cost_params, "eur_to_pkr_rate")
    eur_to_usd = cl.get_param(cost_params, "eur_to_usd_rate")
    return native({**result, "eurToPkr": eur_to_pkr, "eurToUsd": eur_to_usd})


@router.post("/financials-diesel/save")
def financials_diesel_save(payload: DieselFinancialsPayload):
    boq, cost_params, result = _run_diesel_financials(payload)
    cl.save_diesel_cost_results(result)
    boq.to_csv(DATA_DIR / "default_boq_items_diesel.csv", index=False)
    cost_params.to_csv(DATA_DIR / "default_cost_parameters_diesel.csv", index=False)
    eur_to_pkr = cl.get_param(cost_params, "eur_to_pkr_rate")
    eur_to_usd = cl.get_param(cost_params, "eur_to_usd_rate")
    return native({**result, "eurToPkr": eur_to_pkr, "eurToUsd": eur_to_usd})


# ---------------------------------------------------------------------------
# 6. Results
# ---------------------------------------------------------------------------

def _results_filenames(system_type: str) -> dict:
    """Which files back each half of a Results scenario. Shared regardless of system_type: connected
    load, the demand profile, and land cost options — the household load and available land don't
    change based on which generation technology is chosen."""
    if system_type == "diesel":
        return {
            "pv_parameters": "default_pv_parameters_diesel.csv", "pv_results": "pv_diesel_sizing_results_2026.csv",
            "cost_lcoe_results": "cost_lcoe_results_diesel_2026.csv", "cost_parameters": "default_cost_parameters_diesel.csv",
            "roi_parameters": "default_roi_parameters_diesel.csv", "roi_results": "roi_results_diesel_2026.csv",
            "master_summary": "master_summary_diesel_2026.csv", "boq_items": "default_boq_items_diesel.csv",
        }
    return {
        "pv_parameters": "default_pv_parameters.csv", "pv_results": "pv_battery_sizing_results_2026.csv",
        "cost_lcoe_results": "cost_lcoe_results_2026.csv", "cost_parameters": "default_cost_parameters.csv",
        "roi_parameters": "default_roi_parameters.csv", "roi_results": "roi_results_2026.csv",
        "master_summary": "master_summary_2026.csv", "boq_items": "default_boq_items.csv",
    }


def _load_results_context(system_type: str = "battery"):
    files = _results_filenames(system_type)
    required = ["connected_load_results.csv", "hourly_load_profile_2026.csv", "default_land_cost_options.csv",
                files["pv_results"], files["pv_parameters"], files["cost_lcoe_results"], files["cost_parameters"], files["boq_items"]]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    if missing:
        raise HTTPException(400, {"missing": missing})
    connected_load = pd.read_csv(DATA_DIR / "connected_load_results.csv").set_index("result")["value"]
    hourly_profile = pd.read_csv(DATA_DIR / "hourly_load_profile_2026.csv")
    annual_demand_wh = float(hourly_profile["total_wh"].sum())
    pv_results = pd.read_csv(DATA_DIR / files["pv_results"]).set_index("result")["value"]
    pv_parameters = pd.read_csv(DATA_DIR / files["pv_parameters"]).set_index("parameter")["value"]
    cost_lcoe_results = pd.read_csv(DATA_DIR / files["cost_lcoe_results"]).set_index("result")["value"]
    cost_parameters = pd.read_csv(DATA_DIR / files["cost_parameters"])
    cost_parameters["value"] = cl.coerce_numeric_column(cost_parameters["value"])
    land_cost_options = pd.read_csv(DATA_DIR / "default_land_cost_options.csv")
    boq_items = pd.read_csv(DATA_DIR / files["boq_items"])
    return {
        "connected_load": connected_load, "annual_demand_wh": annual_demand_wh,
        "pv_results": pv_results, "pv_parameters": pv_parameters,
        "cost_lcoe_results": cost_lcoe_results, "cost_parameters": cost_parameters,
        "land_cost_options": land_cost_options, "boq_items": boq_items, "files": files,
    }


@router.get("/results/context")
def results_context(system_type: str = "battery"):
    ctx = _load_results_context(system_type)
    site = si.as_dict(si.load_defaults())
    hh_path = DATA_DIR / "default_household_categories.csv"
    total_houses = int(pd.read_csv(hh_path)["household_count"].sum()) if hh_path.exists() else None
    roi_path = DATA_DIR / ctx["files"]["roi_parameters"]
    roi_parameters = pd.read_csv(roi_path) if roi_path.exists() else sr.build_default_roi_parameters(ctx["cost_lcoe_results"]["lcoe_eur_per_kwh"], system_type=system_type)
    return native({
        "systemType": system_type,
        "connectedLoad": ctx["connected_load"], "annualDemandWh": ctx["annual_demand_wh"],
        "pvResults": ctx["pv_results"], "pvParameters": ctx["pv_parameters"],
        "costLcoeResults": ctx["cost_lcoe_results"], "costParameters": ctx["cost_parameters"],
        "landCostOptions": ctx["land_cost_options"], "siteInfo": site, "totalHouses": total_houses,
        "roiParameters": roi_parameters,
        "projectLifetimeYears": int(cl.get_param(ctx["cost_parameters"], "project_lifetime_years")),
    })


class ResultsComputePayload(BaseModel):
    roiParameters: list[dict[str, Any]]
    comparePct: Optional[float] = None


def _run_results(payload: ResultsComputePayload, system_type: str = "battery"):
    ctx = _load_results_context(system_type)
    roi_params = pd.DataFrame(payload.roiParameters)

    def _scenario(params_df):
        if system_type == "diesel":
            return sr.run_diesel_roi_scenario(ctx["cost_parameters"], params_df, ctx["pv_results"],
                                               ctx["cost_lcoe_results"], ctx["land_cost_options"], ctx["annual_demand_wh"],
                                               ctx["boq_items"])
        return sr.run_roi_scenario(ctx["cost_parameters"], params_df, ctx["pv_parameters"], ctx["pv_results"],
                                    ctx["cost_lcoe_results"], ctx["land_cost_options"], ctx["annual_demand_wh"],
                                    ctx["boq_items"])

    scenario = _scenario(roi_params)
    cashflow = scenario["cashflow"]
    yearly_opex_eur = float(scenario["om_cash_flow"][0]) if len(scenario["om_cash_flow"]) else 0.0

    result = {"cashflow": cashflow, "yearlyOpexEur": yearly_opex_eur}

    if payload.comparePct:
        compare_params = roi_params.copy()
        compare_params.loc[compare_params["parameter"] == "electricity_tariff_eur_per_kwh", "value"] *= payload.comparePct / 100
        compare_scenario = _scenario(compare_params)
        result["compareCashflow"] = compare_scenario["cashflow"]
        result["compareTariffEur"] = cl.get_param(compare_params, "electricity_tariff_eur_per_kwh")

    if system_type == "diesel":
        master_summary = sr.build_diesel_master_summary(ctx["connected_load"], ctx["annual_demand_wh"], ctx["pv_parameters"],
                                                          ctx["pv_results"], ctx["cost_lcoe_results"], ctx["cost_parameters"],
                                                          roi_params, cashflow)
    else:
        master_summary = sr.build_master_summary(ctx["connected_load"], ctx["annual_demand_wh"], ctx["pv_parameters"],
                                                   ctx["pv_results"], ctx["cost_lcoe_results"], ctx["cost_parameters"],
                                                   roi_params, cashflow)
    result["masterSummary"] = master_summary
    return roi_params, master_summary, cashflow, result


@router.post("/results/compute")
def results_compute(payload: ResultsComputePayload, system_type: str = "battery"):
    _, _, _, result = _run_results(payload, system_type)
    return native(result)


@router.post("/results/save")
def results_save(payload: ResultsComputePayload, system_type: str = "battery"):
    roi_params, master_summary, cashflow, result = _run_results(payload, system_type)
    files = _results_filenames(system_type)
    if system_type == "diesel":
        sr.save_diesel_roi_results(roi_params, master_summary, cashflow)
    else:
        sr.save_results(roi_params, master_summary, cashflow)
    roi_params.to_csv(DATA_DIR / files["roi_parameters"], index=False)
    return native(result)


class BillingPayload(BaseModel):
    tariffMarkupPct: float = 20.0


@router.post("/results/billing")
def results_billing(payload: BillingPayload, system_type: str = "battery"):
    """Estimated monthly bill per household category and per community load, at tariff = LCOE x (1 + markup%).
    Needs the computed (day-type-based) demand profile — unavailable if Demand Profile used a direct
    hourly upload instead, since that carries no per-category breakdown. The per-category consumption
    breakdown itself doesn't depend on generation technology — only which LCOE (system_type) sets the tariff."""
    files = _results_filenames(system_type)
    required = ["annual_calendar_2026.csv", "default_daytype_profiles.csv", "default_appliances.csv",
                "default_misc_loads.csv", "default_household_categories.csv", files["cost_lcoe_results"]]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    if missing:
        raise HTTPException(400, {"errors": [
            f"Missing saved result(s): {missing}. This breakdown needs the computed demand profile "
            "(season/day-type based) and this scenario's saved LCOE."
        ]})

    calendar = pd.read_csv(DATA_DIR / "annual_calendar_2026.csv")
    daytype_profiles = pd.read_csv(DATA_DIR / "default_daytype_profiles.csv")
    appliances = pd.read_csv(DATA_DIR / "default_appliances.csv")
    misc_loads = pd.read_csv(DATA_DIR / "default_misc_loads.csv")
    household_categories = pd.read_csv(DATA_DIR / "default_household_categories.csv")
    cost_lcoe_results = pd.read_csv(DATA_DIR / files["cost_lcoe_results"]).set_index("result")["value"]

    item_annual_wh = lp.compute_item_annual_wh(calendar, daytype_profiles, appliances, misc_loads, household_categories)
    summary = sr.compute_billing_summary(item_annual_wh, household_categories,
                                          float(cost_lcoe_results["lcoe_eur_per_kwh"]), payload.tariffMarkupPct)
    return native(summary)


@router.get("/results/export")
def results_export(system_type: str = "battery"):
    """Full project export as one .xlsx — reflects the last-SAVED state of every step (same
    convention as the rest of this app: Results already only ever reads other steps' last-saved
    CSVs, never in-progress edits), so this is a simple GET with no payload."""
    ctx = _load_results_context(system_type)
    files = _results_filenames(system_type)

    roi_path = DATA_DIR / files["roi_parameters"]
    roi_parameters = (pd.read_csv(roi_path) if roi_path.exists()
                       else sr.build_default_roi_parameters(ctx["cost_lcoe_results"]["lcoe_eur_per_kwh"], system_type=system_type))
    _, master_summary, cashflow, _ = _run_results(ResultsComputePayload(roiParameters=roi_parameters.to_dict("records")), system_type)

    if system_type == "diesel":
        cost_result = cl.run_diesel_cost_lcoe_pipeline(
            ctx["boq_items"], ctx["land_cost_options"], ctx["cost_parameters"], ctx["pv_parameters"]["ppeak_w"],
            ctx["pv_results"]["installed_capacity_kw"], ctx["pv_results"]["annual_fuel_cost_eur"],
            ctx["annual_demand_wh"] - ctx["pv_results"]["unserved_energy_wh"],
        )
        simulation_path = DATA_DIR / "pv_diesel_simulation_2026.csv"
        selection_title = "Generator Selection"
    else:
        cost_result = cl.run_cost_lcoe_pipeline(
            ctx["boq_items"], ctx["land_cost_options"], ctx["cost_parameters"], ctx["pv_parameters"]["ppeak_w"],
            ctx["pv_results"]["battery_capacity_kwh"], ctx["pv_results"]["annual_egen_wh"],
        )
        simulation_path = DATA_DIR / "pv_battery_simulation_2026.csv"
        selection_title = "Battery Selection"

    total_cost_overview = pd.DataFrame(
        [{"Metric": "capital_cost_eur", "Value": cost_result["capital_cost_eur"]},
         {"Metric": "total_opex_eur", "Value": cost_result["opex"]["total_opex_eur"]}]
        + [{"Metric": f"opex_{k}", "Value": v} for k, v in cost_result["opex"]["breakdown"].items()]
        + [{"Metric": f"lcoe_{k}", "Value": v} for k, v in cost_result["lcoe"].items()]
    )

    demand_load = pd.read_csv(DATA_DIR / "hourly_load_profile_2026.csv")
    irradiance = spv.load_default_irradiance()
    solar_generation = pd.read_csv(simulation_path) if simulation_path.exists() else pd.DataFrame()

    sheets = {
        "Overall Summary": master_summary,
        "Demand Load": demand_load,
        "Solar Irradiation Data": irradiance,
        "Solar Generation": solar_generation,
        selection_title: er.series_to_frame(ctx["pv_results"], "Result", "Value"),
        "Cost Breakdown": cost_result["boq"]["items"],
        "NPV": cashflow["yearly"],
        "Total Cost Overview": total_cost_overview,
    }
    return _xlsx_response(lambda buf: er.build_workbook(sheets, buf), f"Results_Export_{system_type}.xlsx")


@router.get("/results/overview")
def results_overview():
    """Side-by-side key figures for both scenarios, tolerant of either not being configured/saved yet."""
    def _scenario_summary(system_type):
        try:
            ctx = _load_results_context(system_type)
        except HTTPException:
            return None
        roi_path = DATA_DIR / _results_filenames(system_type)["roi_results"]
        roi = pd.read_csv(roi_path).iloc[0].to_dict() if roi_path.exists() else None
        return {
            "capitalCostEur": ctx["cost_lcoe_results"]["capital_cost_eur"],
            "totalOpexEur": ctx["cost_lcoe_results"]["total_opex_eur"],
            "lcoeEurPerKwh": ctx["cost_lcoe_results"]["lcoe_eur_per_kwh"],
            "unmetOrZeroYieldHours": ctx["pv_results"]["zero_yield_hours"] if system_type == "battery" else ctx["pv_results"]["unmet_hours"],
            "roiPct": roi["roi_pct"] if roi else None,
            "npvEur": roi["npv_eur"] if roi else None,
            "simplePaybackYears": roi.get("simple_payback_years") if roi else None,
        }

    return native({"battery": _scenario_summary("battery"), "diesel": _scenario_summary("diesel")})


# ---------------------------------------------------------------------------
# Landing page dashboard — tolerant of missing upstream steps
# ---------------------------------------------------------------------------

@router.get("/progress")
def progress():
    """Which steps have a saved result on disk yet — drives the top stepper's checkmarks."""
    return {
        "loadSetup": (DATA_DIR / "connected_load_results.csv").exists(),
        "demandProfile": (DATA_DIR / "hourly_load_profile_2026.csv").exists(),
        "energyInsights": (DATA_DIR / "hourly_load_profile_2026.csv").exists(),
        "solarDesign": (DATA_DIR / "pv_battery_sizing_results_2026.csv").exists(),
        "financials": (DATA_DIR / "cost_lcoe_results_2026.csv").exists(),
        "results": (DATA_DIR / "roi_results_2026.csv").exists(),
    }


@router.get("/dashboard")
def dashboard():
    def _try(path, idx_col=None):
        p = DATA_DIR / path
        if not p.exists():
            return None
        df = pd.read_csv(p)
        return df.set_index(idx_col)["value"] if idx_col else df

    connected_load = _try("connected_load_results.csv", "result")
    pv_battery = _try("pv_battery_sizing_results_2026.csv", "result")
    cost_lcoe = _try("cost_lcoe_results_2026.csv", "result")
    hourly = _try("hourly_load_profile_2026.csv")
    roi_results = _try("roi_results_2026.csv")
    site = si.as_dict(si.load_defaults())

    return native({
        "connectedLoadMw": connected_load["total_connected_load_mw"] if connected_load is not None else None,
        "annualDemandGwh": (hourly["total_wh"].sum() / 1e9) if hourly is not None else None,
        "batteryKwh": pv_battery["battery_capacity_kwh"] if pv_battery is not None else None,
        "zeroYieldHours": pv_battery["zero_yield_hours"] if pv_battery is not None else None,
        "capitalCostEur": cost_lcoe["capital_cost_eur"] if cost_lcoe is not None else None,
        "lcoeEurPerKwh": cost_lcoe["lcoe_eur_per_kwh"] if cost_lcoe is not None else None,
        "roiPct": roi_results["roi_pct"].iloc[0] if roi_results is not None else None,
        "siteInfo": site,
    })
