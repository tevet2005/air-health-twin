"""Daily air-quality and weather outlook for any location.

Answers two questions for a given point:

1. Will PM2.5 be high tomorrow?
2. What will the temperature, humidity and wind be?

Command-line example::

    python -m airhealth.forecast --lat 48.85 --lon 2.35
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

import pandas as pd

from airhealth import qc
from airhealth.sources import openmeteo

#: WHO 2021 Air Quality Guideline for 24-hour mean PM2.5 (µg/m³).
WHO_PM25_24H = 15.0


@dataclass
class DailyOutlook:
    date: date
    pm25_mean: float
    pm25_max: float
    pm25_change_vs_previous_day: float
    exceeds_guideline: bool
    guideline: float
    temperature_min: float
    temperature_max: float
    humidity_mean: float
    wind_speed_mean: float
    precipitation_total: float

    def summary(self) -> str:
        level = "ABOVE" if self.exceeds_guideline else "below"
        trend = f"{self.pm25_change_vs_previous_day:+.1f}" if pd.notna(self.pm25_change_vs_previous_day) else "n/a"
        return (
            f"{self.date}: PM2.5 daily mean {self.pm25_mean:.1f} µg/m³ "
            f"(max {self.pm25_max:.1f}, {trend} vs previous day), {level} the "
            f"{self.guideline:g} µg/m³ 24-h guideline\n"
            f"  temperature {self.temperature_min:.1f}–{self.temperature_max:.1f} °C, "
            f"humidity {self.humidity_mean:.0f} %, wind {self.wind_speed_mean:.1f} m/s, "
            f"precipitation {self.precipitation_total:.1f} mm"
        )


def local_today(utc_offset_seconds: int, now: datetime | None = None) -> date:
    """Today's date at the forecast location."""
    now = now or datetime.now(timezone.utc)
    return (now + timedelta(seconds=utc_offset_seconds)).date()


def daily_outlook(
    hourly: pd.DataFrame,
    day: date,
    guideline: float = WHO_PM25_24H,
    min_valid_hours: int = 18,
) -> DailyOutlook:
    """Summarise a merged hourly forecast (air quality + weather) for one local day."""
    pm_daily = qc.daily_mean(hourly["pm2_5"], min_valid_hours=min_valid_hours, hour_ending=False)
    d = pd.Timestamp(day)
    if d not in pm_daily.index:
        raise ValueError(f"{day} is outside the forecast window "
                         f"({hourly.index.min():%Y-%m-%d} to {hourly.index.max():%Y-%m-%d})")
    prev = pm_daily.get(d - pd.Timedelta(days=1), float("nan"))
    h = hourly.loc[hourly.index.normalize() == d]
    mean = float(pm_daily.loc[d])
    return DailyOutlook(
        date=day,
        pm25_mean=mean,
        pm25_max=float(h["pm2_5"].max()),
        pm25_change_vs_previous_day=float(mean - prev),
        exceeds_guideline=bool(mean > guideline),
        guideline=guideline,
        temperature_min=float(h["temperature_2m"].min()),
        temperature_max=float(h["temperature_2m"].max()),
        humidity_mean=float(h["relative_humidity_2m"].mean()),
        wind_speed_mean=float(h["wind_speed_10m"].mean()),
        precipitation_total=float(h["precipitation"].sum()),
    )


def fetch_hourly(lat: float, lon: float, days: int = 3, session=None) -> pd.DataFrame:
    """Merged hourly air-quality and weather forecast in local time."""
    aq = openmeteo.fetch_air_quality(lat, lon, days=days, session=session)
    wx = openmeteo.fetch_weather(lat, lon, days=days, session=session)
    merged = aq.join(wx, how="inner")
    merged.attrs = {**wx.attrs, **aq.attrs}
    return merged


def tomorrow(lat: float, lon: float, guideline: float = WHO_PM25_24H, session=None) -> DailyOutlook:
    """Outlook for tomorrow (local date) at ``lat``, ``lon``."""
    hourly = fetch_hourly(lat, lon, days=3, session=session)
    day = local_today(hourly.attrs.get("utc_offset_seconds", 0)) + timedelta(days=1)
    return daily_outlook(hourly, day, guideline)


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Tomorrow's PM2.5 and weather outlook for a location.")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--guideline", type=float, default=WHO_PM25_24H,
                   help="24-h PM2.5 threshold in µg/m³ (default: WHO 2021 guideline)")
    p.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = p.parse_args(argv)

    o = tomorrow(args.lat, args.lon, args.guideline)
    if args.json:
        import json
        print(json.dumps(asdict(o), default=str, indent=2))
    else:
        print(o.summary())
        print("Data: Open-Meteo (CC BY 4.0), CAMS forecasts. Not medical advice.")


if __name__ == "__main__":
    main()
