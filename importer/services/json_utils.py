import pandas as pd
import numpy as np
from datetime import datetime, date


def make_json_safe(obj):
    """
    Recursively convert pandas / numpy / datetime objects
    into JSON-serializable Python primitives.
    """

    # ---- pandas / numpy ----
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()

    if isinstance(obj, (np.integer,)):
        return int(obj)

    if isinstance(obj, (np.floating,)):
        return float(obj)

    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()

    # ---- containers ----
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]

    # ---- fallback ----
    return obj
