"""Date handling utilities for consistent date formatting across the application."""
from __future__ import annotations

from datetime import datetime, date
from typing import Union, Optional
import pandas as pd


def safe_format_date(
    date_value: Union[datetime, date, pd.Timestamp, str, None],
    format_str: str = '%m/%d/%Y'
) -> str:
    """
    Safely format a date value to string, handling various input types.

    This function eliminates the need for hasattr checks throughout the codebase
    by handling all common date types robustly.

    Args:
        date_value: Date value in various formats (datetime, date, pandas Timestamp, string, or None)
        format_str: strftime format string (default: MM/DD/YYYY)

    Returns:
        Formatted date string, or empty string if invalid

    Examples:
        >>> safe_format_date(datetime(2025, 1, 15))
        '01/15/2025'
        >>> safe_format_date('2025-01-15')
        '01/15/2025'
        >>> safe_format_date(None)
        ''
        >>> safe_format_date(pd.Timestamp('2025-01-15'))
        '01/15/2025'
    """
    if date_value is None:
        return ''

    # Handle pandas Timestamp
    if isinstance(date_value, pd.Timestamp):
        return date_value.strftime(format_str)

    # Handle datetime/date objects
    if isinstance(date_value, (datetime, date)):
        return date_value.strftime(format_str)

    # Try to parse string
    if isinstance(date_value, str):
        try:
            parsed = pd.to_datetime(date_value)
            return parsed.strftime(format_str)
        except (ValueError, TypeError):
            # Return as-is if can't parse
            return str(date_value)

    # Fallback to string representation
    return str(date_value)


def normalize_date_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Normalize a date column in a DataFrame to datetime objects.

    Args:
        df: DataFrame containing the column
        column: Name of the date column

    Returns:
        DataFrame with normalized date column

    Raises:
        ValueError: If the column doesn't exist
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    df = df.copy()
    df[column] = pd.to_datetime(df[column], errors='coerce')
    return df
