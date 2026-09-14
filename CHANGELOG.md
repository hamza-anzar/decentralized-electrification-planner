# Changelog

Internal version log for this project, kept so any past state can be found and reverted to if
something breaks. Each version below corresponds to a git tag of the same name (e.g. `v1.1`) — to go
back to that exact state:

```bash
git checkout v1.1
```

or, to permanently roll the `main` branch back to it (destructive — ask before doing this on a shared
branch):

```bash
git reset --hard v1.1
```

Versions are numbered `1.x` for now (incremented on every pushed change) since this is a single-track
project, not a public library with a compatibility contract.

---

## [1.1] - 2026-09-14

### Added — Wind Turbine generation technology (Wind+Battery / Wind+Diesel)

A third generation technology alongside the existing Solar+Battery and Solar+Diesel, added end-to-end:
turbine data layer, sizing engineering, BOQ/financials, results, and the full frontend UI.

**System Design** (renamed from "Solar Design" — it now covers more than one generation source) gained
two new tabs:
- **Wind Turbine with Battery System** — turbine selection (8-model library or a custom uploaded power
  curve), wind resource (bundled default from the source workbook's Annex-V, or live NASA POWER),
  wind-shear hub-height correction, auto-recommended turbine count, battery sizing (reuses the exact
  Solar+Battery battery-sizing math), a wind-speed frequency histogram (Weibull-style, 0.5 m/s bins),
  and all the same chart views as Solar+Battery (battery sensitivity, demand/generation/SOC, duck curve).
- **Wind Turbine with Diesel Generator** — same turbine selection, sized against a diesel generator
  (reuses the exact Solar+Diesel generator-sizing math) with a deficit load-duration curve.

**Financials** gained matching **Wind Turbine with Battery System** and **Wind Turbine with Diesel
Generator** tabs — BOQ line items and costs sourced from the source workbook's Annex-VII (wind
economics), land cost options shared with the Solar scenarios, generator cost rates reused exactly from
Solar+Diesel.

**Results** gained **Wind + Battery** and **Wind + Diesel** scenario tabs, and the **Overview** page was
generalized from a hardcoded 2-scenario (Battery/Diesel) comparison to an N-scenario one, now showing
all four side by side (tolerant of any not yet being configured/saved).

### New backend files
- `rural-electrification-webapp/backend/core/wind_pv.py` — wind sizing engine: wind-shear correction,
  turbine power-curve interpolation, turbine-count recommendation, Wind+Battery/Wind+Diesel sizing
  pipelines, custom power-curve Excel round-trip. Imports and reuses `core/solar_pv.py`'s
  battery/generator-sizing helpers unchanged (already generation-technology-agnostic).
- New data files: `default_wind_turbines.csv` (8-model library), `default_wind_turbine_power_curves.csv`
  (long-format power curves, 0.5 m/s bins), `default_wind_speed_2026.csv` (hourly wind speed, extracted
  from the source workbook's Annex-V), `default_wind_parameters(_diesel).csv`,
  `default_diesel_generator_parameters_wind.csv`, `default_boq_items_wind_(battery|diesel).csv`,
  `default_cost_parameters_wind_(battery|diesel).csv`, plus their computed-result counterparts
  (`wind_*_sizing_results_2026.csv`, `cost_lcoe_results_wind_*_2026.csv`, `master_summary_wind_*_2026.csv`,
  `roi_results_wind_*_2026.csv`, `default_roi_parameters_wind_*.csv`).
- `wind-turbine-datasheets/` — source PDFs for the 8 turbine models, the `Wind_Turbine_Library.xlsx`
  workbook the library CSVs were digitized from, and the one-off extraction scripts
  (`build_turbine_library.py`, `export_to_data.py`, `extract_wind_speed.py`). Kept in the repo for the
  same provenance/transparency reason `Base-Calculations-00.xlsx` is — so the turbine data's source is
  traceable.

### New backend API endpoints
- `GET/POST /api/wind-design/*` — Wind+Battery design (defaults, fetch-resource, curve-template,
  curve-upload, recommended-turbine-count, compute, save)
- `GET/POST /api/wind-diesel-design/*` — Wind+Diesel design (defaults, compute, save)
- `GET/POST /api/financials-wind-battery/*` — Wind+Battery financials (defaults, template, upload,
  compute, save)
- `GET/POST /api/financials-wind-diesel/*` — Wind+Diesel financials (defaults, template, upload,
  compute, save)
- `/api/results/*` (context, compute, save, billing, export, overview) extended with two new
  `system_type` values: `wind_battery`, `wind_diesel` — purely additive `elif` branches; the existing
  `battery`/`diesel` branches were not touched.

### New frontend files
- `pages/SystemDesign.jsx` (replaces `pages/SolarDesign.jsx`) — now renders 4 tabs instead of 2.
- `pages/wind/WindBattery.jsx`, `pages/wind/WindDiesel.jsx`
- `pages/financials/FinancialsWindBattery.jsx`, `pages/financials/FinancialsWindDiesel.jsx`

### Changed
- `lib/steps.js` — the "Solar Design" step is now titled "System Design" (`stepperLabel: "SYSTEM DESIGN"`);
  route/key (`solarDesign` / `/solar-design`) left unchanged so nothing else breaks.
- `lib/charts.js` — `egenVsDemandChart`, `duckCurveChart`, `generatorDispatchChart` gained an optional
  generation-source label parameter (defaults preserved, so existing Solar callers are unaffected);
  added `windSpeedVsDemandChart` and `windSpeedHistogramChart`; `deficitLoadDurationChart` gained an
  optional source label; `scenarioComparisonBarChart` generalized from a hardcoded battery/diesel pair
  to an arbitrary list of `{label, value, color}` series.
- `lib/labels.js` — added human-readable labels for the wind parameter keys (turbine_model,
  turbine_count, hub_height_m, etc.).
- `pages/results/ResultsScenario.jsx` — generalized `isDiesel`/KPI-label branching to also recognize
  `wind_battery`/`wind_diesel`; the "missing results" error message now names the correct scenario tab
  for all four system types instead of hardcoding Battery/Diesel.
- `pages/results/ResultsOverview.jsx` — rewritten to loop over a `SCENARIOS` array (4 entries) instead
  of two hardcoded `battery`/`diesel` variables.
- `core/summary_roi.py` — `build_default_roi_parameters()`'s diesel-vs-battery description branch fixed
  to check `system_type in ("diesel", "wind_diesel")` (and `"wind_battery"`) instead of an exact
  `== "diesel"` match, so it doesn't mislabel the wind scenarios.

### Fixed
- **`compute_boq_totals()` dtype trap** (`core/cost_lcoe.py`): a BOQ's `total_cost_eur` column, on its
  very first live compute after a fresh page load (before any value has ever been recomputed), can come
  back from the browser's JSON round-trip as an all-integer-valued column, which pandas infers as
  `int64`. Assigning a genuinely fractional cost into that column then raises
  `TypeError: Invalid value '...' for dtype 'int64'` instead of silently truncating it. This didn't
  surface for the existing Solar+Battery/Solar+Diesel scenarios only because their non-system-scaled
  BOQ rows all start at a placeholder cost of exactly `0.0`; it hit immediately for Wind, whose
  Annex-VII-sourced costs are real fractional numbers (e.g. 28,282.83 EUR). Fixed at the root by
  casting `total_cost_eur` to `float64` up front in `compute_boq_totals()`, protecting all four
  scenarios (and any future one) against this regardless of which values happen to be involved.

### Verified
- Every new backend endpoint smoke-tested via FastAPI's `TestClient` (design compute/save, financials
  compute/save + template round-trip, results compute/save/billing/export/overview) for both
  Wind+Battery and Wind+Diesel.
- Solar+Battery and Solar+Diesel's saved result files (`pv_battery_sizing_results_2026.csv`,
  `pv_diesel_sizing_results_2026.csv`, `cost_lcoe_results_2026.csv`, `cost_lcoe_results_diesel_2026.csv`)
  confirmed **byte-identical** before and after this change — zero regression from the additive
  branching approach.
- Frontend `npm run build` passes; full browser walkthrough of all 4 System Design tabs, all 4
  Financials tabs, and Results (Overview with all 4 scenarios + both new scenario tabs), including the
  turbine-library dropdown, wind-speed histogram, and custom power-curve upload round-trip.

---

## [1.0] - 2026-09-13 (baseline)

Everything up to and including commit `cb38e81` ("Fix Render Blueprint: static sites don't take a plan
field") — the state of the project immediately before the Wind Turbine feature work began. Covers, in
summary:

- Initial GitHub upload with a full README (title, description, methodology, repo layout, notebook
  table, workflow, setup instructions, academic disclaimer).
- Project/repo renamed to "Decentralized Electrification Planner".
- Render.com Blueprint deployment (`render.yaml`) — single-platform hosting for both frontend (static
  site) and backend (web service).
- Appliance/day-type demand-profile sync bug fixed (new appliances now correctly propagate into the
  Demand Profile's day-type grid and the hourly calculation).
- Optional load-randomness feature added to the Demand Profile step (multiplicative Gaussian noise,
  seeded, default off).

This is tag `v1.0` — see `git show v1.0` or `git checkout v1.0` for the exact state.
