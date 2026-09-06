# Base-Calculations.xlsx — Complete Methodology Map

Source file: `/mnt/user-data/uploads/Rural Electrification/Base-Calculations.xlsx` (11.9 MB, 12 sheets, 1 hidden).
Extracted with `openpyxl` (`data_only=False` for formulas, `data_only=True` for cached values — both were present and valid, i.e. the file was last saved by Excel with live cached values).

This document is the authoritative reference for re-implementing the workbook as a Python/web app. All Excel formulas are quoted verbatim. Every number quoted as a "value" is the cached value found in the file (site: **Shamspir**, presumably coastal Pakistan given the mangroves reference, currency PKR, 2026 study year).

---

## 0. Workbook map (corrected)

| Sheet | Real purpose | Size |
|---|---|---|
| Annex-I | Household/appliance inventory + connected-load calc. Also contains the **area-based household-count derivation** (not previously known). | 28 used rows |
| Annex-II | 19 representative 24-hour "day-type" hourly load profiles (Qty-Active per appliance), one for each season-month / weekend / holiday / festival combination. | ~485 used rows |
| Annex-III | Full 8,760-hour annual demand table for calendar year **2026**. Each hour's appliance-activity is `INDEX()`-looked-up from a **hard-coded** row-range in Annex-II (not a computed/dynamic mapping — see §4). Also carries an (orphaned) 2026→2030 demand-growth projection. | 8,760 data rows (10–8769), 91 cols |
| Annex-IIIa | **Native Excel PivotTable** (static cached values, no formulas): Weekly Demand Profile, sourced from hidden Annex-DP. | 52 weeks |
| Annex-IIIb | **Native Excel PivotTable** (static cached values): Monthly Demand Profile, sourced from hidden Annex-DP. | 12 months |
| Annex-DP (for Pivot) | **Hidden** sheet. Flat "long format" extract of Annex-III (Hour, Date, Week, Month, Total Wh) that feeds the two PivotTables above and the PivotCache. | 8,760 rows × 5 cols |
| Annex-IV | **Solar PV** sizing: hourly irradiance → PV generation → Delta-E vs demand → battery SOC simulation → battery size & zero-yield-hour count. | 8,760 rows × 23 cols |
| Annex-V | **Wind resource** table: hourly wind speed (raw data) rounded to 0.5 m/s bins, per-month histogram of hours-per-bin (Weibull-style frequency table), and a wind-power lookup into Annex-Va. **Not** a "solar/battery detail" sheet as originally guessed. | 8,760 rows × 23 cols |
| Annex-Va | Wind turbine **power curve** (kW output vs wind-speed bin, 0–20 m/s in 0.5 m/s steps) × monthly frequency (from Annex-V) → monthly energy produced vs monthly demand comparison. | 65 rows |
| Annex-Vb | **Wind power** sizing sheet — structurally the exact mirror of Annex-IV (Delta-E, SOC simulation, battery sizing) but for wind generation (via VLOOKUP into Annex-Va's power curve). Contains leftover/unused solar-Ppeak columns copied from Annex-IV. | 8,760 rows × 24 cols |
| Annex-VI | **Solar PV economic analysis**: full BOQ (2 MW solar plant), land cost, O&M with inflation/discount present-value calc, LCOE. | 70 used rows |
| Annex-VII | **Wind power economic analysis** — NOT the project summary as originally guessed. Same structure as Annex-VI but for a 6×500 kW wind farm. | 70 used rows |

**No defined names** exist in the workbook (`wb.defined_names` is empty — each sheet's own printed `dimensions` string, e.g. `Annex-III A1:CM8769`, is just openpyxl's used-range report, not a named range).

**Currency confirmed:** all costs in Annex-VI and Annex-VII are **PKR (Pakistani Rupees)**, with a fixed conversion `1 Euro = 330 PKR` used throughout for the Euro-equivalent columns.

---

## 1. Data flow (sheet → sheet dependency chain)

```
Annex-I (appliance list, power, household counts, connected load)
   │  (appliance names/power pulled by formula into Annex-II & Annex-III;
   │   household counts 'Annex-I'!$K$7/$K$8/$K$9 used to scale per-household → all-households)
   ▼
Annex-II (19 hand-built 24-hour "day-type" profiles: Qty-Active per appliance per hour)
   │  (Annex-III!G10:AD8769 = INDEX() lookups into HARD-CODED row-ranges of Annex-II,
   │   chosen per calendar day by the workbook author — see §4. NOT a live calendar→
   │   day-type mapping formula; Annex-IIIa/IIIb are NOT used for this lookup.)
   ▼
Annex-III (8,760-hour annual demand profile, col AF = Total Wh per hour)
   │                                   │                                  │
   │ (AF10:AF8769 read as 'Annex-III'!AF{row+3})                          │
   ▼                                   ▼                                  ▼
Annex-DP (hidden, flat copy)     Annex-IV (col H = Solar demand input)   Annex-V (col G = Wind demand input, via 'Annex-III'!AF; also A/B/C/E/F date fields copied)
   │                                   │                                  │
   ▼                                   │                                  ▼
Annex-IIIa / Annex-IIIb                │                             Annex-Va (power curve, fed by Annex-V's monthly wind-speed
(PivotTables: weekly/monthly           │                             frequency table L:W, itself derived from Annex-V col I)
  demand summary — cached values)      │                                  │
                                       │                                  ▼
                                       │                             Annex-Vb (col G = 'Annex-V'!I; col L = VLOOKUP into
                                       │                              Annex-Va power curve × turbine count; Delta-E/SOC/
                                       │                              battery-size simulation, mirrors Annex-IV)
                                       ▼                                  │
                                Annex-IV battery size (S7, kWh)           ▼
                                       │                          Annex-Vb battery size (T6, kWh)
                                       │  (MANUALLY re-typed,             │  (MANUALLY re-typed,
                                       │   not a live formula link)       │   not a live formula link)
                                       ▼                                  ▼
                                Annex-VI!E27 (Battery Qty, MWh)    Annex-VII!C27 (Battery Qty, MWh)
                                Annex-VI (Solar BOQ, O&M, LCOE)    Annex-VII (Wind BOQ, O&M, LCOE)
```

Key structural finding: **the battery-size numbers that appear in the two economics sheets (Annex-VI!E27 = 8 MWh, Annex-VII!C27 = 46 MWh) are plain literal numbers, not formulas referencing Annex-IV!S7 / Annex-Vb!T6.** They happen to equal the current computed values (8,000 kWh and 46,000 kWh respectively) — someone manually copied the result over. In a Python re-implementation this dependency should become a **real** computed link.

Similarly, **Annex-VI!H50 ("Total Energy Generation (30 Years)")** references `'Annex-IV'!H8767` — but Annex-IV column **H is the DEMAND column**, not the generation column (K). So despite the label, the LCOE denominator is actually `total annual DEMAND (Wh) × 30 years`, not generation, and it does **not** apply the AG:AL demand-growth projection computed elsewhere in Annex-III (that projection appears to be orphaned/unused — see §12 Anomalies).

---

## 2. Annex-I — Households & Appliances

### 2.1 Household-count derivation (area-based extrapolation) — genuinely new finding

This is not a simple input table; households are extrapolated from measured area, top-right of the sheet (columns H/I/J/K, rows 6–14):

| Cell | Label | Value / Formula |
|---|---|---|
| H11 | km² (Total) | `0.65` |
| H12 | km² (Mangroves) | `0.26` |
| H13 / I13 / J13 / K13 | reference sample: "3000 m² (google map)" → "19 houses" | `H13=3000`, `J13=19` |
| H14 | "m² (60% area for houses)" | `=(H11-H12)*1000000*0.6` → `234000` (i.e. total−mangroves, km²→m², ×60% land-use factor) |
| J14 | extrapolated total households | `=J13*H14/H13` → `1482` (density from the 3000 m²/19-house Google-Maps sample, scaled to usable area) |
| H7 | **Total households (rounded)** | `=MROUND(J14,10)` → **`1480`** |
| J7/J8/J9 | category split % | A=`10`, B=`50`, C=`40` |
| K7/K8/K9 | **households per category** | `=MROUND(J7%*H7,10)` → A=**150**, B=**740**, C=**590** (sums to 1480) |

**Input assumptions to expose in the app:** total site area (km²), mangrove/excluded area (km²), usable-land fraction (60%), reference density sample (19 houses / 3000 m²), category split percentages (10/50/40%).

### 2.2 Appliance list & connected load

`Connected Load (W) = Power(W) × Qty × Household-count-of-category` — formula `E7 = C7*D7*$K$7` etc.

| Cat | # | Appliance | Power (W) | Qty/house (default) | Comment/Assumption |
|---|---|---|---|---|---|
| A (150 hh) | 1 | LED Light | 18 | 5 | |
| A | 2 | Ceiling Fan | 50 | 3 | |
| A | 3 | Television | 60 | 1 | |
| A | 4 | Iron | 800 | 1 | "Assuming daily use for simplicity" |
| A | 5 | Refrigerator | 800 | 1 | "800 W = Surge Load; Running Load = 200 W (Assumed)" |
| A | 6 | Washing Machine | 350 | 1 | "Assuming daily use for simplicity (In actual 2 days/week)" |
| B (740 hh) | 7 | LED Light | =A's (18) | 4 | |
| B | 8 | Ceiling Fan | =A's (50) | 2 | |
| B | 9 | Television | =A's (60) | 1 | |
| B | 10 | Iron | =A's (800) | 1 | "Assuming daily use for simplicity" |
| B | 11 | Refrigerator | =A's (800) | 1 | |
| C (590 hh) | 12 | LED Light | =A's (18) | 2 | |
| C | 13 | Ceiling Fan | =A's (50) | 1 | |
| **Misc.** | 14 | Hospital | 2000 | 1 | "~40 kWh/day small hospital → assume 2 kW constant; 1 hospital in area" |
| Misc. | 15 | Street Light | 60 | 50 | "50 lights per ChatGPT estimate (0.65 km², perimeter, internal roads, population)" |
| Misc. | 16 | Cold Storage | 10500 | 5 | "28A/380V max current; constant load assumed; multiple compressors so stable" |
| Misc. | 17 | School | `=20*C7+14*C8+20*200+C11` → 5860 | 1 | "10 classrooms, staff/principal/admin rooms, 4 toilets, canteen — 20 lights, 14 fans, 20 computers (200 W each), 1 fridge" |
| Misc. | 18 | Others | 4000 | 1 | "Pumps, offices, schools, shops etc. — assumed 2× hospital load" |

**Total Connected Load (MW)** = `=SUM(E7:E27)/1000000` = **1.81128 MW**.

Category C has only 2 appliance lines (minimal 1-bedroom/kitchen/toilet, 50 m² dwelling) — Iron/Fridge/Washing-machine are NOT modeled for category C.

---

## 3. Annex-II — Daily Hourly Load Profile Estimate

Structure: for each of **19 hand-authored "day types"**, 24 hourly rows give **"Qty Active"** (a fractional 0–N number, e.g. `0.25` for a fridge meaning "cycles on 25% of the hour") per appliance, per category (A/B/C) plus 5 Misc. loads (Hospitals/Street Lights/Cold Storage/School/Others use an "Active-or-Factor" number instead, e.g. street lights `40`–`50` = count of lights on that hour, hospital `0.7`/`1` = load factor).

### 3.1 Column layout (row 6/7 headers)

| Cols | Category | Sub-columns |
|---|---|---|
| A | Time | "Hourly Range" (text), B = decimal Hour-of-day (`TIME()`) |
| C–H | Category A | Qty-Active for LED/Fan/TV/Iron/Fridge/WashMachine |
| I, J | Category A totals | `I`=Wh/household, `J`=kWh all households |
| K–O | Category B | Qty-Active for LED/Fan/TV/Iron/Fridge |
| P, Q | Category B totals | Wh/household, kWh all households |
| R, S | Category C | Qty-Active LED/Fan |
| T, U | Category C totals | Wh/household, kWh all households |
| V–Z | Misc | Hospitals / Street Lights / Cold Storage / School / Others (Qty-Active-or-Factor) |

Example formula (row 10, category A per-household Wh, "November" block):
```
I10 = ($C10*'Annex-I'!$C$7 + 'Annex-II'!$D10*'Annex-I'!$C$8 + 'Annex-II'!$E10*'Annex-I'!$C$9
     + 'Annex-II'!$F10*'Annex-I'!$C$10 + 'Annex-II'!$G10*'Annex-I'!$C$11
     + 'Annex-II'!$H10*'Annex-I'!$C$12) * ($B11-$B10) * 24
```
i.e. `Σ(QtyActive_appliance × Power_W) × hour-length(=1) × 24` → this is (oddly) always ×24 even though `$B11-$B10` is already a 1-hour Excel time fraction (=1/24), so the `×24` exactly cancels the 1/24 time-fraction — net effect is simply `Σ(QtyActive × Power_W)` in Wh for that hour. (Re-implement in Python as plain `Σ(qty_active[i] * power_w[i])`.)
```
J10 = I10 * 'Annex-I'!$K$7 / 1000      → kWh across all Category-A households (K7 = 150)
```
Category B/C use the analogous pattern with `$K$8`(=740)/`$K$9`(=590).

### 3.2 The 19 day-type blocks (label row → 24-hour data rows)

| Data rows | Label (as typed in Annex-II col A) |
|---|---|
| 10–33 | November (Winter weekday) |
| 35–58 | December (Winter weekday) |
| 60–83 | January (Winter weekday) |
| 85–108 | February (Winter weekday) |
| 110–133 | March (Winter weekday) |
| 135–158 | **Winter Weekends Only** (November 01 – March 31) |
| 161–184 | April (Summer weekday) |
| 186–209 | May (Summer weekday) |
| 211–234 | June 01–15 (Summer weekday) |
| 236–259 | **Summer Weekends** (April 01 – June 15) |
| 261–284 | Early Monsoon (weekday, June 15 – July 15) |
| 286–309 | **Early Monsoon Weekends** |
| 312–335 | Peak Monsoon: June 16 – August 15 (weekday) — **defined but never referenced by Annex-III (see §12)** |
| 337–360 | Peak Monsoon: August 15 – September 15 (weekday) |
| 362–385 | **Peak Monsoon Weekends** (July 16 – September 15) |
| 387–410 | Late Summer (Sep 15 – Oct 31, weekday) — **defined but never referenced by Annex-III (see §12)** |
| 412–435 | **Late Summer Weekends** |
| 437–460 | **All Public Holidays** — "Stay at home (January 16, Feb 05, April 04, May 01, Aug 14, Nov 09, Dec 25)" |
| 462–485 | **Festival Holidays** — "(March 21, 22, 23, May 28, 29, June 25, 26, Aug 25)" |

Full per-hour Qty-Active values for every block are preserved verbatim in `/tmp/wb_explore/dump_Annex-II.txt` (not reproduced here for brevity, but every value is a plain number — no hidden formulas at the hourly level).

---

## 4. Annex-III — Annual Hourly Demand Profile (8,760 hours, year 2026)

### 4.1 Header / column layout

| Cols | Meaning |
|---|---|
| A–F | Date, Hour(1-8760), Week(`=INT((B-1)/168)+1`), Month(text), Day(weekday text), 24-hr clock |
| G–L | Category A Qty-Active × 6 appliances (`INDEX()` lookups, see §4.2) |
| M, N | Category A Wh/household, Wh all households |
| O–S | Category B Qty-Active × 5 appliances |
| T, U | Category B Wh/household, Wh all households |
| V, W | Category C Qty-Active × 2 appliances |
| X, Y | Category C Wh/household, Wh all households |
| Z–AD | Misc Qty-Active/Factor × 5 (Hospitals/StreetLights/ColdStorage/School/Others) |
| AE | Misc total Wh |
| AF | **Total Electricity Consumption (Wh) for that hour** = `N+U+Y+AE` |
| AG | (row 10 only) `=SUM(AF10:AF8769)/1e9` → Total Annual Consumption **3.472586398 GWh** |
| AH–AL | (row 10 only) a **linear demand-growth projection** to 2027–2030, target = 25% growth by 2030 (see §4.4) |

Row 5: `Connected Load: = 'Annex-I'!E28` = 1.81128 MW.
Row 6: `Peak Load: =MAX(AF10:AF8769)/1e6` = **1.18176 MW**.

### 4.2 How each hour's appliance activity is pulled from Annex-II (the actual "date→day-type" mechanism)

Each of columns G,H,I,J,K,L,O,P,Q,R,S,V,W,Z,AA,AB,AC,AD is an **array formula** of the form:
```
{=INDEX('Annex-II'!C$60:'Annex-II'!C$83, MOD($B10-1,24)+1)}
```
i.e. "take the row-range in Annex-II that represents the correct day-type for THIS calendar day, and index into it by hour-of-day (`MOD(hour-1,24)+1`)". **Crucially, the Annex-II row-range (`C$60:C$83` above) is a hard row-literal, individually chosen by the spreadsheet author for each of the 365 days** — it is not computed by any live formula that reads a calendar/holiday table. There is **no dynamic lookup table** (Annex-IIIa/IIIb are unrelated PivotTables, not used here). The mapping was built by manually copy/pasting the correct Annex-II block onto each day's 24 rows in Annex-III.

We reconstructed the complete day→block mapping for all 365 days of 2026 by reading the actual array-formula text at the first hour of every day. Full result: `/tmp/wb_explore/annexIII_daymap_segments2.txt`. Compressed summary (each row = a contiguous run of days using the same Annex-II block):

* Weekdays follow the season/month blocks in §3.2 in calendar order (Jan→Feb→Mar→[Apr..]), with weekend days (Sat/Sun, confirmed against the `E` weekday-name column) substituted with the matching season's "Weekend" block.
* The 7 **Public Holidays** and 8 **Festival Holidays** listed in Annex-II correctly override the season/weekend block on their specific calendar dates, **except**: the holiday labeled "January 16" is actually applied to **January 15** (one day early) — a one-day paste offset. All other 6 holidays and all 8 festival dates line up exactly with their labels.
* **Two of the nineteen Annex-II blocks are silently unused** — see Anomalies §12.1.

### 4.3 Growth-projection columns (AH:AL, row 10 only — orphaned)

```
AH10 = AG10 + ($AG$10*1.25 - AG10) * (AH8 - $AG$8) / (2030 - 2026)
```
Linear interpolation from the 2026 baseline (`AG10`) toward a **+25% by 2030** target, for years 2027 (AH), 2028 (AI), 2029 (AJ, AK — duplicated), 2030 (AL). This computation exists only in this one cell block and is **not referenced anywhere else in the workbook** (LCOE, battery sizing, and BOQ all use the flat 2026 demand). Flag for the human: was this growth curve meant to feed into system sizing / LCOE and was simply never wired up?

---

## 5. Annex-IIIa & Annex-IIIb — Weekly / Monthly Demand Pivots

Both are genuine Excel **PivotTables** (cache-backed; cells hold plain cached numbers, zero formulas) built off the hidden Annex-DP sheet.

* Annex-IIIa: `Week (1–52) → Sum of Total Electricity Consumption (Wh)`. Grand Total = **3,464,432,386 Wh**.
* Annex-IIIb: `Month → Sum of Total Electricity Consumption (Wh)`. Grand Total = **3,472,586,398 Wh** (matches Annex-III!AG10 GWh figure ×1e9).

(The two grand totals differ slightly — 3.4644 vs 3.4726 billion Wh — because the pivot's 52-week grouping doesn't cleanly divide the 8,760-hour year; not a bug, just a boundary effect of week-52 vs the days that spill into "week 53".)

Monthly and weekly demand values (Annex-IIIb, PKR-relevant later): Jan 276.22 MWh, Feb 264.80, Mar 304.13, Apr 308.82, May 325.56, Jun 296.46, Jul 276.65, Aug 285.57, Sep 276.13, Oct 310.74, Nov 271.66, Dec 275.84.

These pivots are used downstream only by Annex-Va (month-by-month wind demand comparison, via `GETPIVOTDATA` — see §9).

---

## 6. Annex-DP (for Pivot) — hidden staging sheet

Columns: `Hour | Date | Week | Month | Total Wh`, each cell a simple cross-sheet reference, e.g. `A3='Annex-III'!B10`, `E3='Annex-III'!AF10`. Pure pass-through of Annex-III into a flat/long table shape suitable for a PivotTable source (Annex-III's date/hour columns aren't contiguous with its Total-Wh column, so this sheet re-arranges them). No calculation logic of its own. **Not needed in a Python rebuild** — just query the hourly table directly.

---

## 7. Annex-IV — Solar PV Resource Potential & Sizing

### 7.1 Inputs (top-of-sheet parameters)

| Cell | Name | Value |
|---|---|---|
| G3 | **Q** (performance ratio / derating factor) | **0.85** |
| G4 | **Iqc** (reference/STC irradiance) | **1 kW/m²** |
| I3/J3 | **Ppeak Optm** (chosen/selected PV array size) | **2,000,000 W = 2 MW** (manual input, matches Annex-VI's "2 MW" plant) |
| N3 | Zero-yield-hours count (output, see §7.4) | `=COUNTIF(N7:N8766,0)` → **384 hours/year** |
| Column G (rows 7–8766) | **G(i) — hourly global solar irradiance, W/m²** | **Raw pasted input data**, no formula (external source, e.g. PVGIS/NASA-POWER — not documented in-file) |

### 7.2 Per-hour columns

| Col | Formula (row 44 example) | Meaning |
|---|---|---|
| H | `='Annex-III'!AF47` | Hourly electricity demand, Wh (pulled from Annex-III) |
| I | `=IFERROR(H44*$G$4/(G44/1000)*$G$3,"∞")` | "Ppeak" if this ONE hour's demand had to be met entirely by solar at that hour's irradiance — an exploratory/diagnostic figure, `"∞"` at night (division by zero). **Not used for actual sizing** (the actual Ppeak is the manual 2 MW input). |
| J | `=IFERROR(I44/1000000, "∞")` | Same, in MW |
| K | `=$J$3*($G44/1000)*$G$3/$G$4` | **Egen (Wh)** = `Ppeak_selected(W) × [G(i)/1000 kW/m²] × Q / Iqc` — the standard hourly PV output model |
| L | `=K44-H44` | **Delta E = Egen − Edemand (Wh)** |
| M | `=IF(P44<>P43, SUMIFS($L$7:$L$8766,$P$7:$P$8766,P44), "")` | **SDE** — sum of Delta-E over the current contiguous same-sign "block" (only written on the first row of each block) |
| N | `=MAX(0, MIN($S$7*1000, N43 + L44))` (row 7 special-cased: `=MIN(S7*1000+L7, $S$7*1000)`) | **Battery SOC simulation (Wh)** — clipped between 0 and full capacity |
| O | `=SIGN(L44)` | Sign of Delta-E (+1 surplus, −1 deficit, 0 balanced) |
| P | `=IF(O44<>O43, P43+1, P43)` | **Block ID** — increments whenever the sign flips; groups consecutive same-sign hours |
| Q7 | `=MIN(M7:M8766)` | Worst (most negative) cumulative deficit over any single contiguous "block" of the year → **−7,141,922 Wh** |
| R7 | `=MAX(M7:M8766)` | Best cumulative surplus block → 8,860,118 Wh |
| **S7** | `=MROUND((-1*Q7/1000)/0.8*0.9, 1000)` | **Battery size (kWh)**: worst-deficit(Wh)→kWh, ÷0.8 (depth-of-discharge), ×0.9 (unclear — see §12.4), rounded to nearest 1,000 kWh → **8,000 kWh (8 MWh)** |
| Row 8767 | `H='=SUM(H7:H8766)'` (3,472,586,398 Wh), `K='=SUM(K7:K8766)'` (3,839,823,405 Wh) | Annual demand & generation totals |
| U/V/W (rows 7–58) | plain pasted numbers, "Weeks / Energy Production (Wh) / Energy Demand (Wh)" | Static weekly production-vs-demand reference table (not formula-driven) |

### 7.3 Battery-size formula, restated for Python

```
deficit_kWh = -min(SDE_per_block)/1000        # worst multi-hour deficit run
battery_kWh = round_to_nearest_1000( (deficit_kWh / 0.80) * 0.90 )
```
0.80 is almost certainly **max Depth of Discharge**. The extra `×0.90` factor is unexplained (no comment survives, and it does not read as round-trip efficiency, since RTE should divide, not multiply, on top of a DoD-adjusted figure) — **flag for the human**.

### 7.4 Zero-yield-hours metric
`N3 = COUNTIF(N7:N8766,0)` counts hours where the simulated battery SOC (col N) hits exactly 0, i.e. hours with **unserved demand**, for the battery size in S7. Result: **384 hours/year** for the 8 MWh solar+battery configuration. The workbook does **not** show a battery-size-vs-zero-hours sensitivity table — it's a single computed pair (S7 size ↔ N3 hours) for whatever S7 currently evaluates to; there's no explicit "try different battery sizes" table to replicate. A Python app should offer this as an interactive slider (recompute N/battery-status for any candidate capacity).

---

## 8. Annex-V — Wind Resource Table

Per-hour columns (row 5 header): `Date/Hour/Day/Clock/Week/Month` (all copied from Annex-III, e.g. `A6='Annex-III'!A10`), `G` = Demand Wh (`='Annex-III'!AF10`), `H` = **Wind Speed, m/s (raw pasted input data, no formula)**, `I` = `=MROUND(H6,0.5)` (rounded to nearest 0.5 m/s bin), `J` = hourly wind-energy estimate:
```
J6 = INDEX('Annex-Va'!$B$8:$B$48, MATCH($I6,'Annex-Va'!$A$8:$A$48,0)) * 4 * 1000
```
— power-curve lookup (kW at that wind-speed bin) **× 4** (hard-coded turbine multiplier — see Anomaly §12.3) **× 1000** (kW→W).

Columns **K–W**: `K` = the wind-speed bin ladder (0, 0.5, 1.0 … m/s), `L`…`W` = **per-month histogram** of hours-per-bin:
```
L6 = COUNTIF($I$6:$I$749, $K6)     ' January block (first 744 hourly rows ≈ 31 days)
M6 = COUNTIF($I$750:$I$1421, $K6)  ' February
... (one COUNTIF per month, ranges hand-picked to match each month's hour-count)
```
This builds the empirical wind-speed-frequency table that Annex-Va consumes (i.e. Annex-V→Annex-Va→feeds back into Annex-V's own J column and into Annex-Vb — a top hourly wind-speed series is both raw input AND, via its binned histogram, indirectly used to build the power curve's monthly weighting).

---

## 9. Annex-Va — Wind Turbine Power Curve & Monthly Comparison

* Turbine model referenced: **LB56-500kW WTGS** (lianbangsolar.com).
* `C4 = 6` — **Number of Turbines** (input).
* Rows 8–48: wind-speed bins 0→20 m/s (0.5 m/s steps) in col A, **rated power per single turbine (kW)** in col B (manufacturer power curve, pasted values: 0 kW below ~3 m/s cut-in, ramps to 500 kW rated by ~10.5 m/s, flat 500 kW to 18 m/s, 0 above — raw input data).
* Cols C–Z (12 month-pairs): `Frequency (Hours)` = `='Annex-V'!L6` etc. (pulled from Annex-V's histogram), `Energy ×4 Turbine (kWh)` = `=$B8*C8*$C$4` (power × hours-at-that-speed × turbine-count — **note: this one correctly uses `$C$4`=6, unlike Annex-V's hard-coded ×4**, another internal inconsistency, see §12.3).
* Row 49: `Monthly Energy Produced (kWh)` = `SUM(D8:D48)` per month.
* Row 50: `Monthly Energy Demand (kWh)` = `=GETPIVOTDATA("Total Electricity Consumption\n(Wh)",'Annex-IIIb'!$A$3,"Month","January")/1000` — pulls straight from the Annex-IIIb PivotTable.
* Row 51 / rows 54–65: Produced − Demand difference, tabulated per month (Jan +196,126 kWh; Feb −38,074; Mar −29,973; Apr +158,499; May +600,318; Jun +715,126; Jul +635,914; Aug +1,114,271; Sep +340,821; Oct +42,861; Nov −38,022; Dec −51,402 kWh) — a simple monthly-balance sanity check, separate from the hourly battery simulation done in Annex-Vb.

---

## 10. Annex-Vb — Wind Power Sizing (mirror of Annex-IV)

Same structural pattern as Annex-IV §7, with these differences:

| Cell | Value | Note |
|---|---|---|
| F2/H2 | Q = 0.85 | same performance-ratio constant, reused (odd for a wind turbine, but present) |
| F3/H3 | Iqc = 1 kW/m² | leftover from the solar template — **columns J/K ("Ppeak"/"Peak Power (MW) (PV)") are dead/unused for wind** (always `"∞"` or 0), a direct copy-paste of Annex-IV's irradiance-based Ppeak logic that doesn't apply to wind and produces no meaningful output |
| L2 | `='Annex-Va'!C4*500000` = **3,000,000 W (3 MW)** | "Ppeak Optm" — nameplate wind capacity (6 × 500 kW) |
| O3 | `=COUNTIF(O6:O8765,0)` = **937 hours/year** | Zero-yield-hours for the wind+battery combo (much higher than solar's 384 — wind is far more intermittent) |
| L (Egen) | `=VLOOKUP(G6,'Annex-Va'!A$8:B$48,2,TRUE)*'Annex-Va'!$C$4*1000` | correct turbine-count reference here (`$C$4`) |
| G | `='Annex-V'!I6` | wind-speed bin (m/s), pulled from Annex-V |
| M (Delta E), N (SDE), O (SOC), P (Sign), Q (Block ID) | identical formula pattern to Annex-IV's L/M/N/O/P | |
| **T6** | `=MROUND((-1*R6/1000)/0.8*0.9, 1000)` | **Battery size = 46,000 kWh (46 MWh)** — same 0.8/0.9 formula as solar |
| Row 8766 | `I='=SUM(I6:I8765)'` (3,472,586,398 Wh demand) `L='=SUM(L6:L8765)'` (7,120,279,200 Wh wind generation — over 2× annual demand, hence the much larger required battery) | |

---

## 11. Annex-VI — Solar PV Economic Analysis (all costs PKR unless noted)

### 11.1 Capital / BOQ (2 MW solar plant)

Reference system for unit-costing: **315 kW** (533 panels × 590 W ≈ 314 kW), scaled to the actual 2 MW plant via `Qty_actual = Qty_ref × (2,000,000/314,000)`.

| # | Item | Ref Qty @315kW | Actual Qty @2MW | Unit | Unit cost (PKR, "Ref BOQ") | Unit cost (PKR, "Ref Website") | Total cost @ Ref BOQ rate (PKR) |
|---|---|---|---|---|---|---|---|
| 1 | Solar Panels (590 W rated) | 533 Nos. | `MROUND(2e6/590,10)`=3,390 Nos. | Nos. | 82 /W | 94 /W | `=82*2,000,000` = **164,000,000** |
| 2 | Inverter (500 kW rated) | 2 Nos. | 4 Nos. | Nos. | — | — | — |
| 3 | DC Cables | 5,878 m | `MROUND(C*(2e6/314000),100)`=37,400 m | m | — | | |
| 4 | AC Cables | 55 m | 350.3 m | m | | | |
| 5 | Grounding Cable (PV) | 156 m | 993.6 m | m | | | |
| 6 | Grounding Cable (Structure) | 95 m | 605.1 m | m | | | |
| 7 | Grounding Cable (Inverter) | 10 m | 63.7 m | m | | | |
| 8 | DC Breakers | 31 Nos. | 197.5 Nos. | Nos. | | | |
| 9 | LV Switchgear | 1 Nos. | 6.4 Nos. | Nos. | | | |
| 10 | Cable Trays & Conduits | 1 Lot | 6.4 Lot | Lot | | | |
| 11 | Panel Mounting Structure | 1 Lot | 1 Lot | Lot | | | |
| 12 | Civil Work | 1 Lot | 1 Lot | Lot | | | |
| 13 | Water Cleaning System | 1 Lot | 1 Lot | Lot | | | |
| 14 | Transport Cost | 1 Lot | 1 Lot | Lot | | | |
| 15 | Commissioning + 3-month O&M | 1 Lot | 1 Lot | Lot | | | |
| 16 | **Battery System** | — | **8 MWh** (manual literal, matches Annex-IV!S7) | MWh | 50,000,000 /MWh (comment: "PKR 50 Million/MWh") | — (40,000,000/MWh "Ref Website") | `=50,000,000*8` = **400,000,000** |
| 17 | Cables & distribution infrastructure | 1 Lot | 1 Lot | Lot | "*ChatGPT Estimation" | same | 40,000,000 |
| — | **Grand Total Capital Cost** | | | | | | `=SUM(H7:H29)` = **604,000,000 PKR** (Ref-BOQ column) / 268,000,000 PKR (Ref-Website column) |
| — | Grand Total Capital Cost (Euro) | | | | | | `=H30/330` = **1,830,303 €** |

Land cost (@ ~1 hectare/MW, 5 acres used):
| Item | Qty | Unit cost | Total (PKR) | Comment |
|---|---|---|---|---|
| 17A Buying Land | 5 Acres | 11,616,000/acre | 58,080,000 | — |
| 17B Lease Private Land (30 yr) | 5 Acres | `200,000*30`=6,000,000/acre | 30,000,000 | comment: "@ 200,000 PKR/acre/annum" |
| 17C Lease Govt Land (30 yr) | 5 Acres | `3000*10+5000*10+8000*10`=160,000×5=800,000/acre | 4,000,000 | comment: "@3,000 PKR/acre-10y, 5,000-next 10y, 8,000-next 10y" |

### 11.2 Operating cost / present-value (O&M)

| Input | Value | Cell |
|---|---|---|
| **Inflation rate** | **8%** | N37/O37 |
| **Discount rate** | **10%** | N38/O38 |
| Insurance | 0.5% of capital cost/year, 30 years | C40 |
| O&M | 1.8 $/kW/year, 30 years | C41 |
| Battery replacement | full replacement after "12+18" years (i.e. once, in year 12; the "+18" is presumably a note that it lasts a further 18 yrs) | C42 |
| Inverter replacement | 4 Nos. after 12 yrs, cost = 15% of (fixed-cost minus battery) ÷ 4 | C43/G43 |
| Govt land lease (again) | 30 yrs | C44/G44 |

Present-value cash-flow table (rows 39–71, 30 years): `Cfo (year-1 cash flow) = (Insurance% × CapitalCost) + (O&M$/kW/yr × 2000kW × 280 PKR/$)` = **4,028,000 PKR/yr**. Then:
```
O_year_n = $N$39 * (1+$N$37%)^(n-1)          ' cash flow, inflated at 8%/yr
P_year_n = O_year_n / (1+$N$38%)^n            ' present value, discounted at 10%/yr
```
Total O&M+Insurance present value = `SUM(P42:P71)` = **85,257,391 PKR**. Grand Total Opex (incl. battery+inverter+land replacement) = **519,857,391 PKR**.

### 11.3 LCOE

```
Total Cost (Capex+Opex) = Total Capital Fixed Cost (604,000,000) + Total Opex PV (519,857,391)
                         = 1,123,857,391 PKR  (3,405,628 €)
Total Energy (30 yrs)   = ('Annex-IV'!H8767 / 1000) * 30      ← NOTE: H8767 is the DEMAND sum, not generation (K8767)
                         = 104,177,592 kWh
LCOE = Total Cost / Total Energy = 10.79 PKR/kWh = 0.0327 €/kWh = 3.27 cents/kWh
```
No ROI / IRR / NPV / payback-period formula exists anywhere in the workbook — only LCOE via the simple total-cost ÷ total-kWh method above (partially discounted: Opex is a true PV sum, but Capex is not discounted, and the energy denominator applies no demand growth or degradation).

References cited (rows 56–64): Gravity Engineering Solutions (solar system cost, PK), ZSW (land use of ground-mounted PV), Renewables First (Solar Fast Track guidebook, PK), SecureTechnologies.pk (1 MW solar cost PK 2025), IRENA (2022 renewable cost report), Ritar Power (BESS pricing), SolarTechOnline (wind turbine cost guide), Saurenergy (battery news), and the in-house "Solar PV System 315 kW (BOQ)".

---

## 12. Annex-VII — Wind Power Economic Analysis (mirror of Annex-VI)

Same structure as §11, key differences:

| Item | Value |
|---|---|
| Wind Turbine (500 kW rated) | 6 Nos., unit cost derived circularly as `=G13` (self-referential "PKR/Watt" back-calculated from the sum of other line items ÷ nameplate W) = 980.87 PKR/W, `Total=E8*'Annex-Vb'!M2` (M2=3,000,000 W) = **2,942,600,000 PKR** |
| Inverter (500 kW) | 2 Nos., `=100,000*280*6/3` = 56,000,000 PKR |
| Auxiliaries/Civil | `=400,000*280*6/3` = 224,000,000 PKR |
| Electrical collection system | `='Annex-VI'!G43*2` = 15,300,000 PKR |
| Substation | `=SUM(G8:G11)` = 1,471,300,000 PKR |
| Battery System | **46 MWh** (literal, matches Annex-Vb!T6), 50,000,000 PKR/MWh → 2,300,000,000 PKR |
| Distribution infra | 40,000,000 PKR |
| **Grand Total Capital Cost** | `=SUM(F7:F29)` = **5,282,600,000 PKR** (16,007,879 €) |
| Land (150 acres govt-lease, vs solar's 5 acres — wind farm footprint much larger) | O&M 3.5% of fixed cost/yr (vs solar's flat 1.8 $/kW/yr) |
| Grand Total Opex (30yr PV) | 6,794,099,464 PKR |
| **Total Cost (Capex+Opex)** | 12,076,699,464 PKR (36,596,059 €) |
| Total Energy (30yr) | same formula as solar, `('Annex-IV'!H8767/1000)*30` = 104,177,592 kWh — **uses the SOLAR demand sum again (Annex-IV, not Annex-Vb), same value, so this line is fine (same site demand) but again is DEMAND not wind GENERATION** |
| **LCOE (Wind)** | **115.92 PKR/kWh = 0.351 €/kWh = 35.1 cents/kWh** — over 10× more expensive than solar, driven by the enormous wind BOQ (turbine unit cost formula looks circular/self-referential — flag for human, see §12.5) |

---

## 13. Defined Names, Comments, Units

### 13.1 Defined names
None (`workbook.defined_names` is empty).

### 13.2 Cell comments (threaded comments) recovered
Only two sheets retain their actual threaded-comment **text** (the rest — Annex-II, Annex-III, Annex-IV, Annex-Vb — still have comment *markers* on certain cells, but Excel/openpyxl only exposes a "[Threaded comment] your version of Excel..." placeholder; the real authored text for those is not recoverable from this file):

**Annex-VI:**
| Cell | Comment |
|---|---|
| G27 (Battery unit cost) | "PKR 50Millon/MWh" |
| G34, I34 (Land buy price) | "2400 PKR/Sq yard (Category VI - Slum areas open fields)" |
| G35, I35 (Private land lease) | "@ 200,000 PKR/acre/annum" |
| G36 (Govt land lease) | "@ 3000 PKR/acre - 10y / 5000 PKR/acre - next 10y / 8000 PKR/acre - next 10y" |

**Annex-VII:** identical set of comments (E27/E34/G34/E35/G35/E36/G36 as above) plus `F36`: **"5$/acre/year"** (an apparent USD unit-cost note attached to the govt land-lease line, inconsistent with the PKR figures elsewhere on that row — worth asking the human which is authoritative).

**Sheets with comment markers but unrecoverable text** (present in the file's legacy `comments1–4.xml` but the corresponding `threadedComments` XML part is missing, so only the "your version of Excel..." placeholder remains):
* Annex-II: C6, D6, K6, R6 (near the Category A/B/C/Misc. header row)
* Annex-III: O8, V8 (near category C / Misc. headers)
* Annex-IV: K5 (the "Egen @ Ppeak=2MW" header cell)
* Annex-Vb: L4 (the corresponding "Egen @ Ppeak=8MW" header cell — note this label says 8 MW but the actual wind Ppeak is 3 MW; likely a stale copy-paste label, see §12)

### 13.3 Units glossary (where they differ across sheets)

| Sheet | Power unit | Energy unit |
|---|---|---|
| Annex-I | W (appliance power), connected load summed to **MW** | Wh (per-appliance connected load) |
| Annex-II | — | Wh/household, kWh all households |
| Annex-III | — | Wh per hour, **GWh** for the annual total (AG10) |
| Annex-IV | W/MW (Ppeak) | Wh (H, K, L, N, Q, R columns), **kWh** for battery size (S) |
| Annex-V | — | Wh (demand), Wh (wind energy estimate J) |
| Annex-Va | kW (turbine power curve) | kWh (monthly energy) |
| Annex-Vb | W/MW (Ppeak, mostly unused) | Wh (I,L,M,N,R,S), **kWh** for battery size (T) |
| Annex-VI/VII | — | kWh (LCOE denominator), all costs **PKR** (Euro columns divide by 330) |

---

## 14. Anomalies / Open Questions Requiring Human Clarification

These were found by systematically comparing every day's actual Annex-III→Annex-II formula reference against the calendar rules stated in Annex-II's own labels (see `/tmp/wb_explore/annexIII_daymap_segments2.txt` for the full audit trail), and are **not guesses** — each is directly verifiable in the file.

1. **Two of Annex-II's 19 day-type blocks are defined but never used** by Annex-III:
   * "Peak Monsoon: June 16 – August 15 (weekday)" (Annex-II rows 312–335) — Annex-III instead continues using the "Early Monsoon" weekday block for July 16–Aug 2, then incorrectly substitutes the **April** weekday block for Aug 3–13.
   * "Late Summer: Sep 15 – Oct 31 (weekday)" (Annex-II rows 387–410) — Annex-III instead uses the **April** weekday block for essentially the entire Sep 16 – Oct 30 period.
   * In both cases the corresponding **weekend** blocks (Peak Monsoon Weekends, Late Summer Weekends) ARE correctly applied on the matching Saturdays/Sundays — only the weekday formula-drag appears to have been botched, most likely an Excel fill-down/copy error that pasted the wrong source range across ~6 weeks of weekday cells twice.
   * **Decision needed:** should the Python rebuild (a) faithfully reproduce this exact (buggy) 365-day mapping as historical ground truth, or (b) fix it to use the seasonally-"correct" blocks per Annex-II's own labels? This changes total annual demand, peak load, and battery sizing non-trivially (the April profile is a shoulder-season profile, likely lower-demand than true peak-monsoon/late-summer, especially given cooling-load appliances).

2. **One holiday date is off by one day.** Annex-II's label reads "January 16" as a public holiday, but the actual hard-coded block was pasted onto **January 15**. All other 6 public holidays and all 8 festival days are correctly placed.

3. **Wind turbine count inconsistency.** Annex-Va's `C4=6` (turbines) is used correctly in Annex-Va's own energy calc and in Annex-Vb's `L` column (`...*'Annex-Va'!$C$4*1000`), but Annex-V's `J` column (hourly wind energy estimate) hard-codes `×4` instead of referencing `C4`. This makes Annex-V's own "Eg (Prod)" column understate generation by 1/3 relative to Annex-Va/Annex-Vb (though Annex-V's J column doesn't appear to feed into any downstream sizing calc, so may be inert — but should be fixed/removed either way in the rebuild).

4. **Battery-size formula's `×0.9` factor is undocumented.** `Battery(kWh) = ROUND_1000( (max_deficit_kWh / 0.80) * 0.90 )`. 0.80 reads naturally as max Depth-of-Discharge. The subsequent `×0.90` is unexplained by any surviving comment — possibilities include a battery-efficiency derate, a safety margin reduction (which would be unusual to apply as a *reduction* right after inflating for DoD), or a data-entry mistake for what should have been `÷0.9` (round-trip efficiency). **Ask the human which interpretation is intended** before hard-coding this in Python.

5. **The two battery-size figures used in the BOQs (Annex-VI!E27 = 8 MWh, Annex-VII!C27 = 46 MWh) are hand-typed literals, not live formula links** to Annex-IV!S7 / Annex-Vb!T6. They currently match the computed values, but will silently go stale if any upstream input (irradiance data, wind data, demand, Q, DoD, etc.) changes. The Python app should make this a live computed dependency.

6. **Annex-VI/VII's LCOE energy denominator uses the DEMAND sum, not the generation sum**, despite being labeled "Total Energy Generation (30 Years)" (`='Annex-IV'!H8767/1000)*30` where H8767 is `SUM` of column H = demand, not column K = generation). Also, this flat calculation ignores the 25%-by-2030 demand-growth projection Annex-III computes elsewhere (§4.4) — that growth curve appears to be entirely orphaned/unused in the whole workbook. **Ask the human**: (a) should LCOE be based on served demand or actual PV generation (they differ — Annex-IV generates 3,839,823,405 Wh/yr vs demand of 3,472,586,398 Wh/yr, i.e. ~10% curtailment/oversizing), and (b) should the growth projection feed into system sizing / LCOE at all, or is it vestigial?

7. **Annex-Vb's header cell L4 says "Egen @ Ppeak=8MW"** (a label seemingly copy-pasted from a different draft), but the actual computed wind Ppeak (L2 = `'Annex-Va'!C4*500000`) is **3 MW** (6×500kW). The J/K "Ppeak"/"Peak Power(MW)(PV)" columns in Annex-Vb are leftover solar-irradiance-based logic that produces `"∞"` or near-zero and is not used for the wind sizing at all (wind generation comes entirely from column L's turbine-power-curve VLOOKUP). Safe to simply drop J/K from the Python port for the wind sheet.

8. **Annex-VII's wind turbine unit cost is self-referential**: `E8 = G13` and `G13 = SUM(G8:G12)/'Annex-Vb'!M2` — i.e. the "per-watt cost" used to price the turbines is derived by summing several BOQ line items (including the turbines themselves, inverters, and civil works) and dividing by system wattage, then that per-watt figure is used again to compute the turbine line's own Total Cost. This is a circular-looking calculation chain that Excel resolves fine here (because `E8*M2` and `SUM(G8:G12)` aren't actually the same cell), but its economic logic (cost-per-watt back-derived from a sum that includes the thing being costed) should be reviewed with the human before being ported as-is — it doesn't look like an intentional cost-estimation methodology so much as a shortcut that happened to produce a plausible-looking number.

9. **Annex-VII land-lease line has two inconsistent unit costs**: cell comment on F36 says "5$/acre/year" (USD) while the sheet's other land-cost figures (E34–G36) are all quoted in PKR/acre. Needs clarification on whether this is a currency-conversion oversight.

10. **The comment/assumption text on 4 sheets' cells (Annex-II C6/D6/K6/R6, Annex-III O8/V8, Annex-IV K5, Annex-Vb L4) is unrecoverable** — the file retains a comment *marker* but Excel's newer "threaded comment" storage for these specific cells was not preserved when the file was last saved (only 2 of 6 comment-files kept their real text). If these assumptions matter, the human who authored them will need to restate them.

---

## 15. Appendix

* Full Annex-I dump (every cell, formula + value): `/tmp/wb_explore/dump_Annex-I.txt`
* Full Annex-II dump: `/tmp/wb_explore/dump_Annex-II.txt`
* Full Annex-IIIa / IIIb / Va / VI / VII dumps: `/tmp/wb_explore/dump_Annex-IIIa.txt`, `dump_Annex-IIIb.txt`, `dump_Annex-Va.txt`, `dump_Annex-VI.txt`, `dump_Annex-VII.txt`
* Header/sample/last-row/formula-pattern extracts for the 8,760-row sheets: `/tmp/wb_explore/BIG_Annex-III.txt`, `BIG_Annex-IV.txt`, `BIG_Annex-V.txt`, `BIG_Annex-Vb.txt`, `BIG_Annex-DP_for_Pivot.txt`
* Raw Annex-III array-formula text samples (INDEX lookups): `/tmp/wb_explore/annexIII_arrayformulas.txt`
* Complete 365-day → Annex-II block mapping (audit trail for §4/§14): `/tmp/wb_explore/annexIII_daymap_segments2.txt`, `/tmp/wb_explore/annexIII_daymap_full.txt`
* Recovered threaded-comment XML: `/tmp/wb_explore/xlsx_extract/xl/threadedComments/threadedComment1.xml` (Annex-VI), `threadedComment2.xml` (Annex-VII)

All of the above remain on disk for follow-up spot-checks; the source `.xlsx` itself was never modified (read-only mount).
