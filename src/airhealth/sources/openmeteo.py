"""Point forecasts of air quality and weather from the Open-Meteo APIs.

* Air quality: https://open-meteo.com/en/docs/air-quality-api
  (hourly PM2.5/PM10 etc., based on CAMS global and regional forecasts)
* Weather: https://open-meteo.com/en/docs (hourly temperature, humidity, wind ...)

No API key is required. Open-Meteo is free for non-commercial use; data are
licensed CC BY 4.0 and must be attributed. Timestamps are returned in the
local time zone of the requested location.
"""
from __future__ import annotations

from typing import Sequence

import pandas as pd
import requests

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

AIR_QUALITY_VARIABLES = ("pm2_5", "pm10")
WEATHER_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
)


def _get_hourly(
    url: str,
    lat: float,
    lon: float,
    variables: Sequence[str],
    days: int,
    session: requests.Session | None,
    extra: dict | None = None,
) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(variables),
        "forecast_days": days,
        "timezone": "auto",
        **(extra or {}),
    }
    http = session or requests
    r = http.get(url, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()

    hourly = payload["hourly"]
    df = pd.DataFrame({v: hourly[v] for v in variables},
                      index=pd.to_datetime(hourly["time"]))
    df.index.name = "time_local"
    df = df.apply(pd.to_numeric, errors="coerce")
    df.attrs.update(
        timezone=payload.get("timezone"),
        utc_offset_seconds=payload.get("utc_offset_seconds", 0),
        units=payload.get("hourly_units", {}),
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
    )
    return df


def fetch_air_quality(
    lat: float,
    lon: float,
    days: int = 3,
    variables: Sequence[str] = AIR_QUALITY_VARIABLES,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Hourly air-quality forecast (µg/m³) for a point, in local time."""
    return _get_hourly(AIR_QUALITY_URL, lat, lon, variables, days, session)


def fetch_weather(
    lat: float,
    lon: float,
    days: int = 3,
    variables: Sequence[str] = WEATHER_VARIABLES,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Hourly weather forecast for a point, in local time. Wind speed is in m/s."""
    return _get_hourly(WEATHER_URL, lat, lon, variables, days, session,
                       extra={"wind_speed_unit": "ms"})
