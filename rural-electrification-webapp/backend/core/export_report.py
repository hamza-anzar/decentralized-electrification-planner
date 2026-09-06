"""Generic multi-sheet Excel export — assembles several already-computed DataFrames into one
formatted workbook. Used by /api/results/export; follows the same xlsxwriter header-formatting
pattern as every export_*_template() function elsewhere in backend/core."""
import pandas as pd


def series_to_frame(series: pd.Series, metric_col: str = "Metric", value_col: str = "Value") -> pd.DataFrame:
    """Turn a name-indexed result/parameter Series (as loaded from a *_results.csv/*_parameters.csv
    file) into a plain two-column DataFrame, ready to write as its own sheet."""
    return series.rename_axis(metric_col).reset_index(name=value_col)


def build_workbook(sheets: dict, output_path) -> None:
    """Write `sheets` ({sheet_name: DataFrame}, in the order given) to one formatted .xlsx —
    each sheet gets the standard bold/blue header row and auto-sized columns."""
    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1})

        seen_names = {}
        safe_names = {}
        for sheet_name in sheets:
            safe = sheet_name[:31]
            n = seen_names.get(safe, 0)
            seen_names[safe] = n + 1
            safe_names[sheet_name] = safe if n == 0 else f"{safe[:28]}_{n}"

        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=safe_names[sheet_name], index=False)

        for sheet_name, df in sheets.items():
            ws = writer.sheets[safe_names[sheet_name]]
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                width = max(12, min(45, int(df[col_name].astype(str).str.len().max() or 10) + 2))
                ws.set_column(col_idx, col_idx, width)
