"""
Invoice file parsing and derived fields (days overdue, ready for processing).
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import BinaryIO

import pandas as pd

REQUIRED_COLUMNS = [
    "invoice_number",
    "client_name",
    "amount_due",
    "due_date",
    "contact_email",
    "follow_up_count",
]


def _normalize_column_name(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_")


def _normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_normalize_column_name(c) for c in df.columns]
    return df


def _parse_due_dates(series: pd.Series) -> pd.Series:
    """Parse due dates from mixed string/excel formats."""
    parsed = pd.to_datetime(series, errors="coerce", utc=False)
    if parsed.dt.tz is not None:
        parsed = parsed.dt.tz_localize(None)
    return parsed.dt.normalize()


def load_invoice_file(
    file_obj: BinaryIO | BytesIO,
    filename: str,
) -> pd.DataFrame:
    """
    Load invoices from CSV or Excel (.xlsx, .xls).

    Raises ValueError with a clear message if required columns are missing.
    """
    name = (filename or "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file_obj)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError("Unsupported file type. Upload a .csv or .xlsx file.")

    df = _normalize_dataframe_columns(df)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}. "
            f"Required: {', '.join(REQUIRED_COLUMNS)}"
        )

    # Trim string fields
    for col in ["invoice_number", "client_name", "contact_email"]:
        df[col] = df[col].astype(str).str.strip()

    df["amount_due"] = pd.to_numeric(df["amount_due"], errors="coerce")
    df["follow_up_count"] = pd.to_numeric(df["follow_up_count"], errors="coerce").fillna(0).astype(int)

    df["due_date"] = _parse_due_dates(df["due_date"])
    invalid_dates = df["due_date"].isna()
    if invalid_dates.any():
        bad_rows = df.loc[invalid_dates].index.tolist()
        raise ValueError(f"Invalid due_date values at row indices (0-based): {bad_rows[:20]}")

    if df["amount_due"].isna().any():
        raise ValueError("amount_due must be numeric for all rows.")

    if "payment_instructions" not in df.columns:
        df["payment_instructions"] = ""
    else:
        df["payment_instructions"] = (
            df["payment_instructions"].astype(str).fillna("").map(lambda s: str(s).strip())
        )

    return df


def add_days_overdue(df: pd.DataFrame, as_of: date | None = None) -> pd.DataFrame:
    """
    Append `days_overdue` (0 if not past due) and `is_overdue` flag.
    """
    df = df.copy()
    as_of = as_of or date.today()
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    as_of_ts = pd.Timestamp(as_of).normalize()
    raw_days = (as_of_ts - df["due_date"]).dt.days
    df["days_overdue"] = raw_days.fillna(0).astype(int).clip(lower=0)
    df["is_overdue"] = df["days_overdue"] > 0
    return df
