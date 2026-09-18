import os

import numpy as np
import pandas as pd
import pytest

from lavaflow_suite import common as lfc
from lavaflow_suite import mapper


def test_haversine_one_degree_latitude():
    d = mapper.haversine_km(0.0, 0.0, np.array([1.0]), np.array([0.0]))
    assert d[0] == pytest.approx(111.19, abs=0.05)


def test_run_filter_applies_frp_track_and_period(project):
    cfg = lfc.load_global_config()
    out = mapper.run_filter(cfg, project)
    assert not out.empty
    assert (out["frp"] >= 20).all() and (out["track"] <= 0.5).all()
    s, e = lfc.get_period(cfg)
    assert out["date"].between(s, e).all()
    assert set(out["satellite"]) == {"SNPP", "NOAA20", "NOAA21"}
    for name in ("filter_VIIRS_combined.csv", "max_distance_per_day_VIIRS.csv"):
        assert os.path.exists(os.path.join(project, name))
    # distance grows with time (synthetic flow advances 0.5 km/day)
    daily = pd.read_csv(os.path.join(project, "max_distance_per_day_VIIRS.csv"))
    per_day = daily.groupby("date_only")["distance_km"].max()
    assert per_day.is_monotonic_increasing
    assert per_day.iloc[-1] == pytest.approx(10.0, rel=0.02)


def test_run_filter_lower_than_mode(project):
    cfg = dict(lfc.load_global_config(), frp_filter_mode="lt", filter_frp=10, filter_track=1.0)
    out = mapper.run_filter(cfg, project)
    assert (out["frp"] <= 10).all() and len(out) > 0


def test_zoom_stats(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    df = lfc.load_filtered_data(project)
    full = mapper.compute_ts_stats(df)
    zoom = mapper.compute_ts_stats(df, "2024-03-01", "2024-03-03 23:59")
    assert zoom["n"] < full["n"]
    assert zoom["dist"]["max"] < full["dist"]["max"]
    assert mapper.compute_ts_stats(df, "2030-01-01")["frp"] is None


def test_folium_map_defaults_to_opentopomap(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    df = lfc.load_filtered_data(project)
    html, warning = mapper.build_folium_map(project, cfg, df, fit="anomalies", default_basemap="topo")
    assert not warning
    assert "opentopomap" in html.lower()
    assert "Station A" in html                    # valid waypoint drawn
    assert "Zero" not in html                     # 0,0 placeholder skipped


def test_timeseries_figure(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    fig = mapper.build_timeseries_figure(lfc.load_filtered_data(project), cfg)
    assert len(fig.data) > 0
