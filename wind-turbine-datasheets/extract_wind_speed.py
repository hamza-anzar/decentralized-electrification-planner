"""One-off: extracts Annex-V's raw hourly wind speed column (col H) from the source workbook into
data/default_wind_speed_2026.csv, mirroring exactly how default_irradiance_2026.csv was built from
Annex-IV's column G (see docs/Workbook-Methodology-Reference.md section 8)."""
import openpyxl
import pandas as pd

wb = openpyxl.load_workbook("../Base-Calculations-00.xlsx", data_only=True)
v = wb["Annex-V"]

rows = []
for i in range(8760):
    r = 6 + i  # data starts row 6, per the methodology doc and the header-row-5 check
    wind_speed = v.cell(r, 8).value  # column H
    if wind_speed is None:
        raise ValueError(f"Row {r} (hour_of_year {i+1}) has no wind speed value -- extraction range is wrong")
    rows.append({"hour_of_year": i + 1, "wind_speed_ms": float(wind_speed)})

df = pd.DataFrame(rows)
df.to_csv("../data/default_wind_speed_2026.csv", index=False)
print("Extracted", len(df), "rows")
print(df.describe())
print(df.head(3))
print(df.tail(3))
