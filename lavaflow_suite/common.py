"""
lavaflow_suite/common.py
========================
Shared helpers used by every module of the LavaFlow Mapper Suite.

Centralising these functions guarantees that all tabs (Anomalies Count,
FRP Statistics, LavaFlow Mapper, Propagation, Speed and Export Report)
read the same project folder, parse the same configuration file in the
same way and interpret waypoints identically.
"""
import math
import os
import re
import sys
import pandas as pd

ACTIVE_FILE = "active_volcano.txt"
EXAMPLES_DIR = "examples"
PROJECTS_DIR = "projects"
GVP_FILENAME = "GVP_Volcano_List_Holocene.csv"
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def gvp_catalogue_path():
    """Path of the GVP Holocene catalogue.

    A copy in the working directory takes precedence (so users can drop in
    an updated list); otherwise the copy shipped with the package is used.
    """
    for cand in (GVP_FILENAME, os.path.join(PACKAGE_DIR, "data", GVP_FILENAME)):
        if os.path.exists(cand):
            return cand
    return None

# Satellite colours shared by every time-series figure
SAT_COLORS = {'SNPP': '#f39c12', 'NOAA20': '#8e44ad', 'NOAA21': '#e74c3c'}

# Sensor colours for the Anomalies Count bar charts
SENSOR_COLORS = {
    'MODIS (AQUA/TERRA)': '#2f6fb5',
    'VIIRS (SNPP)': '#f39c12',
    'VIIRS (NOAA-20)': '#8e44ad',
    'VIIRS (NOAA-21)': '#e74c3c',
}

# Date colour ramp used for anomalies on the maps (oldest -> newest)
DATE_RAMP = ['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c']

DEFAULT_CONFIG = {
    'volcano': 'Volcano Name', 'lats_vent': 0.0, 'longs_vent': 0.0,
    'start_day_str': '01/01/2026 00:00', 'end_day_str': '01/05/2026 23:59',
    'filter_frp': 35, 'frp_filter_mode': 'gt', 'filter_track': 0.5,
    'map_key': 'INSERT_YOUR_MAP_KEY_HERE',
    # Optional layers are OFF for a new project. They only become useful
    # once the user has entered meaningful values for them.
    'include_reference_radius': False, 'ref_radius_m': 5000,
    'include_shapefile': False, 'shapefile_path': '',
    'include_reference_waypoint': False,
    'wpt_names': '', 'wpt_lats': '', 'wpt_lons': '', 'wpt_symbols': 'circle',
}


# ------------------------------------------------------------------
# Project folder
# ------------------------------------------------------------------
def get_active_folder():
    """
    Returns the relative folder path of the active project
    (e.g. 'projects/Wolf_2022' or 'examples/Fernandina'), or None.
    Accepts both the path-based active_volcano.txt and legacy bare names.
    """
    if not os.path.exists(ACTIVE_FILE):
        return None
    with open(ACTIVE_FILE, "r") as f:
        path = f.read().strip()
    if not path:
        return None
    if os.path.isdir(path):
        return path
    legacy = path.replace(" ", "_")
    if os.path.isdir(legacy):
        return legacy
    for base in (PROJECTS_DIR, EXAMPLES_DIR):
        cand = os.path.join(base, legacy)
        if os.path.isdir(cand):
            return cand
    return None


def set_active_folder(path):
    with open(ACTIVE_FILE, "w") as f:
        f.write(path)


def is_example_path(path):
    return bool(path) and os.path.normpath(path).split(os.sep)[0] == EXAMPLES_DIR


def config_path_for(folder):
    return os.path.join(folder, f"config_{os.path.basename(folder)}.txt")


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
def _coerce(v):
    if v.lower() == 'true':
        return True
    if v.lower() == 'false':
        return False
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


def load_global_config(with_defaults=True):
    """
    Reads the active project's config file. Values are coerced to
    bool/int/float where possible; wpt_* keys keep the raw string because
    they may hold ';'-separated lists.
    """
    config = dict(DEFAULT_CONFIG) if with_defaults else {}
    folder = get_active_folder()
    if not folder:
        return config
    cp = config_path_for(folder)
    if not os.path.exists(cp):
        return config
    with open(cp, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k.startswith('wpt_'):
                config[k] = v
            else:
                config[k] = _coerce(v)
    return config


def get_period(cfg=None):
    """Returns (start_dt, end_dt) as pandas Timestamps from the config."""
    cfg = cfg or load_global_config()
    start = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True, errors='coerce')
    end = pd.to_datetime(cfg.get('end_day_str'), dayfirst=True, errors='coerce')
    return start, end


def period_tag(cfg=None):
    """'YYYYMMDD_YYYYMMDD' tag used in output filenames."""
    s, e = get_period(cfg)
    fs = s.strftime('%Y%m%d') if not pd.isna(s) else 'start'
    fe = e.strftime('%Y%m%d') if not pd.isna(e) else 'end'
    return f"{fs}_{fe}"


def safe_name(name):
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', str(name)).strip('_') or 'Volcano'


# ------------------------------------------------------------------
# Waypoints
# ------------------------------------------------------------------
def parse_waypoints_from_config(c, keep_empty=False):
    """
    Parses ';'-separated waypoint lists from the config. Entries without
    coordinates (blank or exactly 0,0 placeholders) are dropped unless
    keep_empty=True (used by the Global Config editor so the user can
    still see and fill an empty row).
    """
    def _as_list(v):
        if v is None:
            return []
        if isinstance(v, str):
            return [x.strip() for x in v.split(';')]
        return [str(v)]

    names = _as_list(c.get('wpt_names', ''))
    lats = _as_list(c.get('wpt_lats', ''))
    lons = _as_list(c.get('wpt_lons', ''))
    syms = _as_list(c.get('wpt_symbols', 'circle'))

    n = max(len(names), len(lats), len(lons), len(syms))
    out = []
    for i in range(n):
        name = names[i] if i < len(names) else ''
        lat_raw = lats[i] if i < len(lats) else ''
        lon_raw = lons[i] if i < len(lons) else ''
        sym = (syms[i] if i < len(syms) else 'circle') or 'circle'
        lat = lon = None
        try:
            if str(lat_raw).strip() != '' and str(lon_raw).strip() != '':
                lat, lon = float(lat_raw), float(lon_raw)
        except ValueError:
            lat = lon = None
        valid = lat is not None and not (lat == 0.0 and lon == 0.0)
        if valid:
            out.append({'name': str(name).strip(), 'lat': lat, 'lon': lon, 'symbol': sym})
        elif keep_empty and (str(name).strip() or n == 1):
            out.append({'name': str(name).strip(), 'lat': None, 'lon': None, 'symbol': sym})
    return out


# ------------------------------------------------------------------
# Dates & data
# ------------------------------------------------------------------
def parse_firms_date(series):
    """
    Row-wise robust date parser for FIRMS CSVs. Strings starting with
    'YYYY-' are treated as ISO; anything else as DD/MM/YYYY.
    """
    s = series.astype(str).str.strip()
    parsed = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')
    iso = s.str.match(r'^\d{4}-\d{2}-\d{2}', na=False)
    if iso.any():
        parsed.loc[iso] = pd.to_datetime(s[iso], errors='coerce')
    rest = parsed.isna() & s.ne('') & s.ne('nan')
    if rest.any():
        parsed.loc[rest] = pd.to_datetime(s[rest], dayfirst=True, errors='coerce')
    return parsed


def read_csv_any(path):
    try:
        return pd.read_csv(path, encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding='latin-1')


def load_filtered_data(folder=None):
    """filter_VIIRS_combined.csv (output of the Mapper) with parsed dates."""
    folder = folder or get_active_folder()
    if not folder:
        return pd.DataFrame()
    fp = os.path.join(folder, "filter_VIIRS_combined.csv")
    if not os.path.exists(fp):
        return pd.DataFrame()
    df = read_csv_any(fp)
    df['date'] = parse_firms_date(df['date'])
    df = df.dropna(subset=['date']).sort_values('date').reset_index(drop=True)
    return df


def shapefile_path(cfg, folder):
    """Absolute/relative path of the configured shapefile or None."""
    if not (cfg.get('include_shapefile') and cfg.get('shapefile_path')):
        return None
    shp = str(cfg.get('shapefile_path'))
    if not shp.lower().endswith('.shp'):
        shp += '.shp'
    p = shp if os.path.isabs(shp) or not folder else os.path.join(folder, shp)
    return p if os.path.exists(p) else None


# ------------------------------------------------------------------
# Shapefiles (robust against broken PROJ installations)
# ------------------------------------------------------------------
_PROJ_STATE = {'checked': False, 'ok': False}


def _proj_works():
    try:
        from pyproj import CRS
        CRS.from_epsg(4326)
        return True
    except Exception:
        return False


def ensure_proj_data():
    """
    Makes sure PROJ can find a *working* proj.db.

    A stale PROJ_LIB / PROJ_DATA variable (QGIS, another conda environment,
    an old PROJ version, ...) makes pyproj fail with
    'proj_create: no database context specified'. Each candidate folder is
    activated and tested; the first one that really works is kept.
    Returns True if PROJ is usable.
    """
    if _PROJ_STATE['checked']:
        return _PROJ_STATE['ok']
    _PROJ_STATE['checked'] = True
    try:
        import pyproj
        import pyproj.datadir
    except ImportError:
        return False
    if _proj_works():
        _PROJ_STATE['ok'] = True
        return True

    prefix = sys.prefix
    cands = [os.path.join(prefix, 'share', 'proj'),                    # conda (macOS / Linux)
             os.path.join(prefix, 'Library', 'share', 'proj'),         # conda (Windows)
             os.path.join(os.path.dirname(pyproj.__file__), 'proj_dir', 'share', 'proj')]   # pip wheel
    for var in ('PROJ_DATA', 'PROJ_LIB'):
        if os.environ.get(var):
            cands.append(os.environ[var])
    try:
        cands.append(pyproj.datadir.get_data_dir())
    except Exception:
        pass
    for c in dict.fromkeys(cands):
        if not (c and os.path.exists(os.path.join(c, 'proj.db'))):
            continue
        os.environ['PROJ_DATA'] = c
        os.environ['PROJ_LIB'] = c
        try:
            pyproj.datadir.set_data_dir(c)
        except Exception:
            continue
        if _proj_works():
            print(f"[LavaFlow] PROJ database set to {c}")
            _PROJ_STATE['ok'] = True
            return True
    print("[LavaFlow] WARNING: PROJ database not usable; shapefiles are read without pyproj "
          "(WGS84 and UTM/WGS84 supported).")
    return False


def _utm_to_lonlat(x, y, zone, south):
    """Inverse UTM (WGS84) – pure Python fallback when PROJ is unavailable."""
    a, f, k0 = 6378137.0, 1 / 298.257223563, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x = x - 500000.0
    if south:
        y = y - 10000000.0
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
          + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
          + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    n1 = a / math.sqrt(1 - e2 * math.sin(p1) ** 2)
    t1 = math.tan(p1) ** 2
    c1 = ep2 * math.cos(p1) ** 2
    r1 = a * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = p1 - (n1 * math.tan(p1) / r1) * (
        d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(p1)
    return math.degrees(lon) + (zone - 1) * 6 - 180 + 3, math.degrees(lat)


def _read_geometries_raw(path):
    """Geometries of a shapefile WITHOUT touching pyproj (pyogrio raw reader,
    or a minimal pure-Python .shp parser as last resort)."""
    import shapely
    try:
        import pyogrio
        meta, _, geoms, _ = pyogrio.raw.read(path)
        return [shapely.from_wkb(g) for g in geoms if g is not None]
    except ImportError:
        return _read_shp_pure_python(path)


def _read_shp_pure_python(path):
    """Minimal reader for Point / PolyLine / Polygon (+Z/M) shapefiles."""
    import struct
    from shapely.geometry import Point, LineString, Polygon, MultiLineString, MultiPolygon, MultiPoint
    out = []
    with open(path, 'rb') as f:
        f.seek(100)
        while True:
            head = f.read(8)
            if len(head) < 8:
                break
            _, length = struct.unpack('>ii', head)
            rec = f.read(length * 2)
            stype = struct.unpack('<i', rec[:4])[0]
            if stype == 0:
                continue
            base = stype % 10
            if base == 1:                                     # point
                x, y = struct.unpack('<2d', rec[4:20])
                out.append(Point(x, y))
            elif base in (3, 5, 8):
                n_parts, n_pts = (struct.unpack('<2i', rec[36:44]) if base != 8
                                  else (0, struct.unpack('<i', rec[36:40])[0]))
                off = 44 if base != 8 else 40
                parts = list(struct.unpack(f'<{n_parts}i', rec[off:off + 4 * n_parts])) if n_parts else [0]
                off += 4 * n_parts
                pts = list(struct.unpack(f'<{2 * n_pts}d', rec[off:off + 16 * n_pts]))
                xy = list(zip(pts[0::2], pts[1::2]))
                if base == 8:
                    out.append(MultiPoint(xy))
                    continue
                rings = [xy[parts[i]:(parts[i + 1] if i + 1 < len(parts) else n_pts)] for i in range(len(parts))]
                if base == 3:
                    out.append(MultiLineString(rings) if len(rings) > 1 else LineString(rings[0]))
                else:
                    polys = [Polygon(r) for r in rings if len(r) >= 4]
                    out.append(MultiPolygon(polys) if len(polys) > 1 else polys[0])
    return out


def read_shapefile_lonlat(path):
    """
    Reads a shapefile and returns a GeoDataFrame in longitude/latitude (WGS84)
    with crs=None (so no library tries to reproject it again).

    1. if PROJ works: normal geopandas read + reprojection to EPSG:4326;
    2. otherwise (or if that fails): geometries are read without pyproj and the
       .prj is interpreted here — geographic WGS84 is used as it is and
       WGS84/UTM is converted with a built-in formula.
    """
    import geopandas as gpd
    if ensure_proj_data():
        try:
            gdf = gpd.read_file(path)
            if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            return gpd.GeoDataFrame(geometry=list(gdf.geometry), crs=None)
        except Exception as ex:
            print(f"[LavaFlow] geopandas/pyproj could not read {path} ({ex}); using the built-in reader")

    geoms = _read_geometries_raw(path)
    gdf = gpd.GeoDataFrame(geometry=geoms, crs=None)
    prj_file = os.path.splitext(path)[0] + '.prj'
    wkt = open(prj_file, encoding='utf-8', errors='ignore').read() if os.path.exists(prj_file) else ''
    up = wkt.upper().replace(' ', '')
    if not wkt:
        minx, miny, maxx, maxy = gdf.total_bounds
        if -180 <= minx <= 180 and -90 <= miny <= 90 and -180 <= maxx <= 180 and -90 <= maxy <= 90:
            return gdf                     # no .prj but values look like degrees
        raise RuntimeError("the shapefile has no .prj file and its coordinates are not in degrees")
    if up.startswith('GEOGCS') or up.startswith('GEOGCRS'):
        if 'WGS' in up and '84' in up:
            return gdf
        # other geographic datums (e.g. SIRGAS, PSAD56 without shift): difference < 1 km for mapping purposes
        return gdf
    m = re.search(r'UTM_?ZONE_?(\d{1,2})([NS])?', up.replace(' ', '_'))
    if m and ('WGS' in up or 'SIRGAS' in up):
        zone = int(m.group(1))
        south = (m.group(2) == 'S') or ('"FALSE_NORTHING",10000000' in up)
        from shapely.ops import transform
        gdf['geometry'] = [transform(lambda xx, yy, zz=None: _vec_utm(xx, yy, zone, south), g) for g in geoms]
        return gdf
    raise RuntimeError("PROJ is not available and this projection is not supported by the built-in reader. "
                       "Save the shapefile in WGS84 (EPSG:4326) or WGS84/UTM, or fix the PROJ installation "
                       "(conda install -c conda-forge --force-reinstall proj pyproj).")


def _vec_utm(xx, yy, zone, south):
    try:
        pts = [_utm_to_lonlat(a, b, zone, south) for a, b in zip(xx, yy)]
        return tuple(zip(*pts)) if pts else (xx, yy)
    except TypeError:
        return _utm_to_lonlat(xx, yy, zone, south)


def robust_stats(values):
    """mean / p95 / max of a numeric series (NaN-safe). Returns None if empty."""
    v = pd.Series(values).dropna()
    if v.empty:
        return None
    return {'n': int(v.size), 'mean': float(v.mean()),
            'p95': float(v.quantile(0.95)), 'max': float(v.max())}


def xrange_from_relayout(relayout, fallback=(None, None)):
    """
    Extracts the visible x-range from a Plotly relayoutData dict.
    Returns (start, end) as Timestamps, or the fallback on autorange/reset.
    """
    if not relayout:
        return fallback
    keys = list(relayout.keys())
    if any(k.endswith('autorange') and relayout[k] for k in keys):
        return fallback
    x0 = x1 = None
    for k in keys:
        if k.startswith('xaxis') and k.endswith('.range[0]'):
            x0 = relayout[k]
        elif k.startswith('xaxis') and k.endswith('.range[1]'):
            x1 = relayout[k]
        elif k.startswith('xaxis') and k.endswith('.range') and isinstance(relayout[k], (list, tuple)):
            x0, x1 = relayout[k][0], relayout[k][1]
    if x0 is None or x1 is None:
        return fallback
    try:
        return pd.to_datetime(x0), pd.to_datetime(x1)
    except Exception:
        return fallback


def stem_xy(dates, values):
    """x/y lists for vertical 'lollipop' stems (0 -> value) in ONE Plotly trace.
    Dates are passed as ISO strings so Plotly never receives raw datetime64 integers."""
    ds = pd.to_datetime(pd.Series(dates)).dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    vs = pd.Series(values).tolist()
    xs, ys = [], []
    for d, v in zip(ds, vs):
        xs += [d, d, None]
        ys += [0, v, None]
    return xs, ys


def slider_kwargs():
    """Hide the numeric input box that Dash >= 4 adds next to sliders (ignored on older Dash)."""
    from dash import dcc
    try:
        if 'allow_direct_input' in dcc.Slider(min=0, max=1).available_properties:
            return {'allow_direct_input': False}
    except Exception:
        pass
    return {}


def shapefile_geojson(path):
    """Shapefile -> plain GeoJSON dict (lon/lat, geometry only).
    Passing a dict (not a GeoDataFrame) stops folium from calling to_crs() itself."""
    import json
    from shapely.geometry import mapping
    gdf = read_shapefile_lonlat(path)
    feats = [{'type': 'Feature', 'properties': {}, 'geometry': mapping(g)}
             for g in gdf.geometry if g is not None and not g.is_empty]
    return json.loads(json.dumps({'type': 'FeatureCollection', 'features': feats}))


# ------------------------------------------------------------------
# Animation time steps (shared by the Propagation tab and the video)
# ------------------------------------------------------------------
SUBDAILY_MAX_DAYS = 14          # periods up to two weeks are animated every 12 h
SUBDAILY_STEP = pd.Timedelta(hours=12)


def animation_frames(start_dt, end_dt, max_frames=None):
    """
    Returns (frames, step): frames is a list of (t0, t1) windows covering the
    analysis period. Up to two weeks → 12-hour windows (FIRMS VIIRS gives a
    day and a night overpass); longer → daily windows (several days per
    window when max_frames would otherwise be exceeded).
    """
    s = pd.Timestamp(start_dt).normalize()
    e = pd.Timestamp(end_dt).normalize() + pd.Timedelta(days=1)       # exclusive end
    n_days = max(int((e - s).days), 1)
    if n_days <= SUBDAILY_MAX_DAYS:
        step = SUBDAILY_STEP
    else:
        k = 1 if not max_frames else max(1, int(math.ceil(n_days / max_frames)))
        step = pd.Timedelta(days=k)
    starts = pd.date_range(s, e - pd.Timedelta(seconds=1), freq=step)
    frames = [(t0, min(t0 + step, e)) for t0 in starts]
    return frames, step


def frame_label(t0, t1, step, times=None):
    """Human readable label of an animation window."""
    if step < pd.Timedelta(days=1):
        end_hm = '24:00' if (t1.normalize() > t0.normalize() and t1 == t1.normalize()) else t1.strftime('%H:%M')
        lbl = f"{t0.strftime('%d %b %Y')}  ·  {t0.strftime('%H:%M')}–{end_hm} UTC"
        if times is not None and len(times):
            passes = sorted({pd.Timestamp(t).strftime('%H:%M') for t in times})
            lbl += "  (overpasses " + ", ".join(passes[:4]) + ("…" if len(passes) > 4 else "") + ")"
        return lbl
    if step == pd.Timedelta(days=1):
        return t0.strftime('%d %b %Y')
    return f"{t0.strftime('%d %b %Y')} – {(t1 - pd.Timedelta(days=1)).strftime('%d %b %Y')}"
