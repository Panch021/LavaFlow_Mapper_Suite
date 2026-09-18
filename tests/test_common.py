import os

import pandas as pd
import pytest

from lavaflow_suite import common as lfc


def test_parse_firms_date_mixed_formats():
    s = pd.Series(["2024-03-05", "06/03/2024", "", "nan", "garbage"])
    out = lfc.parse_firms_date(s)
    assert out.iloc[0] == pd.Timestamp("2024-03-05")
    assert out.iloc[1] == pd.Timestamp("2024-03-06")      # day first
    assert out.iloc[2:].isna().all()


def test_waypoints_drop_blank_and_zero_entries():
    cfg = {"wpt_names": "A;B;C", "wpt_lats": "-0.4;;0", "wpt_lons": "-91.5;;0",
           "wpt_symbols": "triangle;circle;circle"}
    wpts = lfc.parse_waypoints_from_config(cfg)
    assert wpts == [{"name": "A", "lat": -0.4, "lon": -91.5, "symbol": "triangle"}]


def test_waypoints_keep_empty_for_editor():
    cfg = {"wpt_names": "", "wpt_lats": "", "wpt_lons": ""}
    wpts = lfc.parse_waypoints_from_config(cfg, keep_empty=True)
    assert len(wpts) == 1 and wpts[0]["lat"] is None


def test_default_config_has_optional_layers_off(workdir):
    cfg = lfc.load_global_config()
    assert cfg["include_reference_radius"] is False
    assert cfg["include_shapefile"] is False
    assert cfg["include_reference_waypoint"] is False


def test_active_folder_and_config(project):
    assert lfc.get_active_folder() == project
    cfg = lfc.load_global_config()
    assert cfg["volcano"] == "Testvolcano"
    assert cfg["filter_frp"] == 20 and cfg["filter_track"] == 0.5
    assert cfg["include_reference_radius"] is True
    assert isinstance(cfg["wpt_lats"], str)            # lists stay raw strings
    assert lfc.period_tag(cfg) == "20240301_20240320"
    assert not lfc.is_example_path(project)
    assert lfc.is_example_path(os.path.join("examples", "Wolf"))


def test_active_folder_legacy_bare_name(workdir):
    os.makedirs("projects/Sierra_Negra")
    with open("active_volcano.txt", "w") as f:
        f.write("Sierra Negra")
    assert lfc.get_active_folder() == os.path.join("projects", "Sierra_Negra")


def test_no_active_folder(workdir):
    assert lfc.get_active_folder() is None


def test_safe_name():
    assert lfc.safe_name("Piton de la Fournaise!") == "Piton_de_la_Fournaise"
    assert lfc.safe_name("***") == "Volcano"


def test_robust_stats():
    st = lfc.robust_stats([1, 2, 3, None, 4])
    assert st["n"] == 4 and st["max"] == 4 and st["mean"] == pytest.approx(2.5)
    assert 3.5 < st["p95"] <= 4
    assert lfc.robust_stats([None]) is None


@pytest.mark.parametrize("relayout, expected", [
    (None, ("fb0", "fb1")),
    ({"xaxis.autorange": True}, ("fb0", "fb1")),
    ({"xaxis.range[0]": "2024-03-02", "xaxis.range[1]": "2024-03-05"},
     (pd.Timestamp("2024-03-02"), pd.Timestamp("2024-03-05"))),
    ({"xaxis2.range": ["2024-03-01 12:00", "2024-03-03"]},
     (pd.Timestamp("2024-03-01 12:00"), pd.Timestamp("2024-03-03"))),
    ({"yaxis.range[0]": 1}, ("fb0", "fb1")),
])
def test_xrange_from_relayout(relayout, expected):
    assert lfc.xrange_from_relayout(relayout, fallback=("fb0", "fb1")) == expected


def test_stem_xy_uses_string_dates():
    xs, ys = lfc.stem_xy(pd.to_datetime(["2024-03-01", "2024-03-02"]), [5, 7])
    assert xs == ["2024-03-01 00:00:00", "2024-03-01 00:00:00", None,
                  "2024-03-02 00:00:00", "2024-03-02 00:00:00", None]
    assert ys == [0, 5, None, 0, 7, None]


def test_animation_frames_12h_for_short_periods():
    frames, step = lfc.animation_frames("2024-03-01", "2024-03-05 23:59")
    assert step == pd.Timedelta(hours=12)
    assert len(frames) == 10
    assert frames[0] == (pd.Timestamp("2024-03-01 00:00"), pd.Timestamp("2024-03-01 12:00"))
    assert frames[-1][1] == pd.Timestamp("2024-03-06")


def test_animation_frames_daily_and_multiday():
    frames, step = lfc.animation_frames("2024-01-01", "2024-03-31")
    assert step == pd.Timedelta(days=1) and len(frames) == 91
    frames, step = lfc.animation_frames("2024-01-01", "2024-12-31", max_frames=100)
    assert step == pd.Timedelta(days=4)
    assert len(frames) <= 100
    # windows are contiguous and cover the whole period
    assert all(a[1] == b[0] for a, b in zip(frames, frames[1:]))
    assert frames[-1][1] == pd.Timestamp("2025-01-01")


def test_frame_label():
    t0 = pd.Timestamp("2024-03-01 12:00")
    lbl = lfc.frame_label(t0, pd.Timestamp("2024-03-02"), pd.Timedelta(hours=12),
                          times=[pd.Timestamp("2024-03-01 19:00")])
    assert "12:00–24:00 UTC" in lbl and "19:00" in lbl
    assert lfc.frame_label(pd.Timestamp("2024-03-01"), pd.Timestamp("2024-03-02"),
                           pd.Timedelta(days=1)) == "01 Mar 2024"
    assert lfc.frame_label(pd.Timestamp("2024-03-01"), pd.Timestamp("2024-03-05"),
                           pd.Timedelta(days=4)) == "01 Mar 2024 – 04 Mar 2024"


def test_gvp_catalogue_is_packaged(workdir):
    path = lfc.gvp_catalogue_path()
    assert path and os.path.exists(path)
    df = pd.read_csv(path)
    assert "Volcano Name" in df.columns and len(df) > 1000


def test_shapefile_path_resolution(project):
    cfg = {"include_shapefile": True, "shapefile_path": "flow"}
    assert lfc.shapefile_path(cfg, project) is None          # file does not exist
    open(os.path.join(project, "flow.shp"), "w").close()
    assert lfc.shapefile_path(cfg, project) == os.path.join(project, "flow.shp")
    assert lfc.shapefile_path({"include_shapefile": False, "shapefile_path": "flow"}, project) is None


def test_update_config_values_keeps_other_keys(project):
    before = lfc.load_global_config()
    lfc.update_config_values(project, {"wpt_names": "A;B", "new_key": "42"})
    text = open(lfc.config_path_for(project), encoding="utf-8").read()
    assert "wpt_names=A;B" in text and "new_key=42" in text
    after = lfc.load_global_config()
    for k in ("volcano", "lats_vent", "filter_frp", "map_key", "start_day_str"):
        assert after[k] == before[k]
    assert text.count("wpt_names=") == 1


def test_waypoint_fields():
    f = lfc.waypoint_fields([{"name": "A", "lat": -0.4123456, "lon": -91.5, "symbol": "triangle"},
                             {"name": "", "lat": 1, "lon": 2}])
    assert f["wpt_names"] == "A;"
    assert f["wpt_lats"] == "-0.41235;1.00000"
    assert f["wpt_symbols"] == "triangle;circle"


def test_center_zoom_for_bounds():
    # Fernandina 2024: flow of ~8.5 x 16.8 km -> fits in a 900x430 px map at zoom ~11.75
    center, zoom = lfc.center_zoom_for_bounds([[-0.5109, -91.5305], [-0.3601, -91.4542]])
    assert center == pytest.approx([-0.4355, -91.49235], abs=1e-4)
    assert 11 <= zoom <= 12.5
    assert (zoom / lfc.ZOOM_STEP) % 1 == 0                       # multiple of the zoom step
    # a smaller area zooms in further, a huge one zooms out, and limits are respected
    assert lfc.center_zoom_for_bounds([[-0.401, -91.501], [-0.399, -91.499]])[1] == 17
    assert lfc.center_zoom_for_bounds([[-40, -120], [40, -40]])[1] <= 4
    assert lfc.center_zoom_for_bounds([[0, 0], [0, 0]])[1] >= 1   # degenerate box, no crash


def test_center_zoom_never_crops_the_data():
    import math
    bounds = [[-0.51, -91.53], [-0.36, -91.45]]
    (s, w), (n, e) = bounds
    _, zoom = lfc.center_zoom_for_bounds(bounds, width_px=900, height_px=430)
    world_px = 256 * 2 ** zoom
    visible_lon = 360 * 900 / world_px
    y = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    visible_y = 2 * math.pi * 430 / world_px
    assert visible_lon >= (e - w) and visible_y >= (y(n) - y(s))
