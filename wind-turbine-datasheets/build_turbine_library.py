"""One-off script: builds Wind_Turbine_Library.xlsx from the manufacturer datasheets in this folder.

Not part of the app — run once to produce the reviewable Excel file, then discarded/kept for reference.
Power curves are digitized from each datasheet's own published table where available (linearly
interpolated to 0.5 m/s steps to match every other curve's resolution), or approximated with the
standard cubic power-curve model (P = Prated * (v^3 - vcutin^3)/(vrated^3 - vcutin^3)) where the
datasheet only published a chart image, not a numeric table -- flagged in the Data Quality column.
"""
import numpy as np
import pandas as pd

# --- 1. Turbine master list -------------------------------------------------

turbines = [
    {
        "company": "Leitwind", "model": "LTW42-250", "rated_power_kw": 250,
        "hub_height_m": 28, "rotor_diameter_m": 42, "iec_class": "IIIA+",
        "cut_in_ms": 2.5, "rated_wind_speed_ms": 14.0, "cut_out_ms": 20,
        "source_file": "turbine-leitwind_ltw42-500-JlZDYId5Npw.pdf",
        "data_quality": "Exact from datasheet (points given at 1 m/s+, linearly interpolated to 0.5 m/s)",
        "notes": "Dual-rated 250|500 kW model, same rotor/tower. Low-wind IEC class.",
    },
    {
        "company": "Leitwind", "model": "LTW42-500", "rated_power_kw": 500,
        "hub_height_m": 39, "rotor_diameter_m": 42, "iec_class": "IIIA+",
        "cut_in_ms": 2.5, "rated_wind_speed_ms": 10.5, "cut_out_ms": 20,
        "source_file": "turbine-leitwind_ltw42-500-JlZDYId5Npw.pdf",
        "data_quality": "Exact from datasheet (points given at 1 m/s+, linearly interpolated to 0.5 m/s)",
        "notes": "Dual-rated 250|500 kW model, same rotor/tower. Low-wind IEC class.",
    },
    {
        "company": "Norwin", "model": "47-ASR-500", "rated_power_kw": 500,
        "hub_height_m": 50, "rotor_diameter_m": 47, "iec_class": "IB / IIA",
        "cut_in_ms": 3.5, "rated_wind_speed_ms": 12.5, "cut_out_ms": 25,
        "source_file": "Brochure - 47-ASR-500 kw.pdf",
        "data_quality": "Exact from datasheet (1 m/s points, linearly interpolated to 0.5 m/s)",
        "notes": ("Hub height on conical tower is 40-65m per datasheet (site-specific); 50m used as a "
                  "representative default -- edit per actual tower ordered. Active Stall Regulation, "
                  "designed for high wind / turbulence (higher IEC class than the Leitwind/Ghrepower units)."),
    },
    {
        "company": "Ghrepower", "model": "GP56-400", "rated_power_kw": 400,
        "hub_height_m": 51, "rotor_diameter_m": 56, "iec_class": "S (DIIIA)",
        "cut_in_ms": 3.0, "rated_wind_speed_ms": 9.5, "cut_out_ms": 18,
        "source_file": "ZY1.603.052GSV1.01_GP56-Series-WTGS-Specification-20230410.pdf",
        "data_quality": "Exact from datasheet (published natively at 0.5 m/s steps)",
        "notes": "Low-wind-speed design (large rotor for its rating). Permanent-magnet direct drive.",
    },
    {
        "company": "Ghrepower", "model": "GP56-500", "rated_power_kw": 500,
        "hub_height_m": 51, "rotor_diameter_m": 56, "iec_class": "S (DIIIA)",
        "cut_in_ms": 3.0, "rated_wind_speed_ms": 10.5, "cut_out_ms": 18,
        "source_file": "ZY1.603.052GSV1.01_GP56-Series-WTGS-Specification-20230410.pdf",
        "data_quality": "Exact from datasheet (published natively at 0.5 m/s steps)",
        "notes": ("Low-wind-speed design (large rotor for its rating). Permanent-magnet direct drive. "
                  "Power curve is numerically identical to this app's existing default 'LB56-500kW' "
                  "turbine -- almost certainly the same base design/product family."),
    },
    {
        "company": "Goldwind", "model": "GW82/1500", "rated_power_kw": 1500,
        "hub_height_m": 70, "rotor_diameter_m": 82, "iec_class": "IIIA",
        "cut_in_ms": 3.0, "rated_wind_speed_ms": 10.3, "cut_out_ms": 22,
        "source_file": "GW 1S MW-ENG-DIGITAL.pdf",
        "data_quality": "APPROXIMATED -- datasheet gives only a chart image, no numeric table. "
                         "Standard cubic power-curve model fit to cut-in/rated/cut-out speeds and rated power.",
        "notes": "Hub height offered at 70m or 85m; 70m used as default -- edit per actual tower ordered.",
    },
    {
        "company": "Goldwind", "model": "GW87/1500", "rated_power_kw": 1500,
        "hub_height_m": 75, "rotor_diameter_m": 87, "iec_class": "S",
        "cut_in_ms": 3.0, "rated_wind_speed_ms": 9.9, "cut_out_ms": 22,
        "source_file": "GW 1S MW-ENG-DIGITAL.pdf",
        "data_quality": "APPROXIMATED -- datasheet gives only a chart image, no numeric table. "
                         "Standard cubic power-curve model fit to cut-in/rated/cut-out speeds and rated power.",
        "notes": "Hub height offered at 75m or 85m; 75m used as default -- edit per actual tower ordered.",
    },
    {
        "company": "AN Wind Energie (Bonus)", "model": "AN Bonus 1000/54", "rated_power_kw": 1000,
        "hub_height_m": 60, "rotor_diameter_m": 54.2, "iec_class": "not specified by manufacturer",
        "cut_in_ms": 3.0, "rated_wind_speed_ms": 15.0, "cut_out_ms": 25,
        "source_file": "AN Bonus 1000_54 - 1,00 MW - Wind turbine.pdf",
        "data_quality": "APPROXIMATED -- datasheet gives only a chart image (power + Cp vs wind speed), no "
                         "numeric table. Standard cubic power-curve model fit to cut-in/rated/cut-out speeds "
                         "and rated power.",
        "notes": ("Manufacturer (AN Wind Energie GmbH, Germany) inactive since 2005 -- older-generation design. "
                  "Hub height offered at 50/60/70m; 60m used as default -- edit per actual tower ordered. "
                  "Survival wind speed 60 m/s. Power density 434.8 W/m^2 (moderate specific power)."),
    },
    {
        "company": "UNAVAILABLE", "model": "Adwen AD 5-135", "rated_power_kw": 5000,
        "hub_height_m": None, "rotor_diameter_m": 135, "iec_class": None,
        "cut_in_ms": None, "rated_wind_speed_ms": None, "cut_out_ms": None,
        "source_file": "(user-provided link: en.wind-turbine-models.com -- blocked; thewindpower.net -- fully paywalled)",
        "data_quality": "NO DATA -- every field is behind a premium paywall.",
        "notes": ("This is a 5 MW OFFSHORE turbine (formerly Areva M5000-135), a different scale/class entirely "
                  "from a rural mini-grid -- likely not useful for this project even if data were available."),
    },
    {
        "company": "UNAVAILABLE", "model": "ACSA A17/90", "rated_power_kw": 90,
        "hub_height_m": None, "rotor_diameter_m": 17, "iec_class": None,
        "cut_in_ms": None, "rated_wind_speed_ms": None, "cut_out_ms": None,
        "source_file": "(user-provided link: en.wind-turbine-models.com -- blocked)",
        "data_quality": "NO DATA -- the exact model could not be retrieved (site blocked); search fallback "
                         "surfaced a different model (ACSA A29/225), not this one.",
        "notes": "Rated power/rotor diameter above are read off the model name (A17/90 = 17m rotor, 90kW), not confirmed from a real datasheet.",
    },
]

turbines_df = pd.DataFrame(turbines)

# --- 2. Power curves (long format: model, wind_speed_ms, power_kw) --------

def cubic_curve(rated_kw, v_cutin, v_rated, v_cutout, speeds):
    p = np.zeros_like(speeds, dtype=float)
    ramp = (speeds >= v_cutin) & (speeds < v_rated)
    p[ramp] = rated_kw * (speeds[ramp] ** 3 - v_cutin ** 3) / (v_rated ** 3 - v_cutin ** 3)
    flat = (speeds >= v_rated) & (speeds <= v_cutout)
    p[flat] = rated_kw
    return p

def interp_curve(known_speeds, known_powers, v_cutout, speeds):
    p = np.interp(speeds, known_speeds, known_powers, left=0, right=0)
    p[speeds > v_cutout] = 0
    return p

all_speeds = np.arange(0, 25.5, 0.5)  # covers every model's cut-out (Norwin's, the highest, is 25 m/s)

curve_rows = []

# Leitwind LTW42-250 / LTW42-500 -- published points (m/s, kW-250, kW-500)
leitwind_pts = [
    (2.5, 3, 0), (3.0, 7, 0), (4.0, 22, 14), (5.0, 47, 40), (6.0, 81, 74), (7.0, 128, 124),
    (8.0, 190, 188), (9.0, 234, 270), (10.0, 249, 360), (11.0, 250, 439), (12.0, 250, 483),
    (13.0, 250, 496), (14.0, 250, 500),
]
lw_speeds = [p[0] for p in leitwind_pts]
lw_250 = [p[1] for p in leitwind_pts]
lw_500 = [p[2] for p in leitwind_pts]
for model, powers, cutout in [("LTW42-250", lw_250, 20), ("LTW42-500", lw_500, 20)]:
    # datasheet states power stays flat at rated from the last tabulated point (14 m/s) to cut-out (20 m/s)
    speeds_k = lw_speeds + [cutout]
    powers_k = powers + [powers[-1]]
    p = interp_curve(speeds_k, powers_k, cutout, all_speeds)
    for v, kw in zip(all_speeds, p):
        curve_rows.append({"model": model, "wind_speed_ms": v, "power_kw": round(float(kw), 2)})

# Norwin 47-ASR-500 -- published points (m/s, kW)
norwin_pts = [(3,3),(4,20),(5,52),(6,90),(7,155),(8,236),(9,338),(10,420),(11,470),(12,495),
              (13,500),(14,500),(15,500),(16,500),(17,500),(18,500),(19,500),(20,500),
              (21,500),(22,500),(23,500),(24,500),(25,500)]
nw_speeds = [p[0] for p in norwin_pts]
nw_power = [p[1] for p in norwin_pts]
p = interp_curve(nw_speeds, nw_power, 25, all_speeds)
for v, kw in zip(all_speeds, p):
    curve_rows.append({"model": "47-ASR-500", "wind_speed_ms": v, "power_kw": round(float(kw), 2)})

# Ghrepower GP56-500 / GP56-400 -- published natively at 0.5 m/s steps
gp500_pts = [(3.0,5.8),(3.5,16.8),(4.0,31.5),(4.5,50.2),(5.0,73.0),(5.5,100.8),(6.0,134.1),(6.5,171.0),
             (7.0,213.8),(7.5,262.7),(8.0,317.8),(8.5,370.3),(9.0,417.4),(9.5,455.5),(10.0,483.8),(10.5,500.0)]
gp400_pts = [(3.0,5.8),(3.5,16.8),(4.0,31.5),(4.5,50.2),(5.0,73.0),(5.5,100.8),(6.0,134.1),(6.5,171.0),
             (7.0,213.8),(7.5,261.9),(8.0,309.3),(8.5,352.4),(9.0,387.2),(9.5,400.0)]
for model, pts, rated, cutout in [("GP56-500", gp500_pts, 500.0, 18), ("GP56-400", gp400_pts, 400.0, 18)]:
    speeds_k = [p[0] for p in pts]
    powers_k = [p[1] for p in pts]
    # flat at rated power from the last known point to cut-out
    speeds_k = speeds_k + [cutout]
    powers_k = powers_k + [rated]
    p = interp_curve(speeds_k, powers_k, cutout, all_speeds)
    for v, kw in zip(all_speeds, p):
        curve_rows.append({"model": model, "wind_speed_ms": v, "power_kw": round(float(kw), 2)})

# Goldwind GW82/1500, GW87/1500 & AN Bonus 1000/54 -- APPROXIMATED (cubic model; no numeric table published)
for model, v_cutin, v_rated, v_cutout, rated in [
    ("GW82/1500", 3.0, 10.3, 22, 1500.0),
    ("GW87/1500", 3.0, 9.9, 22, 1500.0),
    ("AN Bonus 1000/54", 3.0, 15.0, 25, 1000.0),
]:
    p = cubic_curve(rated, v_cutin, v_rated, v_cutout, all_speeds)
    for v, kw in zip(all_speeds, p):
        curve_rows.append({"model": model, "wind_speed_ms": v, "power_kw": round(float(kw), 2)})

curves_df = pd.DataFrame(curve_rows)

# --- 3. Write workbook -------------------------------------------------------

instructions = pd.DataFrame({"Instructions": [
    "'Turbine Library' sheet: one row per turbine model/rating -- company, rated power, hub height, "
    "rotor diameter, IEC wind class, cut-in/rated/cut-out speed, data source file, and a Data Quality "
    "note (whether the power curve below is exact-from-datasheet or an approximated cubic-model fit).",
    "'Power Curves' sheet: long/tidy format (one row per model x wind-speed bin, 0-20 m/s in 0.5 m/s "
    "steps) -- filter by the 'model' column to get one turbine's full curve. This is the same shape as "
    "this app's other 'day-type'-style tables, so it can be read directly with pandas (pd.read_excel).",
    "Three models (Bonus B54/1000, Adwen AD 5-135, ACSA A17/90) could not be retrieved -- the source "
    "site blocked scraping and/or paywalled the specs. They're listed in the Turbine Library sheet with "
    "blank power-curve/speed fields and a note explaining why, rather than guessed.",
    "Review this file, edit/correct anything, then say so -- it will be copied into data/ as the app's "
    "wind-turbine library once approved.",
]})

out_path = "Wind_Turbine_Library.xlsx"
with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
    workbook = writer.book
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1, "text_wrap": True})

    instructions.to_excel(writer, sheet_name="Instructions", index=False)
    turbines_df.to_excel(writer, sheet_name="Turbine Library", index=False)
    curves_df.to_excel(writer, sheet_name="Power Curves", index=False)

    for sheet_name, df in [("Instructions", instructions), ("Turbine Library", turbines_df), ("Power Curves", curves_df)]:
        ws = writer.sheets[sheet_name]
        for col_idx, col_name in enumerate(df.columns):
            ws.write(0, col_idx, col_name, header_fmt)
            max_len = int(df[col_name].astype(str).str.len().max() or 10)
            width = max(12, min(60, max_len + 2))
            ws.set_column(col_idx, col_idx, width)
        ws.freeze_panes(1, 0)

print("Wrote", out_path)
print(turbines_df[["company", "model", "rated_power_kw", "data_quality"]].to_string(index=False))
