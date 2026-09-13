"""Step 2 — Hourly Load Profile.

Ported from notebooks/02_Hourly_Load_Profile.ipynb. The workbook-extraction steps (§2.2/§2.3, which
need openpyxl + the source .xlsx) are one-time, already-done notebook work — their output
(default_daytype_profiles.csv, and the editable calendar-rule tables) is what this module loads. The
app's job is running the *editable* rule-based calendar (§2.9, the project's default going forward)
live against whatever the user edits, not re-deriving the as-implemented workbook calendar.
"""
import re
import pandas as pd
import numpy as np

from .paths import DATA_DIR

_MMDD_RE = re.compile(r"^\d{2}-\d{2}$")


def load_defaults() -> dict:
    """Load the day-type profile library and the three editable calendar-rule tables."""
    return {
        "daytype_profiles": pd.read_csv(DATA_DIR / "default_daytype_profiles.csv"),
        "season_periods": pd.read_csv(DATA_DIR / "default_season_periods.csv"),
        "public_holidays": pd.read_csv(DATA_DIR / "default_public_holidays.csv"),
        "festival_holidays": pd.read_csv(DATA_DIR / "default_festival_holidays.csv"),
        "demand_settings": load_demand_settings(),
    }


def load_demand_settings() -> dict:
    """Project start year / duration / load-growth-rate settings for Demand Setup's own growth-
    projection chart — a Demand-Setup-scoped copy of the growth-rate concept, independent of the ROI
    cash-flow's own annual_load_growth_pct (which stays scenario-specific on Financials/Results).
    Also carries the optional load-randomness overlay (load_randomness_pct, random_seed) — see
    apply_load_randomness()."""
    path = DATA_DIR / "default_demand_settings.csv"
    defaults = {"project_start_year": 2026, "project_duration_years": 30, "annual_load_growth_pct": 3.0,
                "load_randomness_pct": 0.0, "random_seed": 42}
    if not path.exists():
        return defaults
    row = pd.read_csv(path).iloc[0]
    return {
        "project_start_year": int(row["project_start_year"]),
        "project_duration_years": int(row["project_duration_years"]),
        "annual_load_growth_pct": float(row["annual_load_growth_pct"]),
        "load_randomness_pct": float(row["load_randomness_pct"]) if "load_randomness_pct" in row else defaults["load_randomness_pct"],
        "random_seed": int(row["random_seed"]) if "random_seed" in row else defaults["random_seed"],
    }


def save_demand_settings(settings: dict) -> None:
    pd.DataFrame([settings]).to_csv(DATA_DIR / "default_demand_settings.csv", index=False)


def apply_load_randomness(hourly_profile_df: pd.DataFrame, randomness_pct: float, seed: int) -> pd.DataFrame:
    """Overlay realistic hour-to-hour variability on the deterministic demand profile.

    Method: multiplicative Gaussian noise per hour, Demand_actual(h) = Demand(h) x (1 + eps_h), with
    eps_h ~ Normal(0, randomness_pct/100), independently drawn for every hour of the year and clipped
    to +/-3 standard deviations so no single hour swings unrealistically. The same factor is applied to
    every category column for a given hour, so totals stay internally consistent (total_wh always
    equals the sum of the category columns) and the noise reads as genuine demand uncertainty rather
    than one category behaving oddly.

    randomness_pct=0 (the default) returns the profile unchanged — the exact deterministic curve the
    calendar/day-type rules produce, matching the workbook methodology. A fixed seed makes results
    reproducible between recomputes; pick a new seed to draw a different random pattern.
    """
    if not randomness_pct:
        return hourly_profile_df
    rng = np.random.default_rng(int(seed))
    sigma = randomness_pct / 100
    noise = rng.normal(loc=0.0, scale=sigma, size=len(hourly_profile_df))
    noise = np.clip(noise, -3 * sigma, 3 * sigma)
    factor = np.clip(1 + noise, 0.05, None)  # never let an hour go to zero/negative demand

    out = hourly_profile_df.copy()
    for col in ("A_wh", "B_wh", "C_wh", "Misc_wh", "total_wh"):
        if col in out.columns:
            out[col] = out[col] * factor
    return out


def count_period_daytype_days(season_periods_df: pd.DataFrame, year: int = 2026) -> pd.DataFrame:
    """Per season period, how many of its days are real weekdays vs. real weekends (Sat/Sun) in the
    given year — so the UI can show e.g. "January: 23 weekday / 8 weekend" instead of leaving it
    ambiguous whether a whole month is treated as "weekend"."""
    dates = pd.date_range(f"{year}-01-01", periods=365, freq="D")
    mmdd = dates.strftime("%m-%d")
    is_weekend = dates.weekday >= 5

    rows = []
    for _, period in season_periods_df.iterrows():
        in_period = (mmdd >= period["start_mmdd"]) & (mmdd <= period["end_mmdd"])
        rows.append({
            "period_name": period["period_name"],
            "weekday_days": int((in_period & ~is_weekend).sum()),
            "weekend_days": int((in_period & is_weekend).sum()),
        })
    return pd.DataFrame(rows)


def build_power_lookup(appliances_df: pd.DataFrame, misc_loads_df: pd.DataFrame) -> pd.DataFrame:
    """One combined (category, item) -> power_w lookup, covering both household appliances and Misc. loads."""
    appliance_power = appliances_df[["category", "appliance", "power_w"]].rename(columns={"appliance": "item"})
    misc_power = misc_loads_df[["appliance", "power_w"]].rename(columns={"appliance": "item"})
    misc_power.insert(0, "category", "Misc")
    return pd.concat([appliance_power, misc_power], ignore_index=True)


def sync_daytype_profiles(daytype_profiles_df: pd.DataFrame, appliances_df: pd.DataFrame,
                           misc_loads_df: pd.DataFrame) -> pd.DataFrame:
    """Keep the day-type usage table in step with the current appliance/misc-load list.

    A new appliance added on Load Setup has no rows here yet (this table is keyed by
    (day_type, hour_of_day, category, item), one row per hour of every day type — ~450 rows per
    item). Without this, the item silently drops out of the hourly demand calculation entirely
    (compute_hourly_demand's first merge is against this table, so an item missing here never
    appears in the merged result at all) and never shows up in the Day-Type Usage Profiles grid.
    This adds an "off" (qty_active=0) row for every day type x hour for any item that's missing,
    so it appears in the grid ready to edit, and drops rows for items that were removed."""
    lookup = build_power_lookup(appliances_df, misc_loads_df)[["category", "item"]].drop_duplicates()
    wanted = pd.MultiIndex.from_frame(lookup)
    day_types = daytype_profiles_df["day_type"].unique()

    existing = pd.MultiIndex.from_frame(daytype_profiles_df[["category", "item"]])
    synced = daytype_profiles_df[existing.isin(wanted)].copy()

    missing = lookup[~wanted.isin(existing)]
    if len(missing) and len(day_types):
        new_rows = pd.DataFrame([
            {"day_type": dt, "hour_of_day": h, "category": row.category, "item": row.item, "qty_active": 0.0}
            for row in missing.itertuples() for dt in day_types for h in range(24)
        ])
        synced = pd.concat([synced, new_rows], ignore_index=True)
    return synced


def validate_season_periods(season_periods_df: pd.DataFrame, year: int = 2026) -> list:
    """Check that the season periods cover every day of the year exactly once (no gaps, no overlaps)."""
    errors = []
    dates = pd.date_range(f"{year}-01-01", periods=365, freq="D")
    mmdd = dates.strftime("%m-%d")
    covered_count = pd.Series(0, index=dates)

    for _, period in season_periods_df.iterrows():
        in_period = (mmdd >= period["start_mmdd"]) & (mmdd <= period["end_mmdd"])
        covered_count[in_period] += 1

    gaps = covered_count[covered_count == 0]
    overlaps = covered_count[covered_count > 1]
    if len(gaps) > 0:
        errors.append(f"{len(gaps)} day(s) not covered by any season period (e.g. {gaps.index[0].strftime('%b %d')})")
    if len(overlaps) > 0:
        errors.append(f"{len(overlaps)} day(s) covered by more than one season period (e.g. {overlaps.index[0].strftime('%b %d')})")
    return errors


def build_calendar_from_rules(year: int,
                               season_periods_df: pd.DataFrame,
                               public_holidays_df: pd.DataFrame,
                               festival_holidays_df: pd.DataFrame) -> pd.DataFrame:
    """Build the 365-day calendar (day type per day) from editable season/holiday/festival rules."""
    period_errors = validate_season_periods(season_periods_df, year)
    if period_errors:
        raise ValueError("Invalid season periods: " + "; ".join(period_errors))

    holiday_set = set(public_holidays_df["date_mmdd"])
    festival_set = set(festival_holidays_df["date_mmdd"])

    records = []
    for date in pd.date_range(f"{year}-01-01", periods=365, freq="D"):
        mmdd = date.strftime("%m-%d")
        is_weekend = date.weekday() >= 5

        if mmdd in holiday_set:
            day_type = "Public_Holiday"
        elif mmdd in festival_set:
            day_type = "Festival_Holiday"
        else:
            period = season_periods_df[(season_periods_df["start_mmdd"] <= mmdd) & (season_periods_df["end_mmdd"] >= mmdd)].iloc[0]
            day_type = period["weekend_daytype"] if is_weekend else period["weekday_daytype"]

        records.append({"day": date.dayofyear, "date": date.date(), "weekday": date.strftime("%A"), "day_type": day_type})

    return pd.DataFrame(records)


def build_hour_skeleton(n_days: int = 365) -> pd.DataFrame:
    """Build the 8,760-row hour-of-year skeleton: hour_of_year (1-8760), day (1-365), hour_of_day (0-23)."""
    hour_of_year = np.arange(1, n_days * 24 + 1)
    day = (hour_of_year - 1) // 24 + 1
    hour_of_day = (hour_of_year - 1) % 24
    return pd.DataFrame({"hour_of_year": hour_of_year, "day": day, "hour_of_day": hour_of_day})


def compute_hourly_demand(hour_skeleton_df: pd.DataFrame,
                           daytype_profiles_df: pd.DataFrame,
                           power_lookup_df: pd.DataFrame,
                           household_categories_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Wh demand for every hour of the year, broken down by category (A/B/C/Misc) and totaled.
    Returns hour_skeleton_df with four new columns: A_wh, B_wh, C_wh, Misc_wh, total_wh.
    """
    expanded = hour_skeleton_df.merge(daytype_profiles_df, on=["day_type", "hour_of_day"], how="left")
    expanded = expanded.merge(power_lookup_df, on=["category", "item"], how="left")
    expanded = expanded.merge(household_categories_df[["category", "household_count"]], on="category", how="left")
    expanded["household_count"] = expanded["household_count"].fillna(1)

    expanded["wh"] = expanded["qty_active"] * expanded["power_w"] * expanded["household_count"]

    by_category = (
        expanded.groupby(["hour_of_year", "category"])["wh"]
        .sum()
        .unstack("category")
        .fillna(0)
    )
    by_category.columns = [f"{c}_wh" for c in by_category.columns]
    by_category["total_wh"] = by_category.sum(axis=1)

    return hour_skeleton_df.merge(by_category, on="hour_of_year")


def compute_full_profile(year: int, season_periods_df: pd.DataFrame, public_holidays_df: pd.DataFrame,
                          festival_holidays_df: pd.DataFrame, daytype_profiles_df: pd.DataFrame,
                          appliances_df: pd.DataFrame, misc_loads_df: pd.DataFrame,
                          household_categories_df: pd.DataFrame) -> dict:
    """End-to-end: rules -> calendar -> hour skeleton -> hourly demand. Returns {"calendar", "hourly_profile"}."""
    calendar = build_calendar_from_rules(year, season_periods_df, public_holidays_df, festival_holidays_df)
    hour_skeleton = build_hour_skeleton()
    hour_skeleton = hour_skeleton.merge(calendar[["day", "date", "day_type"]], on="day", how="left")
    power_lookup = build_power_lookup(appliances_df, misc_loads_df)
    hourly_profile = compute_hourly_demand(hour_skeleton, daytype_profiles_df, power_lookup, household_categories_df)
    return {"calendar": calendar, "hourly_profile": hourly_profile}


def save_results(calendar: pd.DataFrame, hourly_profile: pd.DataFrame) -> None:
    calendar.to_csv(DATA_DIR / "annual_calendar_2026.csv", index=False)
    hourly_profile.to_csv(DATA_DIR / "hourly_load_profile_2026.csv", index=False)


# --- Excel round-trip: day-type profiles ---

def export_daytype_template(daytype_profiles_df: pd.DataFrame, output_path) -> None:
    """Write the day-type Qty-Active table to a formatted .xlsx, pivoted wide (one column per item) for easy editing."""
    wide = daytype_profiles_df.pivot_table(
        index=["day_type", "hour_of_day"], columns=["category", "item"], values="qty_active"
    )
    wide.columns = [f"{cat}|{item}" for cat, item in wide.columns]
    wide = wide.reset_index()

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "Each row is one hour of one day type. Edit any 'Qty Active' value (a category|item column).",
            "Qty Active is a COUNT of units running that hour (e.g. how many of the household's lights are on), not a fraction.",
            "Do not add/remove/rename day_type or hour_of_day rows, or rename columns — the app matches them by name on re-upload.",
            "Save the file, then re-upload it in the app to use these values instead of the defaults.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        wide.to_excel(writer, sheet_name="Day Type Profiles", index=False)

        for sheet_name, df in [("Instructions", instructions), ("Day Type Profiles", wide)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                width = max(10, min(28, len(str(col_name)) + 2))
                ws.set_column(col_idx, col_idx, width)


def import_daytype_template(input_path) -> dict:
    """Read a workbook in the export_daytype_template() shape back into a tidy (long-format) DataFrame, with validation."""
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)

    if "Day Type Profiles" not in sheets:
        return {"daytype_profiles": None, "errors": ["Missing required sheet: 'Day Type Profiles'"]}

    wide = sheets["Day Type Profiles"]
    required_index_cols = ["day_type", "hour_of_day"]
    missing = [c for c in required_index_cols if c not in wide.columns]
    if missing:
        errors.append(f"'Day Type Profiles' sheet is missing column(s): {missing}")

    if not errors:
        item_cols = [c for c in wide.columns if c not in required_index_cols]
        long = wide.melt(id_vars=required_index_cols, value_vars=item_cols,
                          var_name="category_item", value_name="qty_active")
        long[["category", "item"]] = long["category_item"].str.split("|", n=1, expand=True)
        long = long.drop(columns="category_item")

        if len(wide) != 19 * 24:
            errors.append(f"Expected {19*24} rows (19 day types x 24 hours), found {len(wide)}")
        if (long["qty_active"] < 0).any():
            errors.append("Some Qty Active value(s) are negative, which isn't physically valid")

    if errors:
        return {"daytype_profiles": None, "errors": errors}
    return {"daytype_profiles": long[["day_type", "hour_of_day", "category", "item", "qty_active"]], "errors": []}


# --- Excel round-trip: fully custom hourly profile (bypasses day-type computation entirely) ---

def export_hourly_profile_template(output_path, year: int = 2026) -> None:
    """Write a blank Date/Hour/Load template — 8,760 rows, ready for the user to fill in their own hourly demand data."""
    dates = pd.date_range(f"{year}-01-01", periods=365, freq="D")
    template_rows = []
    for date in dates:
        for hour in range(24):
            template_rows.append({"Date": date.strftime("%Y-%m-%d"), "Hour": hour, "Load_kWh": None})
    template = pd.DataFrame(template_rows)

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "Fill in Load_kWh for every hour with your own hourly demand data (kWh consumed in that hour).",
            "Hour runs 0-23, where 0 means the hour from midnight to 1am, 23 means 11pm to midnight.",
            "Do not add, remove, or reorder rows, and do not rename columns.",
            "Save the file, then upload it in the app to use this data instead of the computed profile.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        template.to_excel(writer, sheet_name="Hourly Profile", index=False)

        for sheet_name, df in [("Instructions", instructions), ("Hourly Profile", template)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                width = max(12, min(40, len(str(col_name)) + 4))
                ws.set_column(col_idx, col_idx, width)


def import_hourly_profile(input_path, expected_year: int = 2026) -> dict:
    """Read a user-filled Date/Hour/Load_kWh workbook, validate it, and return an 8,760-row profile ready to use."""
    errors = []
    df = pd.read_excel(input_path, sheet_name="Hourly Profile")

    required_cols = ["Date", "Hour", "Load_kWh"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return {"hourly_profile": None, "errors": [f"Missing column(s): {missing}"]}

    if len(df) != 8760:
        errors.append(f"Expected 8,760 rows (365 days x 24 hours), found {len(df)}")
    if df["Load_kWh"].isna().any():
        n_missing = int(df["Load_kWh"].isna().sum())
        errors.append(f"{n_missing} row(s) have a blank Load_kWh value — every hour must be filled in")
    if (df["Load_kWh"].dropna() < 0).any():
        errors.append("Some Load_kWh value(s) are negative, which isn't physically valid")
    if not df["Hour"].between(0, 23).all():
        errors.append("Hour must be between 0 and 23 for every row")

    date_hour_pairs = df["Date"].astype(str) + "_" + df["Hour"].astype(str)
    if date_hour_pairs.duplicated().any():
        errors.append("Some Date+Hour combination(s) appear more than once")

    if errors:
        return {"hourly_profile": None, "errors": errors}

    df["total_wh"] = df["Load_kWh"] * 1000
    return {"hourly_profile": df, "errors": []}


def finalize_uploaded_hourly_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Convert an import_hourly_profile() result into this project's standard hourly-profile shape
    (hour_of_year/day/date/total_wh), so it can be saved and consumed exactly like a computed profile.
    There is no per-category (A/B/C/Misc) breakdown here — a direct hourly upload bypasses day-types
    entirely, so category-level features (e.g. Results' per-category billing estimate) aren't available
    against an uploaded profile."""
    dates = pd.to_datetime(df["Date"])
    day = dates.dt.dayofyear
    hour_of_year = (day - 1) * 24 + df["Hour"] + 1
    out = pd.DataFrame({
        "hour_of_year": hour_of_year,
        "day": day,
        "date": dates.dt.date.astype(str),
        "total_wh": df["total_wh"],
    })
    return out.sort_values("hour_of_year").reset_index(drop=True)


# --- Per-item annual totals (lighter-weight than the full hourly pipeline — used for billing estimates) ---

def compute_item_annual_wh(calendar_df: pd.DataFrame, daytype_profiles_df: pd.DataFrame,
                            appliances_df: pd.DataFrame, misc_loads_df: pd.DataFrame,
                            household_categories_df: pd.DataFrame) -> pd.DataFrame:
    """Annual Wh consumption per individual item (each household appliance and each Misc/community
    load), summed across all households in its category. Uses each day-type's day-count from the
    saved calendar rather than expanding to all 8,760 hours — only annual totals are needed here."""
    power_lookup = build_power_lookup(appliances_df, misc_loads_df)
    day_counts = calendar_df["day_type"].value_counts().rename("n_days")

    merged = daytype_profiles_df.merge(day_counts, left_on="day_type", right_index=True, how="inner")
    merged = merged.merge(power_lookup, on=["category", "item"], how="left")
    merged = merged.merge(household_categories_df[["category", "household_count"]], on="category", how="left")
    merged["household_count"] = merged["household_count"].fillna(1)

    merged["annual_wh"] = merged["qty_active"] * merged["power_w"] * merged["household_count"] * merged["n_days"]
    return merged.groupby(["category", "item"], as_index=False)["annual_wh"].sum()


# --- Excel round-trip: calendar rules (season periods, public holidays, festival holidays) ---

def export_calendar_rules_template(season_periods_df: pd.DataFrame, public_holidays_df: pd.DataFrame,
                                     festival_holidays_df: pd.DataFrame, output_path) -> None:
    """Write the three editable calendar tables (season periods, public holidays, festival holidays) to a formatted .xlsx."""
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "Season Periods: each row is a named period of the year, with a start and end date (MM-DD, no year — the same table applies every year).",
            "Periods must cover all 365 days exactly once, with no gaps and no overlaps. Edit start_mmdd/end_mmdd to change season durations.",
            "weekday_daytype / weekend_daytype select which usage pattern (from the Day Type Profiles table) applies on weekdays / weekends within that period.",
            "Public Holidays / Festival Holidays: each row is ONE specific date (MM-DD). Add or remove rows to add/remove individual holiday or festival dates.",
            "A date listed as a holiday or festival always overrides the season/weekday-weekend pattern on that exact date.",
            "Save the file, then re-upload it in the app to use these values instead of the defaults.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        season_periods_df.to_excel(writer, sheet_name="Season Periods", index=False)
        public_holidays_df.to_excel(writer, sheet_name="Public Holidays", index=False)
        festival_holidays_df.to_excel(writer, sheet_name="Festival Holidays", index=False)

        sheet_frames = [("Instructions", instructions), ("Season Periods", season_periods_df),
                         ("Public Holidays", public_holidays_df), ("Festival Holidays", festival_holidays_df)]
        for sheet_name, df in sheet_frames:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                width = max(10, min(30, len(str(col_name)) + 2))
                ws.set_column(col_idx, col_idx, width)


def _valid_mmdd_series(series: pd.Series) -> pd.Series:
    """Boolean mask: which values in a Series look like a valid MM-DD date string."""
    format_ok = series.astype(str).str.match(_MMDD_RE)
    parsed = pd.to_datetime("2026-" + series.astype(str), format="%Y-%m-%d", errors="coerce")
    return format_ok & parsed.notna()


def import_calendar_rules_template(input_path) -> dict:
    """Read a workbook in the export_calendar_rules_template() shape back into the three tables, with validation."""
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)

    required_sheets = ["Season Periods", "Public Holidays", "Festival Holidays"]
    missing_sheets = [s for s in required_sheets if s not in sheets]
    if missing_sheets:
        return {"season_periods": None, "public_holidays": None, "festival_holidays": None,
                "errors": [f"Missing required sheet(s): {missing_sheets}"]}

    season_periods = sheets["Season Periods"]
    public_holidays = sheets["Public Holidays"]
    festival_holidays = sheets["Festival Holidays"]

    required_cols = {
        "Season Periods": ["period_name", "start_mmdd", "end_mmdd", "weekday_daytype", "weekend_daytype"],
        "Public Holidays": ["date_mmdd", "label"],
        "Festival Holidays": ["date_mmdd", "label"],
    }
    for sheet_name, df in [("Season Periods", season_periods), ("Public Holidays", public_holidays), ("Festival Holidays", festival_holidays)]:
        missing = [c for c in required_cols[sheet_name] if c not in df.columns]
        if missing:
            errors.append(f"'{sheet_name}' sheet is missing column(s): {missing}")

    if not errors:
        if not _valid_mmdd_series(season_periods["start_mmdd"]).all() or not _valid_mmdd_series(season_periods["end_mmdd"]).all():
            errors.append("Season Periods: start_mmdd/end_mmdd must all be valid MM-DD dates")
        for sheet_name, df in [("Public Holidays", public_holidays), ("Festival Holidays", festival_holidays)]:
            if not _valid_mmdd_series(df["date_mmdd"]).all():
                errors.append(f"{sheet_name}: date_mmdd must all be valid MM-DD dates")
            if df["date_mmdd"].duplicated().any():
                errors.append(f"{sheet_name}: contains duplicate date(s)")

        if not errors:
            period_errors = validate_season_periods(season_periods)
            errors.extend(period_errors)

        overlap = set(public_holidays["date_mmdd"]) & set(festival_holidays["date_mmdd"])
        if overlap:
            errors.append(f"Date(s) listed as both a Public Holiday and a Festival: {sorted(overlap)}")

    if errors:
        return {"season_periods": None, "public_holidays": None, "festival_holidays": None, "errors": errors}
    return {"season_periods": season_periods, "public_holidays": public_holidays, "festival_holidays": festival_holidays, "errors": []}
