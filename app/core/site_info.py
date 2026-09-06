"""Site / location info — non-calculation contextual fields (country, population, GDP/capita, etc.)

These fields don't feed the load/generation/cost pipeline directly — they exist for socio-economic
context, per-capita figures, and the headline summary on the Results & Summary page, per the user's
explicit request to keep them separate from calculation inputs.
"""
import pandas as pd

from .paths import DATA_DIR

SITE_INFO_PATH = DATA_DIR / "default_site_info.csv"


def load_defaults() -> pd.DataFrame:
    return pd.read_csv(SITE_INFO_PATH)


def get_field(site_info_df: pd.DataFrame, name: str):
    """Look up one field's value by name — same pattern as the cost/ROI get_param() helpers."""
    return site_info_df.loc[site_info_df["field"] == name, "value"].iloc[0]


def as_dict(site_info_df: pd.DataFrame) -> dict:
    """Convenience: {field: value} for easy access in pages/templates."""
    return dict(zip(site_info_df["field"], site_info_df["value"]))


def save(site_info_df: pd.DataFrame) -> None:
    site_info_df.to_csv(SITE_INFO_PATH, index=False)


# --- Excel round-trip ---

def export_site_info_template(site_info_df: pd.DataFrame, output_path) -> None:
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        instructions = pd.DataFrame({"Instructions": [
            "Edit the 'value' column only — do not add/remove/rename rows.",
            "These fields are for context and later socio-economic analysis (per-capita figures, etc.) — "
            "they are not used in the load, generation, or cost calculations.",
            "Save the file, then re-upload it in the app to use these values instead of the defaults.",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)
        site_info_df.to_excel(writer, sheet_name="Site Info", index=False)

        for sheet_name, df in [("Instructions", instructions), ("Site Info", site_info_df)]:
            ws = writer.sheets[sheet_name]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                ws.set_column(col_idx, col_idx, max(14, len(str(col_name)) + 2))


def import_site_info_template(input_path) -> dict:
    errors = []
    sheets = pd.read_excel(input_path, sheet_name=None)
    if "Site Info" not in sheets:
        return {"site_info": None, "errors": ["Missing required sheet: 'Site Info'"]}

    site_info = sheets["Site Info"]
    defaults = load_defaults()
    if set(site_info.get("field", [])) != set(defaults["field"]):
        errors.append("'Site Info' must contain exactly the same field rows as the default")

    if errors:
        return {"site_info": None, "errors": errors}
    return {"site_info": site_info, "errors": []}
