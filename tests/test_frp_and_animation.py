import pandas as pd

from lavaflow_suite import animation
from lavaflow_suite import common as lfc
from lavaflow_suite import frp_statistics as frp
from lavaflow_suite import mapper


def test_frp_statistics_cumulative(project):
    df = frp.process_satellite_data(project, "historical_VIIRS_SNPP_NRT_Testvolcano.csv",
                                     pd.Timestamp("2024-03-01"), pd.Timestamp("2024-03-10"))
    assert df["datetime"].min() == pd.Timestamp("2024-03-01 06:30")
    st = frp.get_cumulative_stats(df)
    assert (st["timestamp"].diff().dropna() == pd.Timedelta(hours=12)).all()
    assert (st["q25"] <= st["median"]).all() and (st["median"] <= st["q75"]).all()
    assert frp.process_satellite_data(project, "missing.csv", None, None) is None
    assert frp.get_cumulative_stats(None).empty


def test_frp_layout_builds(project):
    assert frp.get_layout() is not None


def test_animation_uses_12h_frames_for_short_periods(short_project):
    frames, step = animation.get_frames()
    assert step == pd.Timedelta(hours=12) and len(frames) == 10
    marks = animation.frame_marks(frames, step)
    assert marks[0] == "01 Mar" and marks[len(frames) - 1].endswith("12h")


def test_animation_daily_marks(project):
    frames, step = animation.get_frames()
    assert step == pd.Timedelta(days=1)
    marks = animation.frame_marks(frames, step)
    assert 0 in marks and len(frames) - 1 in marks


def test_date_marks_scale_with_period():
    assert all(v.isdigit() for k, v in animation.date_marks("2015-01-01", 3000).items()
               if k not in (0, 3000))
    m = animation.date_marks("2024-01-01", 200)
    assert any(" 24" in v for v in m.values())


def test_animation_timeseries(short_project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, short_project)
    df = animation.load_data()
    assert not df.empty
    fig = animation.build_anim_timeseries(df, cfg, ["RAD"], df["date"].max())
    assert len(fig.data) >= 2
    empty = animation.build_anim_timeseries(df.iloc[0:0], cfg, [], df["date"].min())
    assert len(empty.data) >= 2          # placeholders keep both panels visible


def test_waypoint_icon_fallback():
    assert animation.waypoint_icon("unknown") == animation.waypoint_icon("circle")
    assert animation.waypoint_icon("triangle")["iconSize"] == [18, 18]


def test_layout_builds(short_project):
    assert animation.get_layout() is not None


def test_propagation_map_opens_on_the_anomalies(project):
    from lavaflow_suite import video
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    lay = animation.get_layout()

    def find(node, wanted):
        if getattr(node, 'id', None) == wanted:
            return node
        ch = getattr(node, 'children', None)
        for c in (ch if isinstance(ch, list) else [ch] if ch is not None else []):
            found = find(c, wanted)
            if found is not None:
                return found
        return None

    m = find(lay, 'main-map')
    assert m is not None
    df = lfc.load_filtered_data(project)
    bounds = video.full_extent(df, cfg, [])          # anomalies + vent, layers excluded
    assert m.bounds == bounds
    center, zoom = lfc.center_zoom_for_bounds(bounds)
    assert m.center == center and m.zoom == zoom
    assert m.zoom > 12                               # a 10 km flow is not shown at the old zoom 12


def test_static_layers_do_not_depend_on_the_time_slider(short_project):
    import dash
    app = dash.Dash(__name__, suppress_callback_exceptions=True)
    animation.register_callbacks(app)
    inputs_of = {}
    for key, spec in app.callback_map.items():
        for out in key.strip('.').split('...'):
            inputs_of[out] = [i['id'] for i in spec['inputs']]
    # waypoint labels and shapefile are rebuilt only when the layer selection changes,
    # otherwise the permanent labels blink on every animation step
    for out in ('static-waypoints-layer.children', 'shapefile-layer.children'):
        assert 'time-slider' not in inputs_of[out], out
        assert 'layer-toggle' in inputs_of[out]
    assert inputs_of['base-layer.url'] == ['basemap-select']
    # the anomalies still follow the slider
    assert 'time-slider' in inputs_of['today-points-layer.children']
