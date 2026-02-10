"""Shared helpers for property labeling/normalization."""
from __future__ import annotations

from typing import Optional

import pandas as pd
from pandas import DataFrame

UNASSIGNED_PROPERTY_LABEL = "Unassigned / Needs Review"


def normalize_property_column(
    df: DataFrame,
    column: str = "property_name",
    fallback_label: str = UNASSIGNED_PROPERTY_LABEL,
) -> DataFrame:
    """Normalize property labels so groupbys retain unassigned rows.

    Pandas drops NaN keys when grouping.  By eagerly filling blanks/None with a
    shared placeholder we make sure unassigned transactions show up everywhere
    (Excel exports, Schedule E summaries, dashboards, etc.).
    """

    if df.empty or column not in df.columns:
        return df

    series = df[column]
    series = series.where(series.notna(), "")
    series = series.astype(str).str.strip()

    lower = series.str.lower()
    mask = lower.isin({"", "nan", "none", "null", "na"})
    series = series.mask(mask, fallback_label)

    df[column] = series
    return df


__all__ = ["UNASSIGNED_PROPERTY_LABEL", "normalize_property_column"]
