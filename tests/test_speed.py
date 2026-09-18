import numpy as np
import pandas as pd
import pytest

from lavaflow_suite import common as lfc
from lavaflow_suite import mapper, speed


def test_compute_speed_merges_same_day_records():
    daily = pd.DataFrame({
        "date_only": ["2024-03-01", "2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04"],
        "distance_km": [1.0, 1.2, 1.2, 2.4, 2.0],
    })
    p = speed.compute_speed(daily)
    # 03-01 (first advance), 03-03 (advance); 03-02 equal and 03-04 retreat are not advances
    assert list(p["date"].dt.strftime("%m-%d")) == ["03-01", "03-03"]
    assert np.isnan(p["speed"].iloc[0])                    # no reference for the first advance
    assert p["speed"].iloc[1] == pytest.approx(1200.0 / 48.0)   # 1.2 km in 48 h -> 25 m/h
    assert (p["speed"].dropna() > 0).all()                 # no artificial zero speeds


def test_compute_speed_no_advance():
    p = speed.compute_speed(pd.DataFrame({"date_only": ["2024-03-01"], "distance_km": [0.0]}))
    assert p.empty


def test_speed_pipeline_and_zoom_stats(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    p = speed.process_speed_data(project)
    assert len(p) == 20
    df = speed.load_speed_data(project)
    full = speed.compute_speed_stats(df)
    assert full["max_dist"] == pytest.approx(10.0, rel=0.02)
    assert full["mean_speed"] == pytest.approx(500.0 / 24.0, rel=0.05)   # 0.5 km/day
    zoom = speed.compute_speed_stats(df, "2024-03-01", "2024-03-05")
    assert zoom["max_dist"] < full["max_dist"]


def test_speed_figure_radius_toggle(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    speed.process_speed_data(project)
    df = speed.load_speed_data(project)
    fig = speed.build_speed_figure(df, cfg)
    assert any("Ref. radius" in (t.name or "") for t in fig.data)
    assert fig.layout.updatemenus                       # show/hide radius button
    fig2 = speed.build_speed_figure(df, dict(cfg, include_reference_radius=False))
    assert not any("Ref. radius" in (t.name or "") for t in fig2.data)
