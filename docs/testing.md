# Testing

The test suite runs **offline**. It builds a synthetic eruption, a flow advancing
0.5 km/day with detections from all sensors, in a temporary folder, and mocks the FIRMS
API and the tile servers.

```bash
python -m pip install -e ".[test]"
python -m pytest                      # everything
python -m pytest -m "not slow"        # skip the MP4 rendering test
python -m pytest --cov=lavaflow_suite # with coverage
```

or `pixi run -e test test`.

What is covered:

| Module | Checks |
|---|---|
| `common` | date parsing, waypoints (no 0,0), config defaults, zoom ranges, 12-h/daily frames, packaged GVP list |
| shapefiles | WGS84 / UTM reading with and without a working PROJ, pure-Python reader |
| `firms_download` | bbox, date migration, chunked download, merge without duplicates (mocked API) |
| `anomalies` | daily = weekly = monthly = summary totals, short/long period rules, partial weeks |
| `mapper` | FRP/track/period filters, distances, zoom statistics, OpenTopoMap default |
| `speed` | same-day merge, first-advance NaN, speeds, radius toggle |
| `video` | extent/scale helpers, tile-extent regression, offline MP4 render, cancellation |
| `report`, `app`, `cli` | full report, app assembly, command-line options |

Continuous integration runs the tests on Linux, macOS and Windows with Python 3.10–3.12
on every push and pull request (`.github/workflows/tests.yml`).
