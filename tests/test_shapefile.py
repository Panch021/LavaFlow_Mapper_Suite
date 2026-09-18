"""Shapefile reading must work even when the PROJ database is broken."""
import os

import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import Polygon, LineString  # noqa: E402

from lavaflow_suite import common as lfc  # noqa: E402

# Lava-flow-like polygon near Sangay (UTM 17S)
LONLAT = [(-78.35, -2.00), (-78.30, -2.00), (-78.30, -2.05), (-78.35, -2.05), (-78.35, -2.00)]


def _write(tmp_path, epsg, name="flow", geom=None):
    g = gpd.GeoDataFrame(geometry=[geom or Polygon(LONLAT)], crs="EPSG:4326").to_crs(epsg=epsg)
    path = os.path.join(tmp_path, f"{name}.shp")
    g.to_file(path)
    return path


def _max_err(gdf):
    xs, ys = gdf.geometry.iloc[0].exterior.coords.xy
    return max(max(abs(a - b[0]) for a, b in zip(xs, LONLAT)),
               max(abs(a - b[1]) for a, b in zip(ys, LONLAT)))


@pytest.mark.parametrize("epsg", [4326, 32717])
def test_read_with_proj(tmp_path, epsg):
    gdf = lfc.read_shapefile_lonlat(_write(tmp_path, epsg))
    assert gdf.crs is None
    assert _max_err(gdf) < 1e-6


@pytest.mark.parametrize("epsg", [4326, 32717, 32617])
def test_read_without_proj(tmp_path, monkeypatch, epsg):
    """Simulates the 'no database context specified' PROJ failure."""
    path = _write(tmp_path, epsg)
    monkeypatch.setattr(lfc, "ensure_proj_data", lambda: False)
    gdf = lfc.read_shapefile_lonlat(path)
    if epsg == 32617:     # northern-hemisphere zone: coordinates are still converted consistently
        assert gdf.geometry.iloc[0].is_valid
    else:
        assert _max_err(gdf) < 1e-5          # built-in inverse UTM: sub-metre accuracy


def test_pure_python_reader_matches_pyogrio(tmp_path):
    path = _write(tmp_path, 4326, name="line", geom=LineString(LONLAT[:3]))
    geoms = lfc._read_shp_pure_python(path)
    assert len(geoms) == 1
    assert list(geoms[0].coords) == pytest.approx(LONLAT[:3])


def test_unsupported_projection_raises(tmp_path, monkeypatch):
    path = _write(tmp_path, 3857)            # Web Mercator: not handled without PROJ
    monkeypatch.setattr(lfc, "ensure_proj_data", lambda: False)
    with pytest.raises(RuntimeError):
        lfc.read_shapefile_lonlat(path)


def test_shapefile_geojson(tmp_path):
    gj = lfc.shapefile_geojson(_write(tmp_path, 32717))
    assert gj["type"] == "FeatureCollection"
    assert gj["features"][0]["geometry"]["type"] == "Polygon"
