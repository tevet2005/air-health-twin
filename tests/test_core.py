import numpy as np
import pandas as pd
import pytest

from airhealth import hia, qc
from airhealth.region import BoundingBox
from airhealth.sources import cams, http_timeseries


# --- region -----------------------------------------------------------------

def test_bbox_validation_and_area():
    b = BoundingBox(north=10, west=-5, south=0, east=5)
    assert b.as_cds_area() == [10, -5, 0, 5]
    with pytest.raises(ValueError):
        BoundingBox(north=0, west=0, south=10, east=5)


def test_bbox_around_clips_to_globe():
    b = BoundingBox.around(89.5, 179.5, 1.0)
    assert b.north == 90 and b.east == 180


# --- cams -------------------------------------------------------------------

def test_iter_months_crosses_year():
    assert list(cams.iter_months("2020-11", "2021-02")) == [(2020, 11), (2020, 12), (2021, 1), (2021, 2)]


def test_build_request_leap_february():
    req = cams.build_request(2024, 2, BoundingBox(1, 0, 0, 1))
    assert req["date"] == "2024-02-01/2024-02-29"
    assert req["area"] == [1, 0, 0, 1]


def test_download_monthly_uses_injected_client(tmp_path):
    calls = []

    class FakeClient:
        def retrieve(self, dataset, request, target):
            calls.append(request["date"])
            open(target, "wb").write(b"nc")

    paths = cams.download_monthly("2021-01", "2021-02", tmp_path, client=FakeClient(), pause_s=0)
    assert len(paths) == 2 and len(calls) == 2
    # second run skips existing files
    cams.download_monthly("2021-01", "2021-02", tmp_path, client=FakeClient(), pause_s=0)
    assert len(calls) == 2


# --- http_timeseries --------------------------------------------------------

class _Resp:
    def __init__(self, code, content=b""):
        self.status_code, self.content = code, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Session:
    def __init__(self, responses):
        self.responses = responses

    def get(self, url, timeout):
        return self.responses[url]


def test_download_series_handles_missing_and_writes_manifest(tmp_path):
    tpl = "https://x.test/%Y%m%d%H.tif"
    s = _Session({
        "https://x.test/2024010100.tif": _Resp(200, b"a"),
        "https://x.test/2024010101.tif": _Resp(404),
    })
    res = http_timeseries.download_series(tpl, "2024-01-01 00:00", "2024-01-01 01:00",
                                          tmp_path, pause_s=0, session=s)
    assert [r.status for r in res] == ["ok", "not_found"]
    assert (tmp_path / "2024010100.tif").read_bytes() == b"a"
    assert "not_found" in (tmp_path / "manifest.csv").read_text()


# --- qc ---------------------------------------------------------------------

def test_clean_masks_error_codes():
    s = qc.clean(pd.Series(["10", 9999, "x", 5]))
    assert s.isna().tolist() == [False, True, True, False]


def test_completeness_counts_against_expected_index():
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    s = pd.Series([1.0, np.nan], index=idx[:2])
    rep = qc.completeness(s.rename("pm"), idx)
    assert rep.loc["pm", "valid"] == 1 and rep.loc["pm", "missing_rate"] == 0.75


def test_daily_mean_hour_ending_and_threshold():
    # hour-ending stamps 01:00..24:00 (=next day 00:00) belong to one day
    idx = pd.date_range("2024-01-01 01:00", periods=24, freq="h")
    s = pd.Series(1.0, index=idx)
    d = qc.daily_mean(s, min_valid_hours=20)
    assert list(d.index) == [pd.Timestamp("2024-01-01")] and d.iloc[0] == 1.0
    s.iloc[:5] = np.nan  # only 19 valid hours
    assert qc.daily_mean(s, min_valid_hours=20).isna().all()


def test_to_timezone_from_utc():
    idx = pd.DatetimeIndex(["2024-01-01 00:00"])
    assert qc.to_timezone(idx, "Asia/Kolkata")[0] == pd.Timestamp("2024-01-01 05:30")


def test_regional_daily():
    df = pd.DataFrame({"a": [10.0, 40.0], "b": [20.0, np.nan]})
    out = qc.regional_daily(df, threshold=35)
    assert out["mean"].tolist() == [15.0, 40.0]
    assert out["sd"].iloc[1] == 0.0 and out["exceeds"].tolist() == [0, 1]


# --- hia --------------------------------------------------------------------

def test_hia_known_values():
    beta = hia.beta_from_rr(1.08, unit=10)
    assert hia.relative_risk(15.0, beta, counterfactual=5.0) == pytest.approx(1.08)
    assert hia.attributable_fraction(15.0, beta, 5.0) == pytest.approx(0.08 / 1.08)
    assert hia.attributable_fraction(3.0, beta, 5.0) == 0.0  # below counterfactual
    cases = hia.attributable_cases(15.0, population=1e6, baseline_rate=0.01, beta=beta, counterfactual=5.0)
    assert cases == pytest.approx(1e4 * 0.08 / 1.08)


def test_hia_vectorised():
    beta = hia.beta_from_rr(1.08)
    af = hia.attributable_fraction(np.array([0.0, 10.0, 20.0]), beta)
    assert af[0] == 0 and np.all(np.diff(af) > 0)
