"""One-off: converts the approved Wind_Turbine_Library.xlsx into the app's data/ CSVs. Drops the
two UNAVAILABLE placeholder rows (Adwen AD 5-135, ACSA A17/90) -- they carry no usable curve data
and would just be a dead/non-functional entry in the app's turbine picker."""
import pandas as pd

DATA_DIR = "../data"

lib = pd.read_excel("Wind_Turbine_Library.xlsx", sheet_name="Turbine Library")
curves = pd.read_excel("Wind_Turbine_Library.xlsx", sheet_name="Power Curves")

usable = lib[lib["company"] != "UNAVAILABLE"].reset_index(drop=True)
usable_models = set(usable["model"])
curves = curves[curves["model"].isin(usable_models)].reset_index(drop=True)

usable.to_csv(f"{DATA_DIR}/default_wind_turbines.csv", index=False)
curves.to_csv(f"{DATA_DIR}/default_wind_turbine_power_curves.csv", index=False)

print("default_wind_turbines.csv:", len(usable), "models")
print(usable[["company", "model", "rated_power_kw"]].to_string(index=False))
print("default_wind_turbine_power_curves.csv:", len(curves), "rows")
