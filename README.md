# air-health-twin

[![tests](https://github.com/tevet2005/air-health-twin/actions/workflows/tests.yml/badge.svg)](https://github.com/tevet2005/air-health-twin/actions/workflows/tests.yml)

**Open tooling for assessing the health impact of air pollution worldwide, built toward an air-quality digital twin.**

Air pollution is one of the largest environmental risks to human health. Estimating its burden
consistently in any region means combining heterogeneous sources: gridded reanalyses and
forecasts, satellite-derived maps, ground monitoring networks and population data. These sources
differ in resolution, time zone, timestamp convention and missing-data codes. `airhealth` provides
region-agnostic building blocks for that pipeline:

| Module | What it does |
| --- | --- |
| `airhealth.sources.cams` | Monthly download of Copernicus Atmosphere (ADS) data, e.g. the CAMS global reanalysis, for any bounding box or the whole globe |
| `airhealth.sources.http_timeseries` | Generic downloader for file-per-timestep products (hourly/daily maps) with retries, 404 handling, atomic writes and a SHA-256 manifest |
| `airhealth.qc` | Error-code masking, time-zone alignment, completeness reports against the *expected* time axis, hour-ending-aware daily means, multi-station summaries |
| `airhealth.hia` | Log-linear concentration-response functions: relative risk, population attributable fraction and attributable cases, vectorised for grids |
| `airhealth.region` | Bounding-box definitions shared by all connectors |

No region, station or study period is hard-coded: every function takes these as arguments.

## Install

```bash
git clone https://github.com/tevet2005/air-health-twin.git
cd air-health-twin
pip install -e ".[cams,dev]"
```

## Quick start

### 1. Download reanalysis data

Register at the [Copernicus Atmosphere Data Store](https://ads.atmosphere.copernicus.eu/) and put
your token in `~/.cdsapirc` (never in code):

```
url: https://ads.atmosphere.copernicus.eu/api
key: <your-personal-access-token>
```

```bash
# any bounding box: north west south east
python -m airhealth.sources.cams --bbox 60 -10 35 30 --start 2020-01 --end 2020-12 --out data/cams
```

### 2. Download a file-per-hour product

```python
from airhealth.sources.http_timeseries import download_series

download_series(
    "https://example.org/pm25/%Y/%m/PM25_%Y%m%d%H.tif",
    start="2024-01-01 00:00", end="2024-01-31 23:00", freq="h",
    out_dir="data/pm25_maps",
)
```

### 3. Quality-control station data

```python
from airhealth import qc

hourly = qc.clean(raw_hourly)                    # wide frame: time x station
hourly.index = qc.to_timezone(hourly.index, "Europe/Paris")
report = qc.completeness(hourly, expected_index) # missing rate per station
daily = qc.daily_mean(hourly, min_valid_hours=20)
summary = qc.regional_daily(daily, threshold=15) # 15 µg/m³: WHO 2021 24-h PM2.5 guideline
```

### 4. Estimate attributable health burden

```python
from airhealth import hia

beta = hia.beta_from_rr(1.08, unit=10)           # RR per 10 µg/m³ from the literature
deaths = hia.attributable_cases(
    conc=pm25_grid, population=pop_grid, baseline_rate=mortality_rate,
    beta=beta, counterfactual=5.0,               # WHO 2021 annual PM2.5 guideline
)
```

## Roadmap

- [x] Data acquisition: CAMS reanalysis, generic time-series files
- [x] Quality control and temporal harmonisation
- [x] Log-linear health impact functions
- [ ] Connectors for open global datasets: OpenAQ ground monitors, gridded population, baseline mortality
- [ ] Spatial harmonisation: regridding, point-to-grid extraction, model-vs-observation evaluation
- [ ] Data fusion and bias correction of gridded estimates with monitor data
- [ ] Non-linear and multi-pollutant exposure-response functions with uncertainty propagation
- [ ] **Digital twin**: continuously updated exposure and health-burden maps with scenario analysis
  (e.g. "what if emissions fall by 30%?")

## Development

```bash
pytest
```

## License

MIT. See [LICENSE](LICENSE). Data obtained with these tools remains subject to each provider's terms.
