"""JSON-safety helpers: converts pandas/numpy objects (DataFrames, Series, numpy scalars, NaN/NaT)
into plain Python types that FastAPI's default JSON encoder can serialize without choking on NaN
(invalid JSON) or numpy int64/float64 (not natively serializable)."""
import math
import numpy as np
import pandas as pd


def clean_records(df: pd.DataFrame) -> list:
    """DataFrame -> list of JSON-safe row dicts. NaN/NaT -> None, dates/Timestamps -> ISO strings."""
    if df is None:
        return None
    safe = df.astype(object).where(pd.notnull(df), None)
    records = safe.to_dict(orient="records")
    for row in records:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
            elif isinstance(v, (np.floating,)):
                row[k] = None if math.isnan(v) else float(v)
            elif isinstance(v, (np.integer,)):
                row[k] = int(v)
    return records


def native(obj):
    """Recursively convert a (possibly deeply nested) structure containing DataFrames, Series, numpy
    scalars, or NaN into plain JSON-safe Python types. Use this to wrap any endpoint's return value
    when it might contain results straight out of the core calculation modules."""
    if isinstance(obj, pd.DataFrame):
        return clean_records(obj)
    if isinstance(obj, pd.Series):
        return native(obj.to_dict())
    if isinstance(obj, dict):
        return {k: native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [native(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return native(obj.tolist())
    if isinstance(obj, (np.floating,)):
        return None if math.isnan(obj) else float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj
