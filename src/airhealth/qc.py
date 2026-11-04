"""Quality control and temporal aggregation for air-quality time series.

Conventions
-----------
* Hourly inputs are ``pd.Series`` / ``pd.DataFrame`` indexed by a
  ``DatetimeIndex``; wide frames have one column per station.
* ``hour_ending=True`` means a value stamped 01:00 is the mean over
  00:00-01:00 (common for station networks); it is shifted back one hour
  before daily grouping so that 24:00 belongs to the right day.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def clean(data: pd.DataFrame | pd.Series, error_codes: Iterable[float] = (9999, 9998, 9997)):
    """Coerce to numeric and replace sentinel 'no valid measurement' codes with NaN."""
    if isinstance(data, pd.DataFrame):
        numeric = data.apply(pd.to_numeric, errors="coerce")
    else:
        numeric = pd.to_numeric(data, errors="coerce")
    return numeric.mask(numeric.isin(list(error_codes)))


def to_timezone(index: pd.DatetimeIndex, tz: str, assume: str = "UTC") -> pd.DatetimeIndex:
    """Convert to ``tz`` and drop tz info (naive local time).

    Naive input is assumed to be in ``assume``.
    """
    if index.tz is None:
        index = index.tz_localize(assume)
    return index.tz_convert(tz).tz_localize(None)


def completeness(data: pd.Series | pd.DataFrame, expected: pd.DatetimeIndex) -> pd.DataFrame:
    """Missing-rate report against the timesteps that *should* exist.

    Comparing against the expected index (not the rows that happen to be
    present) keeps datasets with different resolutions comparable.
    """
    frame = data.to_frame() if isinstance(data, pd.Series) else data
    aligned = frame.reindex(expected)
    n = len(expected)
    valid = aligned.notna().sum()
    return pd.DataFrame({
        "expected": n,
        "valid": valid,
        "missing": n - valid,
        "missing_rate": (n - valid) / n if n else np.nan,
    })


def daily_mean(
    hourly: pd.Series | pd.DataFrame,
    min_valid_hours: int = 20,
    hour_ending: bool = True,
) -> pd.DataFrame | pd.Series:
    """Daily means; days with fewer than ``min_valid_hours`` valid hours become NaN."""
    shifted = hourly.copy()
    if hour_ending:
        shifted.index = shifted.index - pd.Timedelta(hours=1)
    grouped = shifted.groupby(shifted.index.normalize())
    means = grouped.mean()
    counts = grouped.count()
    return means.where(counts >= min_valid_hours)


def regional_daily(station_daily: pd.DataFrame, threshold: float | None = None) -> pd.DataFrame:
    """Summarise a wide (date x station) frame of daily means across stations."""
    out = pd.DataFrame({
        "mean": station_daily.mean(axis=1),
        "n_stations": station_daily.count(axis=1),
        "sd": station_daily.std(axis=1).fillna(0.0),
        "range": (station_daily.max(axis=1) - station_daily.min(axis=1)),
    })
    if threshold is not None:
        out["exceeds"] = (out["mean"] > threshold).astype(int)
    return out
