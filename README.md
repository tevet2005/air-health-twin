# air-health-twin

[![tests](https://github.com/tevet2005/air-health-twin/actions/workflows/tests.yml/badge.svg)](https://github.com/tevet2005/air-health-twin/actions/workflows/tests.yml)

**An open air-quality health forecast for anywhere on Earth, built toward a digital twin of
air pollution and its health impact.**

Air pollution is one of the largest environmental risks to human health, but forecasts usually
stop at a concentration number. This project aims to answer, for any location, the questions people
actually ask:

1. **Will PM2.5 be high tomorrow?**
2. **What will the weather be: temperature, humidity, wind?**
3. **If I spend a given amount of time in that air, what health effects are expected?**
4. **How careful should people with asthma be?**

## Status

| Question | What is needed | Status |
| --- | --- | --- |
| 1. PM2.5 tomorrow | Point and gridded forecasts, then bias correction with ground monitors | ✅ Forecasts · ⏳ bias correction |
| 2. Weather | Point weather forecasts | ✅ |
| 3. Exposure → health effect | Inhaled dose (concentration × duration × breathing rate), short-term exposure-response functions | 🧱 Log-linear risk functions · ⏳ dose and short-term coefficients |
| 4. Asthma advice | Asthma-specific risk estimates and tiered advice for sensitive groups | ⏳ |

### Try it

```bash
pip install -e .
python -m airhealth.forecast --lat 48.85 --lon 2.35
```

```
2026-11-05: PM2.5 daily mean 18.6 µg/m³ (max 28.8, +5.6 vs previous day), ABOVE the 15 µg/m³ 24-h guideline
  temperature 4.7–11.8 °C, humidity 77 %, wind 1.5 m/s, precipitation 0.0 mm
```

## Modules

| Module | What it does |
| --- | --- |
| `airhealth.forecast` | Tomorrow's PM2.5 and weather outlook for any coordinates (local time, WHO guideline check, day-over-day change) |
| `airhealth.sources.openmeteo` | Hourly point forecasts of air quality (CAMS-based) and weather, no API key needed |
| `airhealth.sources.cams` | Gridded CAMS data from the Copernicus Atmosphere Data Store: global forecasts (up to 5 days) and reanalysis, for any bounding box |
| `airhealth.sources.http_timeseries` | Generic downloader for file-per-timestep products with retries, 404 handling, atomic writes and a SHA-256 manifest |
| `airhealth.qc` | Error-code masking, time-zone alignment, completeness against the expected time axis, hour-ending-aware daily means, multi-station summaries |
| `airhealth.hia` | Log-linear concentration-response functions: relative risk, attributable fraction and attributable cases, vectorised for grids |
| `airhealth.region` | Bounding boxes shared by all connectors |

No region, station or study period is hard-coded: every function takes them as arguments.

## Usage

### Forecast outlook in Python

```python
from airhealth import forecast

outlook = forecast.tomorrow(lat=48.85, lon=2.35)
outlook.exceeds_guideline     # True / False
outlook.pm25_mean, outlook.wind_speed_mean
```

### Gridded forecasts and reanalysis

Register at the [Copernicus Atmosphere Data Store](https://ads.atmosphere.copernicus.eu/) and put
your token in `~/.cdsapirc` (never in code):

```
url: https://ads.atmosphere.copernicus.eu/api
key: <your-personal-access-token>
```

```python
from airhealth.region import BoundingBox
from airhealth.sources import cams

box = BoundingBox(north=60, west=-10, south=35, east=30)
cams.download_forecast("2026-11-04", "data/forecast", bbox=box)        # 0–120 h ahead
cams.download_monthly("2020-01", "2020-12", "data/reanalysis", bbox=box)
```

### Quality control of monitoring data

```python
from airhealth import qc

hourly = qc.clean(raw_hourly)                    # wide frame: time x station
hourly.index = qc.to_timezone(hourly.index, "Europe/Paris")
report = qc.completeness(hourly, expected_index) # missing rate per station
daily = qc.daily_mean(hourly, min_valid_hours=20)
```

### Attributable health burden

```python
from airhealth import hia

beta = hia.beta_from_rr(1.08, unit=10)           # RR per 10 µg/m³ from the literature
deaths = hia.attributable_cases(conc=pm25_grid, population=pop_grid,
                                baseline_rate=mortality_rate, beta=beta, counterfactual=5.0)
```

## Roadmap

**1. PM2.5 tomorrow**
- [x] Point forecasts (Open-Meteo / CAMS) and gridded CAMS global forecasts
- [x] Daily outlook against the WHO 24-h guideline
- [ ] Ground-monitor connectors (e.g. OpenAQ) and forecast-vs-observation evaluation
- [ ] Machine-learning bias correction of forecasts using monitors and meteorology

**2. Weather**
- [x] Hourly temperature, humidity, wind and precipitation forecasts
- [ ] Meteorological drivers of pollution episodes (stagnation, inversions)

**3. Exposure → health effect**
- [x] Log-linear relative risk and attributable fraction
- [ ] Inhaled dose from duration and activity level (rest, walking, exercise)
- [ ] Short-term exposure-response functions from meta-analyses, with uncertainty

**4. Asthma and sensitive groups**
- [ ] Asthma exacerbation risk relative to a clean-air day
- [ ] Tiered, evidence-based advice (e.g. limit outdoor exercise)

**Digital twin**
- [ ] Continuously updated exposure and health-risk maps
- [ ] Scenario analysis (e.g. "what if emissions fall by 30%?")

## Disclaimer

Health outputs are derived from population-level epidemiological evidence. They describe changes in
risk, not individual predictions, and are **not medical advice**. People with asthma or other
conditions should follow their doctor's guidance.

## Data and attribution

- Air-quality and weather point forecasts: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0), based on
  [CAMS](https://atmosphere.copernicus.eu/) and national weather services.
- Gridded data: Copernicus Atmosphere Monitoring Service, retrieved via the Atmosphere Data Store.

Data obtained with these tools remains subject to each provider's terms.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT. See [LICENSE](LICENSE).
