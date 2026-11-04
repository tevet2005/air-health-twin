"""Generic downloader for file-per-timestep products served over HTTP(S).

Many monitoring and forecasting services publish one file per hour or per day
at a predictable URL. Describe the URL with a ``strftime`` template and this
module handles the loop, retries, missing files and an integrity manifest::

    from airhealth.sources.http_timeseries import download_series

    download_series(
        "https://example.org/pm25/%Y/%m/PM25_%Y%m%d%H.tif",
        start="2024-01-01 00:00", end="2024-01-31 23:00", freq="h",
        out_dir="data/pm25_maps",
    )
"""
from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

USER_AGENT = "air-health-twin/0.1 (+https://github.com/tevet2005/air-health-twin)"


@dataclass
class FetchResult:
    timestamp: datetime
    path: Path
    status: str  # "ok", "skipped", "not_found", "error"
    sha256: str = ""


def fetch_one(
    url: str,
    path: Path,
    session: requests.Session,
    max_retries: int = 3,
    timeout_s: float = 60,
) -> tuple[str, str]:
    """Download ``url`` to ``path``. Returns (status, sha256)."""
    if path.exists() and path.stat().st_size > 0:
        return "skipped", ""

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, timeout=timeout_s)
            if r.status_code == 404:
                return "not_found", ""
            r.raise_for_status()
            if not r.content:
                raise RuntimeError("empty response")
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(r.content)
            tmp.replace(path)  # atomic: never leave a half-written file behind
            return "ok", sha256(r.content).hexdigest()
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(2**attempt)
    log.error("giving up on %s: %s", url, last_error)
    return "error", ""


def download_series(
    url_template: str,
    start: str | datetime,
    end: str | datetime,
    out_dir: str | Path,
    freq: str = "h",
    pause_s: float = 1.0,
    manifest: str | None = "manifest.csv",
    session: requests.Session | None = None,
) -> list[FetchResult]:
    """Download every timestep in ``[start, end]``.

    ``url_template`` is formatted with ``datetime.strftime``; the file name is
    the last path segment of the resulting URL. A CSV manifest (timestamp,
    file, status, sha256) is appended in ``out_dir`` for reproducibility.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

    results: list[FetchResult] = []
    for ts in pd.date_range(start, end, freq=freq):
        ts = ts.to_pydatetime()
        url = ts.strftime(url_template)
        path = out_dir / url.rstrip("/").rsplit("/", 1)[-1]
        status, digest = fetch_one(url, path, session)
        results.append(FetchResult(ts, path, status, digest))
        log.info("%s %s", status, path.name)
        if status not in ("skipped",):
            time.sleep(pause_s)

    if manifest:
        mpath = out_dir / manifest
        new = not mpath.exists()
        with mpath.open("a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "file", "status", "sha256"])
            for r in results:
                w.writerow([r.timestamp.isoformat(), r.path.name, r.status, r.sha256])
    return results
