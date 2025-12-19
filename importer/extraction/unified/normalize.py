import pandas as pd
import numpy as np


def detect_field_type(series: pd.Series) -> str:
    """
    Smarter type detection that checks numeric-like strings,
    date-like strings, and boolean-like content.
    """

    # Convert DataFrame column → Series if needed
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]

    s = series.dropna().astype(str).str.strip()

    if s.empty:
        return "text"

    # Boolean
    if s.str.lower().isin(["true", "false", "yes", "no", "1", "0"]).all():
        return "boolean"

    # Integer
    if s.str.match(r"^-?\d+$").all():
        return "number"

    # Decimal
    if s.str.match(r"^-?\d+\.\d+$").all():
        return "decimal"

    # Date
    try:
        parsed = pd.to_datetime(
            s,
            errors="coerce",
            dayfirst=False,
            infer_datetime_format=False
        )
        return "datetime"
    except Exception:
        pass

    return "text"


def normalize_table(columns, rows):
    """
    A fully robust table normalizer that:
    - fixes empty/duplicate headers
    - handles messy PDF rows
    - removes empty columns
    - detects types
    - converts NaN → None
    """

    # ---------------------------------------------
    # 1. Create DataFrame with safe headers
    # ---------------------------------------------
    if not columns:
        columns = [f"Column_{i+1}" for i in range(len(rows[0]))]

    # Fix blank headers
    columns = [
        col if isinstance(col, str) and col.strip() != "" else f"Column_{i+1}"
        for i, col in enumerate(columns)
    ]

    # Fix duplicate headers
    seen = {}
    unique_cols = []
    for col in columns:
        if col not in seen:
            seen[col] = 0
            unique_cols.append(col)
        else:
            seen[col] += 1
            unique_cols.append(f"{col}_{seen[col]}")

    df = pd.DataFrame(rows, columns=unique_cols)

    # ---------------------------------------------
    # 2. Fix ragged rows (make all same length)
    # ---------------------------------------------
    max_cols = len(df.columns)
    df = df.apply(
        lambda row: row.tolist() + [None] * (max_cols - len(row)),
        axis=1,
        result_type="expand"
    )
    df.columns = unique_cols

    # ---------------------------------------------
    # 3. Drop columns that are fully empty
    # ---------------------------------------------
    def is_empty_column(series):
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]

        cleaned = (
            series.dropna()
                  .astype(str)
                  .str.strip()
                  .str.lower()
        )

        return cleaned.empty or cleaned.isin(["", "nan"]).all()

    non_empty_cols = [col for col in df.columns if not is_empty_column(df[col])]
    df = df[non_empty_cols]

    # ---------------------------------------------
    # 4. Detect field types
    # ---------------------------------------------
    field_types = {
        col: detect_field_type(df[col])
        for col in df.columns
    }

    # ---------------------------------------------
    # 5. Convert NaN to None
    # ---------------------------------------------
    df = df.replace({np.nan: None, "nan": None, "": None})

    # ---------------------------------------------
    # FINAL OUTPUT
    # ---------------------------------------------
    return {
        "columns": list(df.columns),
        "rows": df.to_dict(orient="records"),
        "field_types": field_types,
    }
