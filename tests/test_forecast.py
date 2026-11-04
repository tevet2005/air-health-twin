from datetime import date, datetime, timezone

import pandas as pd
import pytest

from airhealth import forecast
from airhealth.region import BoundingBox
from airhealth.sources import cams, openmeteo


def _hours(n=72, start="2024-03-01"):
    return [t.strftime("%Y-%m-%dT%H:%M") for t in pd.date_range(start, periods=n, freq="h")]


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeSession:
    """Returns PM2.5 of 10/20/30 µg/m³ on days 1/2/3 and constant weather."""

    def __init__(self):
        self.params = []

    def get(self, url, params, timeout):
        self.params.append(params)
        t = _hours()
        if url == openmeteo.AIR_QUALITY_URL:
            pm = [10.0] * 24 + [20.0] * 24 + [30.0] * 24
            hourly = {"time": t, "pm2_5": pm, "pm10": pm}
        else:
            hourly = {"time": t, "temperature_2m": [5.0] * 71 + [15.0],
                      "relative_humidity_2m": [60] * 72, "wind_speed_10m": [2.0] * 72,
                      "precipitation": [0.5] * 72}
        return _Resp({"hourly": hourly, "utc_offset_seconds": 3600, "timezone": "X/Y"})


def test_fetch_requests_local_time_and_ms_wind():
    s = FakeSession()
    df = openmeteo.fetch_weather(1.0, 2.0, session=s)
    assert s.params[0]["timezone"] == "auto" and s.params[0]["wind_speed_unit"] == "ms"
    assert df.attrs["utc_offset_seconds"] == 3600 and len(df) == 72


def test_daily_outlook_flags_guideline_and_trend():
    hourly = forecast.fetch_hourly(0, 0, session=FakeSession())
    o = forecast.daily_outlook(hourly, date(2024, 3, 2))
    assert o.pm25_mean == 20.0 and o.exceeds_guideline
    assert o.pm25_change_vs_previous_day == 10.0
    assert o.precipitation_total == pytest.approx(12.0)
    first = forecast.daily_outlook(hourly, date(2024, 3, 1))
    assert not first.exceeds_guideline and pd.isna(first.pm25_change_vs_previous_day)
    assert "ABOVE" in o.summary()


def test_daily_outlook_outside_window():
    hourly = forecast.fetch_hourly(0, 0, session=FakeSession())
    with pytest.raises(ValueError):
        forecast.daily_outlook(hourly, date(2024, 3, 9))


def test_local_today_uses_location_offset():
    now = datetime(2024, 3, 1, 20, 0, tzinfo=timezone.utc)
    assert forecast.local_today(9 * 3600, now) == date(2024, 3, 2)
    assert forecast.local_today(-5 * 3600, now) == date(2024, 3, 1)


def test_cams_forecast_request():
    req = cams.build_forecast_request("2024-03-01", BoundingBox(1, 0, 0, 1), leadtime_hours=[0, 24])
    assert req["date"] == "2024-03-01/2024-03-01"
    assert req["leadtime_hour"] == ["0", "24"] and req["type"] == ["forecast"]
