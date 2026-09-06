# Rural Electrification Planner

**Design and Economic Analysis of a Rural Electrification System — a six-step approach from load
estimation to a fully sized PV system (with battery or diesel-generator backup) and full economic
parameters.**

> ⚠️ **Academic project.** This tool and its outputs are for educational demonstration only. Figures
> are illustrative and are **not** validated or accurate for real-time or investment-grade engineering
> or financial decisions.

![Landing page](docs/screenshots/01_landing.png)

---

## Table of Contents

- [Description & Scope](#description--scope)
- [Methodology](#methodology)
- [Repository Layout](#repository-layout)
- [Notebook Details](#notebook-details)
- [Workflow](#workflow)
- [Screenshots](#screenshots)
- [Setup](#setup)
- [Disclaimer](#disclaimer)

---

## Description & Scope

This project plans and economically evaluates a **solar mini-grid** for an off-grid rural community —
starting from a household-by-household appliance inventory and ending at a fully sized PV plant (with
either a **battery bank** or a **diesel generator** as backup/firming), a bill of quantities, an LCOE
calculation, and an ROI/NPV/payback cash-flow model.

It began as a from-scratch re-implementation, in Python, of a large Excel-based engineering workbook
(`Base-Calculations-00.xlsx`, 12 sheets, ~1.9 MB of formulas) built for a real reference site
("Shamspir", a coastal site with 1,480 households across 3 socio-economic categories). Every core
calculation was first built and validated cell-by-cell against that workbook in a series of Jupyter
notebooks (see [Notebook Details](#notebook-details)), then ported into a small Streamlit app, and
finally rebuilt as the app in this repository: a **FastAPI** backend (wrapping the exact same
calculation modules as a JSON REST API) and a **React + Tailwind CSS + Apache ECharts** frontend.

**Scope — Phase 1: Solar PV.** Two generation/storage pairings are supported side by side:

- **Solar PV + Battery** — PV sized from the load profile, battery sized from the worst deficit block.
- **Solar PV + Diesel Generator** — PV sized from average daytime demand, diesel generator sized from
  the residual (unmet) load with a safety margin and rounded to a practical unit size.

Wind, hydro, and biomass generation are **explicitly out of scope** for this phase (the source workbook
also contains a parallel wind-power model, `Annex-V`/`Annex-Va`/`Annex-Vb`, which was not ported).

## Methodology

The six computational stages below mirror the source workbook's own annexes, with a handful of
deliberate, documented improvements over the as-implemented workbook (a buggy calendar mapping fixed,
an undocumented battery-derating constant made an explicit editable input, and an ROI/payback model
added from scratch since the source workbook has no revenue model at all — only cost). The full
formula-by-formula extraction of the original workbook lives in
[`docs/Workbook-Methodology-Reference.md`](docs/Workbook-Methodology-Reference.md); day-to-day
decisions and their rationale are logged in [`docs/PROJECT_LOG.md`](docs/PROJECT_LOG.md).

1. **Connected load** — `Σ (appliance power × qty/house × household count)` per category (A/B/C) plus
   community/misc. loads (hospital, school, street lighting, etc.). Household counts are derived
   live from a total and each category's % split (largest-remainder rounding, so counts always sum
   exactly).
2. **8,760-hour annual demand profile** — a fully editable rule-based calendar (season periods,
   public holidays, festival holidays → one of 19 "day-type" hourly usage patterns per day) drives
   `demand(hour) = Σ (qty_active × power × household_count)` for every hour of the year. An alternative
   path lets a user upload a complete custom hourly profile and skip the calendar entirely.
3. **Solar resource & sizing**:
   - Hourly generation: **`Egen(Wh) = Ppeak(W) × [G(i)/1000] × Q / Iqc`**, where `G(i)` is hourly
     global irradiance (W/m², from a bundled dataset or a live PVGIS/NASA POWER pull), `Q` is the
     system performance ratio, and `Iqc` is the reference (STC) irradiance.
   - **Battery pairing**: `Δh = Egen(h) − Demand(h)`; battery size is derived from the worst
     (most negative) deficit block, divided by depth-of-discharge and a battery quality/derating
     factor, then rounded — with a manual override always available and a live zero-yield-hours curve.
   - **Diesel pairing**: PV is sized off average daytime demand (no battery to smooth output); the
     residual/unmet load drives diesel generator sizing — peak deficit → safety margin → rounded up to
     a practical unit size/count (e.g. "2 × 1 MW" instead of a single oddly-sized 1.72 MW unit),
     manually overridable.
4. **Cost, Bill of Quantities & LCOE** — an itemized BOQ (qty × unit cost for standard line items;
   system-size × lumpsum rate for PV panels, the battery system, or diesel generators — so the BOQ
   total tracks Step 3's sizing automatically); O&M discounted to present value over the project
   lifetime; `LCOE = Total Cost (Capex + PV of Opex) / Total PV Generation`.
5. **Load-growth projection** — a compound annual growth rate, `Energy(year n) = Energy(year 1) ×
   (1+g)^(n-1)`, projects demand across the full project lifetime (typical mini-grid range 3–8%/yr;
   depends on population growth, income growth, connection-rate uptake, and productive-use adoption).
6. **Summary, ROI & payback** — every prior step's headline figures in one place, plus a full
   year-by-year cash-flow model (simple & discounted payback, NPV, lifetime ROI) built from scratch —
   this doesn't exist anywhere in the source workbook, which only ever computes cost (LCOE), not
   revenue — so the electricity tariff is an explicit, clearly-flagged placeholder assumption
   (break-even = LCOE) rather than a researched market rate.

## Repository Layout

```
Rural Electrification/
├── notebooks/                        # Step-by-step development notebooks (one per core stage, §Notebook Details)
├── data/                              # Default assumption tables & saved results — editable CSV, the app's data layer
├── rural-electrification-webapp/      # THE APP — current, actively developed deliverable
│   ├── backend/                       #   FastAPI REST API
│   │   ├── api.py                     #     All HTTP endpoints
│   │   ├── core/                      #     Pure-Python calculation modules (ported 1:1 from the notebooks)
│   │   └── main.py                    #     FastAPI app entrypoint
│   └── frontend/                      #   React + Vite + Tailwind CSS + Apache ECharts SPA
│       └── src/
│           ├── pages/                 #     One page per workflow step (+ Battery/Diesel sub-tabs)
│           ├── components/            #     Shared UI (charts, editable tables, KPI cards, …)
│           └── lib/                   #     Chart builders, formatting, shared client-side logic
├── app/                                # Legacy Streamlit app — superseded by backend/ + frontend/, kept for reference only
├── docs/
│   ├── Workbook-Methodology-Reference.md   # Full formula-by-formula extraction of the source workbook
│   ├── PROJECT_LOG.md                      # Scope decisions, open questions, build history
│   ├── Local-VSCode-Setup.md               # Editor/venv setup notes
│   └── screenshots/                        # README screenshots
├── Base-Calculations-00.xlsx           # Original source workbook (reference only, read-only)
└── requirements.txt                    # Python dependencies (backend + notebooks + legacy app)
```

## Notebook Details

Each notebook was built, executed, and validated against the source workbook **before** its logic was
ported into `backend/core/`, in the order below. They are not required to run the app itself (the app
ships with the resulting default data already extracted into `data/*.csv`) — they exist as the
audit trail: how each formula was derived, cross-checked, and where it deliberately deviates from the
source file.

| # | Notebook | What it does | Noting points |
|---|---|---|---|
| 1 | `01_Connected_Load_Estimation.ipynb` | Builds the household/appliance/misc-load tables and computes total connected load (≈ Annex-I). | Verified against the workbook: **1.81128 MW**. Adds a user-editable "Others" placeholder appliance per category (not in the source file) so a new appliance can be added later without changing table structure. |
| 2 | `02_Hourly_Load_Profile.ipynb` | Extracts the 19 day-type hourly usage patterns and builds the full 8,760-hour annual demand profile from an editable season/holiday/festival calendar (≈ Annex-II/III). | **Fixes a real bug** in the source workbook: the as-implemented calendar mis-maps ~44 days (mid-Aug–Oct) to the wrong day-type block. The editable calendar's annual total (3.4403 GWh) differs from the buggy as-implemented one (3.4373 GWh) by design. A known, accepted 4-day/year simplification remains (single date range per season can't capture the source's weekday/weekend-asymmetric transition) — see `docs/PROJECT_LOG.md` item 3. |
| 3 | `03_Load_Profile_Visualization.ipynb` | Builds the weekly / monthly / yearly chart views over the Step-2 profile, unit-switchable (kWh/MWh/TWh). | Read-only over `data/hourly_load_profile_2026.csv` — changes nothing. Confirms unit conversion is exact across all three views. |
| 4 | `04_Solar_Resource_and_PV_Battery_Sizing.ipynb` | Sources hourly irradiance (bundled dataset, or live PVGIS/NASA POWER), computes hourly PV generation (Egen), the demand-vs-generation deficit, and battery sizing from the worst deficit block. | The app only ever needs latitude/longitude from the user — both live APIs are genuinely free and need **no signup/API key**. The workbook's undocumented `×0.90` battery-derating constant becomes an explicit, user-editable "battery quality factor" (default 0.85), separate from depth-of-discharge (default 0.80). |
| 5 | `05_Cost_BOQ_LCOE.ipynb` | Replicates the economic model: itemized BOQ, O&M present value (inflation/discount adjusted), LCOE (≈ Annex-VI). | Fixes two BOQ line items (solar panels, battery system) that the workbook methodology doc itself flagged as "should be a live computed dependency, not a hand-typed number" — both now scale automatically with Step 4's sizing. Adds a PKR/EUR/USD currency toggle and a lump-sum capex override. |
| 6 | `06_Summary_Table.ipynb` | Pulls every prior step into one summary, and builds an ROI/payback/NPV cash-flow model from scratch. | The source workbook has **no revenue model at all** — this is new territory, not a port. The electricity tariff needed for revenue is an explicit placeholder (break-even = LCOE), clearly flagged in the app rather than presented as a researched figure. |

## Workflow

The app guides you through six steps, shown as a stepper across the top of every page:

1. **Load Setup** — site/location context, household categories (counts, income tier, living area),
   per-category appliance lists, and community/misc. loads.
2. **Demand Profile** — the editable season/holiday/day-type calendar that generates the 8,760-hour
   annual demand profile (or upload your own hourly profile directly); also sets the project's start
   year, duration, and annual load-growth rate, with a growth-projection chart.
3. **Energy Insights** — explore the demand profile at hourly / daily / weekly / monthly / annual
   granularity, plus a multi-year view previewing any future project year's scaled demand.
4. **Solar Design** — two sub-tabs, **Solar + Battery** and **Solar + Diesel Generator**: irradiance
   source, PV sizing (with a recommended size and manual override), and battery or generator sizing
   with the formulas shown inline.
5. **Financials** — mirrored **Battery**/**Diesel** tabs: an itemized, editable Bill of Quantities
   (with Excel upload/download), cost parameters, and the resulting capital cost, opex, and LCOE.
6. **Results** — an **Overview** tab comparing both scenarios side by side (LCOE, capex, ROI,
   no-electricity hours, recommended tariff & billing estimate), plus a full **Battery** and **Diesel**
   results tab each with ROI assumptions, a payback/NPV chart, the full annual cash-flow table, and an
   Excel export of the entire project (demand, irradiance, generation, BOQ, cash-flow, and summary, all
   in one workbook).

## Screenshots

| | |
|---|---|
| **Load Setup** — household categories & appliances | **Demand Profile** — editable calendar with real weekday/weekend day counts |
| ![Load Setup](docs/screenshots/02_load_setup.png) | ![Demand Profile](docs/screenshots/03_demand_profile.png) |
| **Energy Insights** — multi-granularity + multi-year view | **Solar Design** — PV/battery sizing with formulas shown |
| ![Energy Insights](docs/screenshots/04_energy_insights.png) | ![Solar Design](docs/screenshots/05_solar_design.png) |
| **Financials** — editable Bill of Quantities | **Results** — Battery vs. Diesel comparison |
| ![Financials](docs/screenshots/06_financials.png) | ![Results](docs/screenshots/07_results.png) |

## Setup

### 1. Prerequisites

- **Python 3.10+**
- **Node.js** (for the frontend — install from [nodejs.org](https://nodejs.org) if `npm` isn't recognized)
- Git

### 2. Download the project

```bash
git clone https://github.com/<your-username>/rural-electrification-planner.git
cd rural-electrification-planner
```

### 3. Python environment (backend + notebooks)

From the project root:

```bash
python -m venv venv
venv\Scripts\activate        # Windows — use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
```

### 4. (Optional) Re-run the development notebooks

Not required to run the app — the app already ships with the extracted default data in `data/`. Run
these only if you want to see/reproduce how each calculation was originally derived and validated:

```bash
jupyter notebook notebooks/
```

Open and run, in order: `01_Connected_Load_Estimation.ipynb` → `02_Hourly_Load_Profile.ipynb` →
`03_Load_Profile_Visualization.ipynb` → `04_Solar_Resource_and_PV_Battery_Sizing.ipynb` →
`05_Cost_BOQ_LCOE.ipynb` → `06_Summary_Table.ipynb`.

### 5. Frontend dependencies

```bash
cd rural-electrification-webapp/frontend
npm install
cd ../..
```

(`node_modules/` is never committed — always run `npm install` after cloning or pulling frontend changes.)

### 6. Run the dashboard

The app is two processes running at once — use two terminals.

**Terminal 1 — backend** (from the project root):

```bash
venv\Scripts\activate
cd rural-electrification-webapp/backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — frontend:**

```bash
cd rural-electrification-webapp/frontend
npm run dev
```

Then open the URL Vite prints — usually **http://localhost:5173**. The frontend talks to the backend
at `http://localhost:8000` by default; if you change that port, also set `VITE_API_URL` for the
frontend (see `rural-electrification-webapp/frontend/README.md` if present).

### Legacy Streamlit app (reference only)

`app/Home.py` still runs (`streamlit run app/Home.py`) but is no longer developed — the FastAPI +
React app above is the actively maintained deliverable.

## Disclaimer

**Academic project.** This tool and its outputs are for **educational demonstration only**. Formulas,
default assumptions, and results are **not validated or accurate for real-time or investment-grade
engineering or financial decisions**. Do not use this project's outputs as the basis for an actual
electrification investment, procurement, or engineering design without independent professional
verification.
