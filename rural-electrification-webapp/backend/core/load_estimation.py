"""Step 1 — Connected Load Estimation.

Ported directly from notebooks/01_Connected_Load_Estimation.ipynb (validated there against the source
workbook: 1.81128 MW). This module only holds the reusable logic — the Streamlit page in
app/pages/1_Connected_Load.py wires it up to widgets.
"""
import pandas as pd
import numpy as np

from .paths import DATA_DIR


def load_defaults() -> dict:
    """Load the three default input tables saved by the notebook (data/default_*.csv)."""
    return {
        "household_categories": pd.read_csv(DATA_DIR / "default_household_categories.csv"),
        "appliances": pd.read_csv(DATA_DIR / "default_appliances.csv"),
        "misc_loads": pd.read_csv(DATA_DIR / "default_misc_loads.csv"),
    }


def apply_total_houses_split(household_categories_df: pd.DataFrame, total_houses: float) -> pd.DataFrame:
    """
    Given a total number of houses and each category's pct_split, compute household_count per category live,
    using largest-remainder allocation so the counts always sum exactly to total_houses (matching the source
    workbook's exact 150/740/590 = 1480 split from 10/50/40%, instead of drifting from independent rounding).
    """
    df = household_categories_df.copy()
    raw = df["pct_split"].astype(float) / 100.0 * float(total_houses)
    floors = np.floor(raw).astype(int)
    remainder = int(round(total_houses)) - int(floors.sum())
    # Give the leftover houses (from rounding down) to the categories with the largest fractional remainder.
    fractional = (raw - floors).sort_values(ascending=False)
    for idx in fractional.index[:max(remainder, 0)]:
        floors[idx] += 1
    df["household_count"] = floors
    return df


def compute_connected_load(appliances_df: pd.DataFrame,
                            household_categories_df: pd.DataFrame,
                            misc_loads_df: pd.DataFrame) -> dict:
    """
    Compute connected load at three levels of detail from the three input tables.

    Returns a dict with:
      - "lines"        : every appliance/misc line with its own Connected Load (W)
      - "by_category"  : subtotal per category (A, B, C, Misc)
      - "total_w"      : grand total connected load, in W
    """
    lines_hh = appliances_df.merge(
        household_categories_df[["category", "household_count"]],
        on="category", how="left"
    )
    lines_hh["connected_load_w"] = (
        lines_hh["power_w"] * lines_hh["qty_per_house"] * lines_hh["household_count"]
    )
    lines_hh = lines_hh[["category", "appliance", "power_w", "qty_per_house",
                          "household_count", "connected_load_w", "comment"]]

    lines_misc = misc_loads_df.copy()
    lines_misc["connected_load_w"] = lines_misc["power_w"] * lines_misc["qty"]
    lines_misc.insert(0, "category", "Misc")
    lines_misc = lines_misc.rename(columns={"qty": "qty_per_house"})
    lines_misc["household_count"] = np.nan
    lines_misc = lines_misc[["category", "appliance", "power_w", "qty_per_house",
                              "household_count", "connected_load_w", "comment"]]

    lines = pd.concat([lines_hh, lines_misc], ignore_index=True)

    by_category = (
        lines.groupby("category", sort=False)["connected_load_w"]
        .sum()
        .reset_index()
        .rename(columns={"connected_load_w": "connected_load_w_subtotal"})
    )

    total_w = lines["connected_load_w"].sum()

    return {"lines": lines, "by_category": by_category, "total_w": total_w}


def save_results(total_w: float, by_category: pd.DataFrame) -> None:
    """Persist Step 1's results so later steps (Step 6's summary table) can consume them."""
    connected_load_results = pd.DataFrame([
        {"result": "total_connected_load_w", "value": total_w, "unit": "W"},
        {"result": "total_connected_load_mw", "value": total_w / 1_000_000, "unit": "MW"},
    ])
    connected_load_results.to_csv(DATA_DIR / "connected_load_results.csv", index=False)
    by_category.to_csv(DATA_DIR / "connected_load_by_category.csv", index=False)


def export_appliance_template(household_categories_df: pd.DataFrame,
                               appliances_df: pd.DataFrame,
                               misc_loads_df: pd.DataFrame,
                               output_path) -> None:
    """Write the three input tables to one formatted .xlsx workbook for the user to download and edit."""
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({
            "bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1
        })

        instructions = pd.DataFrame({
            "Instructions": [
                "Edit any value in the 'Household Categories', 'Appliances', or 'Misc Loads' sheets.",
                "Do not rename columns or sheets — the app matches them by name on re-upload.",
                "'category' must be A, B, or C on the Appliances sheet.",
                "To add a new appliance, edit one of the existing 'Others' rows (set its power_w and qty_per_house).",
                "Save the file, then re-upload it in the app to use these values instead of the defaults.",
            ]
        })
        instructions.to_excel(writer, sheet_name="Instructions", index=False)

        household_categories_df.to_excel(writer, sheet_name="Household Categories", index=False)
        appliances_df.to_excel(writer, sheet_name="Appliances", index=False)
        misc_loads_df.to_excel(writer, sheet_name="Misc Loads", index=False)

        for sheet_name, df in [("Instructions", instructions),
                                ("Household Categories", household_categories_df),
                                ("Appliances", appliances_df),
                                ("Misc Loads", misc_loads_df)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                width = max(12, min(45, int(df[col_name].astype(str).str.len().max() or 10) + 2))
                ws.set_column(col_idx, col_idx, width)


def import_appliance_template(input_path) -> dict:
    """
    Read a workbook in the export_appliance_template() shape back into the three tables.
    Returns {"household_categories": df, "appliances": df, "misc_loads": df, "errors": [list of str]}.
    If "errors" is non-empty, the data should NOT be used — surface the errors to the user instead.
    """
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)

    required_sheets = {"Household Categories": ["category", "label", "pct_split", "household_count"],
                        "Appliances": ["category", "appliance", "power_w", "qty_per_house"],
                        "Misc Loads": ["appliance", "power_w", "qty"]}

    for sheet_name, required_cols in required_sheets.items():
        if sheet_name not in sheets:
            errors.append(f"Missing required sheet: '{sheet_name}'")
            continue
        missing_cols = [c for c in required_cols if c not in sheets[sheet_name].columns]
        if missing_cols:
            errors.append(f"Sheet '{sheet_name}' is missing column(s): {missing_cols}")

    if not errors:
        hh = sheets["Household Categories"]
        appl = sheets["Appliances"]
        misc = sheets["Misc Loads"]

        bad_categories = set(appl["category"].unique()) - {"A", "B", "C"}
        if bad_categories:
            errors.append(f"Appliances sheet has invalid category value(s): {sorted(bad_categories)} (must be A, B, or C)")

        for df, cols, name in [(hh, ["household_count", "pct_split"], "Household Categories"),
                                (appl, ["power_w", "qty_per_house"], "Appliances"),
                                (misc, ["power_w", "qty"], "Misc Loads")]:
            for col in cols:
                if (df[col] < 0).any():
                    errors.append(f"Sheet '{name}' column '{col}' has negative value(s), which isn't physically valid")

    if errors:
        return {"household_categories": None, "appliances": None, "misc_loads": None, "errors": errors}

    return {"household_categories": sheets["Household Categories"],
            "appliances": sheets["Appliances"],
            "misc_loads": sheets["Misc Loads"],
            "errors": []}
