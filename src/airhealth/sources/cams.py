"""Download gridded atmospheric-composition data from the Copernicus
Atmosphere Data Store (ADS), e.g. the CAMS global reanalysis.

Credentials are never stored in code. ``cdsapi`` reads them from
``~/.cdsapirc`` or the ``CDSAPI_URL`` / ``CDSAPI_KEY`` environment variables::

    url: https://ads.atmosphere.copernicus.eu/api
    key: <your-personal-access-token>

Command-line example::

    python -m airhealth.sources.cams --bbox 60 -10 35 30 \\
        --start 2020-01 --end 2020-12 --out data/cams
"""
from __future__ import annotations

import argparse
import calendar
import logging
import time
from pathlib import Path
from typing import Iterator, Sequence

from airhealth.region import GLOBAL, BoundingBox

log = logging.getLogger(__name__)

DEFAULT_DATASET = "cams-global-reanalysis-eac4"
DEFAULT_TIMES = [f"{h:02d}:00" for h in range(0, 24, 3)]
DEFAULT_VARIABLES = [
    "particulate_matter_2.5um",
    "particulate_matter_10um",
    "2m_temperature",
    "surface_pressure",
]


def iter_months(start: str, end: str) -> Iterator[tuple[int, int]]:
    """Yield (year, month) from ``start`` to ``end`` inclusive (both ``YYYY-MM``)."""
    y, m = map(int, start.split("-"))
    y_end, m_end = map(int, end.split("-"))
    if (y, m) > (y_end, m_end):
        raise ValueError(f"start {start} is after end {end}")
    while (y, m) <= (y_end, m_end):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def build_request(
    year: int,
    month: int,
    bbox: BoundingBox,
    variables: Sequence[str] = DEFAULT_VARIABLES,
    times: Sequence[str] = DEFAULT_TIMES,
) -> dict:
    """Build an ADS request covering one calendar month."""
    last_day = calendar.monthrange(year, month)[1]
    return {
        "variable": list(variables),
        "date": f"{year}-{month:02d}-01/{year}-{month:02d}-{last_day}",
        "time": list(times),
        "data_format": "netcdf",
        "area": bbox.as_cds_area(),
    }


def download_monthly(
    start: str,
    end: str,
    out_dir: str | Path,
    bbox: BoundingBox = GLOBAL,
    variables: Sequence[str] = DEFAULT_VARIABLES,
    dataset: str = DEFAULT_DATASET,
    times: Sequence[str] = DEFAULT_TIMES,
    pause_s: float = 3.0,
    client=None,
) -> list[Path]:
    """Download one NetCDF file per month. Existing files are skipped.

    Returns the paths that exist after the run.
    """
    if client is None:
        import cdsapi  # imported lazily so the rest of the package works without it

        client = cdsapi.Client()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    done: list[Path] = []

    for year, month in iter_months(start, end):
        path = out_dir / f"{dataset}_{bbox.tag()}_{year}{month:02d}.nc"
        if path.exists() and path.stat().st_size > 0:
            log.info("skip %s (exists)", path.name)
            done.append(path)
            continue
        try:
            client.retrieve(dataset, build_request(year, month, bbox, variables, times), str(path))
            log.info("saved %s", path.name)
            done.append(path)
        except Exception as exc:  # keep going; one bad month should not stop a long run
            log.error("failed %d-%02d: %s", year, month, exc)
        time.sleep(pause_s)
    return done


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Download monthly CAMS/ADS NetCDF files.")
    p.add_argument("--bbox", nargs=4, type=float, metavar=("N", "W", "S", "E"),
                   help="bounding box; omit for the whole globe")
    p.add_argument("--start", required=True, help="first month, YYYY-MM")
    p.add_argument("--end", required=True, help="last month, YYYY-MM")
    p.add_argument("--out", default="data/cams", help="output directory")
    p.add_argument("--dataset", default=DEFAULT_DATASET)
    p.add_argument("--variables", nargs="+", default=DEFAULT_VARIABLES)
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    bbox = BoundingBox(*args.bbox) if args.bbox else GLOBAL
    download_monthly(args.start, args.end, args.out, bbox, args.variables, args.dataset)


if __name__ == "__main__":
    main()
