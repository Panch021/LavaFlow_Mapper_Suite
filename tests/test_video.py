import os

import pytest

from lavaflow_suite import common as lfc
from lavaflow_suite import mapper, video


def test_nice_scale_length():
    assert video.nice_scale_length(10_000) == 2000
    assert video.nice_scale_length(37_000) == 5000
    assert video.nice_scale_length(900) == 100


def test_normalise_bounds():
    assert video.normalise_bounds([[-1, -92], [0, -91]]) == [[-1.0, -92.0], [0.0, -91.0]]
    leaflet = {"_southWest": {"lat": -1, "lng": -92}, "_northEast": {"lat": 0, "lng": -91}}
    assert video.normalise_bounds(leaflet) == [[-1.0, -92.0], [0.0, -91.0]]
    assert video.normalise_bounds([[0, 0], [-1, 1]]) is None
    assert video.normalise_bounds("bad") is None


def test_output_name_has_project_and_period(project):
    cfg = lfc.load_global_config()
    assert os.path.basename(video.output_path(project, cfg)) == \
        "Testvolcano_20240301_20240320_propagation.mp4"


def test_full_extent_includes_radius(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    df = lfc.load_filtered_data(project)
    no_rad = video.full_extent(df, cfg, [])
    rad = video.full_extent(df, cfg, ["RAD"])
    assert rad[0][0] < no_rad[0][0] and rad[1][0] > no_rad[1][0]


def test_basemap_extent_uses_tile_size(monkeypatch):
    """Regression test for the white-map bug (extent computed from pixels, not tiles)."""
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (256, 256), (10, 20, 30)).save(buf, format="PNG")
    png = buf.getvalue()

    class Resp:
        status_code = 200
        content = png
        headers = {"Content-Type": "image/png"}

        def raise_for_status(self):
            pass

    import requests

    class FakeSession:
        def get(self, *a, **k):
            return Resp()

    monkeypatch.setattr(requests, "Session", FakeSession)
    x0, y0 = video.merc(-0.5, -91.6)
    x1, y1 = video.merc(-0.3, -91.4)
    img, ext = video.fetch_basemap("https://tile.example/{z}/{x}/{y}.png", x0, x1, y0, y1, 800)
    assert img is not None
    ex0, ex1, ey0, ey1 = ext
    assert ex0 <= x0 and ex1 >= x1 and ey0 <= y0 and ey1 >= y1
    assert (ex1 - ex0) < 50 * (x1 - x0)


@pytest.mark.slow
def test_render_short_video_offline(short_project, monkeypatch, tmp_path):
    """Renders a real (small) MP4 with the basemap download disabled."""
    if not video.find_ffmpeg():
        pytest.skip("ffmpeg not available")
    monkeypatch.setattr(video, "fetch_basemap_with_fallback", lambda *a, **k: (None, None, None))
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, short_project)
    df = lfc.load_filtered_data(short_project)
    out = str(tmp_path / "clip.mp4")
    steps = []
    res = video.render_video(short_project, cfg, df, None, video.BASEMAPS["topo"], ["RAD", "WPT"], 10, out,
                             progress=lambda p, m, **k: steps.append(p))
    assert os.path.exists(res) and os.path.getsize(res) > 10_000
    assert steps and steps[-1] >= 0.9


def test_render_can_be_cancelled(short_project, monkeypatch, tmp_path):
    monkeypatch.setattr(video, "fetch_basemap_with_fallback", lambda *a, **k: (None, None, None))
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, short_project)
    df = lfc.load_filtered_data(short_project)
    with pytest.raises(video.RenderCancelled):
        video.render_video(short_project, cfg, df, None, "", [], 5, str(tmp_path / "x.mp4"),
                           cancel_flag=lambda: True)
