"""Shared fixtures: a throw-away working directory with a synthetic project.

All tests run offline. The synthetic eruption is a lava flow that advances
~0.5 km per day south-east of a fictitious vent, observed by the three VIIRS
satellites (day and night passes) plus MODIS.
"""
import os

import numpy as np
import pandas as pd
import pytest

VENT_LAT, VENT_LON = -0.40, -91.50
VOLCANO = "Testvolcano"

CONFIG_TEMPLATE = """volcano={volcano}
lats_vent={lat}
longs_vent={lon}
start_day_str={start} 00:00
end_day_str={end} 23:59
filter_frp=20
frp_filter_mode=gt
filter_track=0.5
map_key=INSERT_YOUR_MAP_KEY_HERE
include_reference_radius=True
ref_radius_m=5000
include_shapefile=False
shapefile_path=
include_reference_waypoint=True
wpt_names=Station A;Blank;Zero
wpt_lats=-0.41;;0
wpt_lons=-91.49;;0
wpt_symbols=triangle;circle;circle
"""

VIIRS_COLS = ["latitude", "longitude", "bright_ti4", "scan", "track", "acq_date", "acq_time",
              "satellite", "instrument", "confidence", "version", "bright_ti5", "frp", "daynight"]


def synthetic_viirs(start, n_days, sat_code, seed=0):
    """One file's worth of VIIRS detections: flow front + noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        day = pd.Timestamp(start) + pd.Timedelta(days=d)
        for hhmm, dn in (("0630", "N"), ("1900", "D")):
            front_km = 0.5 * (d + 1)
            for k in range(6):
                dist = front_km * (k + 1) / 6
                lat = VENT_LAT - dist / 111.0 * 0.7
                lon = VENT_LON + dist / 111.0 * 0.7
                rows.append([lat, lon, 330.0, 0.4, 0.40, day.strftime("%Y-%m-%d"), hhmm, sat_code,
                             "VIIRS", "n", "2.0NRT", 290.0, float(rng.uniform(25, 120)), dn])
            # a low-FRP / bad-geometry detection that the filter must drop
            rows.append([VENT_LAT, VENT_LON, 300.0, 0.6, 0.70, day.strftime("%Y-%m-%d"), hhmm, sat_code,
                         "VIIRS", "n", "2.0NRT", 280.0, 3.0, dn])
    return pd.DataFrame(rows, columns=VIIRS_COLS)


def make_project(root, start="2024-03-01", n_days=20, name=VOLCANO):
    folder = os.path.join("projects", name)
    os.makedirs(os.path.join(root, folder), exist_ok=True)
    s = pd.Timestamp(start)
    e = s + pd.Timedelta(days=n_days - 1)
    with open(os.path.join(root, folder, f"config_{name}.txt"), "w") as f:
        f.write(CONFIG_TEMPLATE.format(volcano=name, lat=VENT_LAT, lon=VENT_LON,
                                       start=s.strftime("%d/%m/%Y"), end=e.strftime("%d/%m/%Y")))
    for i, (tag, code) in enumerate([("SNPP", "N"), ("NOAA20", "N20"), ("NOAA21", "N21")]):
        synthetic_viirs(s, n_days, code, seed=i).to_csv(
            os.path.join(root, folder, f"historical_VIIRS_{tag}_NRT_{name}.csv"), index=False)
    modis = synthetic_viirs(s, n_days, "A", seed=9).iloc[::5].copy()
    # MODIS files use DD/MM/YYYY in some legacy downloads: exercise the mixed-date parser
    modis["acq_date"] = pd.to_datetime(modis["acq_date"]).dt.strftime("%d/%m/%Y")
    modis.to_csv(os.path.join(root, folder, f"historical_MODIS_NRT_{name}.csv"), index=False)
    with open(os.path.join(root, "active_volcano.txt"), "w") as f:
        f.write(folder)
    return folder


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Empty working directory (cwd) for the suite."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def project(workdir):
    """Working directory with an active 20-day synthetic project."""
    return make_project(str(workdir))


@pytest.fixture
def short_project(workdir):
    """Active project spanning only 5 days (12-hour animation, short summary)."""
    return make_project(str(workdir), n_days=5)
