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


def test_capture_control_only_in_the_app_map(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    df = lfc.load_filtered_data(project)
    html_app, _ = mapper.build_folium_map(project, cfg, df, default_basemap="topo", capture=True)
    assert "Add waypoints" in html_app and "lavaflow-capture" in html_app
    # while capturing, layers must not swallow the click
    assert "lf-capturing" in html_app and "pointer-events: none !important" in html_app
    html_report, _ = mapper.build_folium_map(project, cfg, df, fit="anomalies")
    assert "Add waypoints" not in html_report


def test_save_captured_waypoints_appends_and_enables_layer(project):
    pts = [{"lat": -0.405, "lon": -91.495}, {"lat": -0.4123456, "lon": -91.4987654}]
    ok, msg = mapper.save_captured_waypoints(project, pts, names=["Crater rim", ""])
    assert ok, msg
    cfg = lfc.load_global_config()
    assert cfg["include_reference_waypoint"] is True
    wpts = lfc.parse_waypoints_from_config(cfg)
    # the pre-existing waypoint of the fixture is kept, the 0,0 placeholder is not
    assert [w["name"] for w in wpts] == ["Station A", "Crater rim", "WP 3"]
    assert wpts[-1]["lat"] == pytest.approx(-0.41235)      # stored with 5 decimals
    assert wpts[-1]["lon"] == pytest.approx(-91.49877)
    # other settings are untouched
    assert cfg["filter_frp"] == 20 and cfg["map_key"] == "INSERT_YOUR_MAP_KEY_HERE"


def test_save_captured_waypoints_replace_and_errors(project):
    assert mapper.save_captured_waypoints(project, [])[0] is False
    assert mapper.save_captured_waypoints(None, [{"lat": 1, "lon": 2}])[0] is False
    ok, _ = mapper.save_captured_waypoints(project, [{"lat": -0.4, "lon": -91.5}], replace=True)
    assert ok
    wpts = lfc.parse_waypoints_from_config(lfc.load_global_config())
    assert len(wpts) == 1 and wpts[0]["name"] == "WP 1"


def test_captured_rows_keep_typed_names():
    pts = [{"lat": -0.4, "lon": -91.5}, {"lat": -0.41, "lon": -91.51}, {"lat": -0.42, "lon": -91.52}]
    rows = mapper.captured_rows(pts, names=["Crater rim", None])
    values = [c.children[0].value for c in rows.children]
    assert values == ["Crater rim", "WP 2", "WP 3"]      # typed name survives, new rows get defaults
    assert mapper.captured_rows([]).className == "lf-muted"
