"""
LavaFlow_video.py
=================
Renders the LavaFlow Propagation animation to an MP4 file.

Portrait layout (1080 x 1440 px):
  * top    : map (basemap tiles, anomalies, optional shapefile / radius /
             waypoints, vent, scale bar) with the extent chosen by the user
  * middle : current date + progress bar whose ticks adapt automatically to
             the analysed period (hours/days … years)
  * bottom : FRP and distance-to-vent time series growing with time

Only matplotlib, Pillow and requests are needed. The ffmpeg executable is
taken from the `imageio-ffmpeg` package when installed (works on Windows,
macOS and Linux without a system-wide ffmpeg), otherwise from the PATH.
If no ffmpeg is available an animated GIF is written instead.

Rendering runs in a background thread; the Dash callbacks poll `JOBS`.
"""
import hashlib
import io
import json
import math
import os
import shutil
import threading
import time
import uuid

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Rectangle
from matplotlib.lines import Line2D
import matplotlib.dates as mdates
from matplotlib import animation

import lavaflow_common as lfc

R_EARTH = 6378137.0
FIG_W, FIG_H, DPI = 10.8, 14.4, 100        # 1080 x 1440 px, portrait 3:4
OUT_FPS = 12                                # container frame rate
MAX_FRAMES = 900                            # longer periods advance >1 day per frame
PIXEL_RADIUS_M = 187.5                      # half of the 375 m VIIRS I-band pixel

BASEMAPS = {
    'esri': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    'topo': 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    'osm': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
}
ATTRIBUTION = {
    'arcgisonline': 'Basemap © Esri, Maxar, Earthstar Geographics',
    'opentopomap': 'Basemap © OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)',
    'openstreetmap': 'Basemap © OpenStreetMap contributors',
}

# Order in which basemaps are tried when the selected one cannot be downloaded
FALLBACK_ORDER = ['esri', 'topo', 'osm']
BASEMAP_NAMES = {'arcgisonline': 'Esri World Imagery', 'opentopomap': 'OpenTopoMap',
                 'openstreetmap': 'OpenStreetMap'}
TILE_HEADERS = {
    # Tile providers reject anonymous clients: identify the application and give a referer
    'User-Agent': 'Mozilla/5.0 (compatible; LavaFlowMapperSuite/2.0; '
                  '+https://github.com/Panch021/LavaFlow_Mapper_Suite)',
    'Referer': 'https://github.com/Panch021/LavaFlow_Mapper_Suite',
    'Accept': 'image/png,image/jpeg,image/*;q=0.9,*/*;q=0.5',
}


class RenderCancelled(Exception):
    pass


JOBS = {}
_JOBS_LOCK = threading.Lock()


# ------------------------------------------------------------------
# Projection & tiles
# ------------------------------------------------------------------
def merc(lat, lon):
    lat = np.clip(np.asarray(lat, dtype=float), -85, 85)
    x = R_EARTH * np.radians(np.asarray(lon, dtype=float))
    y = R_EARTH * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    return x, y


def _tile_xy(x, y, z):
    n = 2 ** z
    tx = (x + math.pi * R_EARTH) / (2 * math.pi * R_EARTH) * n
    ty = (math.pi * R_EARTH - y) / (2 * math.pi * R_EARTH) * n
    return tx, ty


def fetch_basemap(url_template, x0, x1, y0, y1, width_px, cache_dir=None, max_tiles=80, cancel_flag=None):
    """Downloads and stitches XYZ tiles. Returns (image_array, extent) or (None, None)."""
    try:
        import requests
        from PIL import Image
    except ImportError:
        return None, None
    if not url_template:
        return None, None
    world = 2 * math.pi * R_EARTH
    z = int(math.ceil(math.log2(world * width_px / (256 * max(x1 - x0, 1.0)))))
    max_z = 17 if 'opentopomap' in url_template else 18
    z = max(1, min(z, max_z))
    while True:
        tx0, ty0 = _tile_xy(x0, y1, z)
        tx1, ty1 = _tile_xy(x1, y0, z)
        ix0, ix1 = int(math.floor(tx0)), int(math.floor(tx1))
        iy0, iy1 = int(math.floor(ty0)), int(math.floor(ty1))
        if (ix1 - ix0 + 1) * (iy1 - iy0 + 1) <= max_tiles or z <= 1:
            break
        z -= 1
    n = 2 ** z
    headers = TILE_HEADERS
    session = requests.Session()
    mosaic = Image.new('RGB', ((ix1 - ix0 + 1) * 256, (iy1 - iy0 + 1) * 256), (230, 230, 230))
    ok = 0
    total = 0
    errors = []
    give_up = False
    for tx in range(ix0, ix1 + 1):
        if give_up:
            break
        for ty in range(iy0, iy1 + 1):
            if ty < 0 or ty >= n:
                continue
            if cancel_flag is not None and cancel_flag():
                raise RenderCancelled()
            total += 1
            url = url_template.replace('{s}', 'a').replace('{z}', str(z)) \
                .replace('{x}', str(tx % n)).replace('{y}', str(ty))
            data = None
            cpath = None
            if cache_dir:
                key = f"{hashlib.md5(url_template.encode()).hexdigest()[:10]}_{z}_{tx % n}_{ty}.png"
                cpath = os.path.join(cache_dir, key)
                if os.path.exists(cpath):
                    with open(cpath, 'rb') as fh:
                        data = fh.read()
            if data is None:
                try:
                    r = session.get(url, headers=headers, timeout=10)
                    if r.status_code == 200 and r.headers.get('content-type', 'image').startswith('image'):
                        data = r.content
                        if cpath:
                            os.makedirs(cache_dir, exist_ok=True)
                            with open(cpath, 'wb') as fh:
                                fh.write(data)
                except Exception as ex:
                    errors.append(str(ex)[:120])
                    data = None
                else:
                    if data is None:
                        errors.append(f"HTTP {r.status_code}")
            if data is None and ok == 0 and len(errors) >= 4:
                give_up = True
                break          # this provider is clearly unavailable: try the next one
            if data:
                try:
                    tile = Image.open(io.BytesIO(data)).convert('RGB')
                    mosaic.paste(tile, ((tx - ix0) * 256, (ty - iy0) * 256))
                    ok += 1
                except Exception:
                    pass
    if total and ok < 0.6 * total:
        print(f"[Video] basemap {basemap_name(url_template)}: {ok}/{total} tiles "
              f"({'; '.join(sorted(set(errors))[:3])})")
        return None, None
    res = world / (256 * n)            # metres per pixel
    tile_m = world / n                 # metres per tile
    left = ix0 * tile_m - math.pi * R_EARTH
    top = math.pi * R_EARTH - iy0 * tile_m
    extent = (left, left + mosaic.width * res, top - mosaic.height * res, top)
    return np.asarray(mosaic), extent


def basemap_name(url):
    for k, v in BASEMAP_NAMES.items():
        if url and k in url:
            return v
    return 'selected basemap' if url else 'basemap'


def fetch_basemap_with_fallback(url_template, x0, x1, y0, y1, width_px, cache_dir=None, cancel_flag=None):
    """Tries the selected basemap first, then the others. Returns (img, extent, url_used)."""
    tried = []
    for url in [url_template] + [BASEMAPS[k] for k in FALLBACK_ORDER]:
        if not url or url in tried:
            continue
        tried.append(url)
        img, ext = fetch_basemap(url, x0, x1, y0, y1, width_px, cache_dir=cache_dir, cancel_flag=cancel_flag)
        if img is not None:
            return img, ext, url
    return None, None, None


def attribution_for(url):
    for k, v in ATTRIBUTION.items():
        if url and k in url:
            return v
    return ''


def nice_scale_length(width_m):
    target = width_m / 5
    exp = 10 ** math.floor(math.log10(target))
    for m in (5, 2, 1):
        if m * exp <= target:
            return m * exp
    return exp


def find_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which('ffmpeg')


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------
def settings_path(folder):
    return os.path.join(folder, "animation_settings.json")


def save_settings(folder, settings):
    try:
        with open(settings_path(folder), 'w') as f:
            json.dump(settings, f, indent=1)
    except Exception:
        pass


def load_settings(folder):
    try:
        with open(settings_path(folder)) as f:
            return json.load(f)
    except Exception:
        return {}


def output_path(folder, cfg, ext='mp4'):
    return os.path.join(folder, f"{lfc.safe_name(cfg.get('volcano', 'Volcano'))}_{lfc.period_tag(cfg)}"
                                f"_propagation.{ext}")


def full_extent(df, cfg, layers):
    """[[south, west], [north, east]] covering anomalies, vent and enabled layers."""
    lat_v, lon_v = float(cfg.get('lats_vent', 0)), float(cfg.get('longs_vent', 0))
    lats = list(df['latitude']) + [lat_v] if not df.empty else [lat_v]
    lons = list(df['longitude']) + [lon_v] if not df.empty else [lon_v]
    if 'RAD' in layers and cfg.get('include_reference_radius'):
        r = float(cfg.get('ref_radius_m', 5000))
        dlat = r / 111000.0
        dlon = r / (111000.0 * max(math.cos(math.radians(lat_v)), 1e-6))
        lats += [lat_v - dlat, lat_v + dlat]
        lons += [lon_v - dlon, lon_v + dlon]
    if 'WPT' in layers and cfg.get('include_reference_waypoint'):
        for w in lfc.parse_waypoints_from_config(cfg):
            lats.append(w['lat'])
            lons.append(w['lon'])
    s, n, w_, e = min(lats), max(lats), min(lons), max(lons)
    pad_lat = max((n - s) * 0.06, 0.004)
    pad_lon = max((e - w_) * 0.06, 0.004)
    return [[s - pad_lat, w_ - pad_lon], [n + pad_lat, e + pad_lon]]


def normalise_bounds(b):
    """Accepts [[s,w],[n,e]] or a dict (leaflet LatLngBounds) and returns [[s,w],[n,e]] or None."""
    try:
        if isinstance(b, dict):
            sw = b.get('_southWest') or b.get('southWest')
            ne = b.get('_northEast') or b.get('northEast')
            return [[float(sw['lat']), float(sw['lng'])], [float(ne['lat']), float(ne['lng'])]]
        (s, w), (n, e) = b
        s, w, n, e = float(s), float(w), float(n), float(e)
        if n <= s or e <= w:
            return None
        return [[s, w], [n, e]]
    except Exception:
        return None


# ------------------------------------------------------------------
# Rendering
# ------------------------------------------------------------------
def render_video(folder, cfg, df, bounds, basemap_url, layers, speed, out_file, progress=None,
                 cancel_flag=None):
    """
    Renders the animation. `speed` is the value of the app's speed slider
    (1 = slow … 10 = fast), converted to the same delay used by the app.
    Returns the path of the written file.
    """
    def report(p, msg):
        if progress:
            progress(p, msg)

    def check_cancel():
        if cancel_flag is not None and cancel_flag():
            raise RenderCancelled()

    layers = layers or []
    start_dt, end_dt = lfc.get_period(cfg)
    start_day = start_dt.normalize()
    end_day = end_dt.normalize()
    # ≤ 2 weeks → 12-hour windows, otherwise daily (or multi-day for very long periods)
    frames, step = lfc.animation_frames(start_dt, end_dt, max_frames=MAX_FRAMES)
    subdaily = step < pd.Timedelta(days=1)
    delay_ms = 1100 - int(speed or 5) * 100
    in_fps = 1000.0 / delay_ms

    lat_v, lon_v = float(cfg.get('lats_vent', 0)), float(cfg.get('longs_vent', 0))
    df = df.sort_values('date').reset_index(drop=True)
    df['day'] = df['date'].dt.normalize()

    # ---------------- figure skeleton ----------------
    fig = Figure(figsize=(FIG_W, FIG_H), dpi=DPI, facecolor='white')
    ax_map = fig.add_axes([0.035, 0.425, 0.93, 0.525])
    ax_bar = fig.add_axes([0.09, 0.335, 0.87, 0.03])
    ax_frp = fig.add_axes([0.09, 0.19, 0.87, 0.115])
    ax_dst = fig.add_axes([0.09, 0.055, 0.87, 0.115], sharex=ax_frp)

    # map extent with the axes' aspect ratio (no distortion)
    b = normalise_bounds(bounds) or full_extent(df, cfg, layers)
    mx0, my0 = merc(b[0][0], b[0][1])
    mx1, my1 = merc(b[1][0], b[1][1])
    cx, cy = (mx0 + mx1) / 2, (my0 + my1) / 2
    box_w_px = FIG_W * DPI * 0.93
    box_h_px = FIG_H * DPI * 0.525
    aspect = box_w_px / box_h_px
    w, h = mx1 - mx0, my1 - my0
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2

    report(0.02, f"Downloading {basemap_name(basemap_url)} tiles…")
    img, ext, used_url = fetch_basemap_with_fallback(basemap_url, x0, x1, y0, y1, box_w_px,
                                                     cache_dir=os.path.join(folder, ".tile_cache"),
                                                     cancel_flag=cancel_flag)
    notes = []
    if img is not None:
        ax_map.imshow(img, extent=ext, interpolation='bilinear', zorder=0)
        if used_url != basemap_url:
            notes.append(f"{basemap_name(basemap_url)} could not be downloaded; "
                         f"{basemap_name(used_url)} was used instead")
        basemap_url = used_url
    else:
        ax_map.set_facecolor('#e8ecef')
        notes.append("no basemap could be downloaded (check the internet connection / firewall)")
        basemap_url = ''
    if progress:
        progress(0.04, "; ".join(notes) or "Basemap ready", notes=notes)
    check_cancel()
    ax_map.set_xlim(x0, x1)
    ax_map.set_ylim(y0, y1)
    ax_map.set_aspect('equal')
    ax_map.set_xticks([])
    ax_map.set_yticks([])
    for sp in ax_map.spines.values():
        sp.set_edgecolor('#555')

    coslat = max(math.cos(math.radians(lat_v)), 1e-6)
    ax_map.text(0.995, 0.004, attribution_for(basemap_url), transform=ax_map.transAxes, ha='right', va='bottom',
                fontsize=7, color='#333', bbox=dict(facecolor='white', alpha=0.7, lw=0, pad=1.5), zorder=20)

    # static layers
    if 'SHP' in layers:
        shp = lfc.shapefile_path(cfg, folder)
        if shp:
            try:
                from shapely.ops import transform as shp_transform
                gdf = lfc.read_shapefile_lonlat(shp)
                gdf['geometry'] = gdf.geometry.apply(
                    lambda g: shp_transform(lambda lon, lat, z=None: merc(lat, lon), g))
                geoms = gdf.geometry.boundary if gdf.geom_type.str.contains('Polygon').any() else gdf.geometry
                for g in geoms:
                    parts = getattr(g, 'geoms', [g])
                    for part in parts:
                        if part.is_empty:
                            continue
                        if part.geom_type == 'Point':
                            ax_map.plot(part.x, part.y, 'o', color='black', ms=5, zorder=7)
                        else:
                            xs, ys = part.xy
                            ax_map.plot(xs, ys, color='black', lw=1.6, zorder=7)
                ax_map.set_xlim(x0, x1)
                ax_map.set_ylim(y0, y1)
            except Exception as e:
                print(f"[Video] shapefile not drawn: {e}")
    vx, vy = merc(lat_v, lon_v)
    if 'RAD' in layers and cfg.get('include_reference_radius'):
        r_m = float(cfg.get('ref_radius_m', 5000)) / coslat
        ax_map.add_patch(Circle((vx, vy), r_m, fill=False, ls=(0, (5, 4)), lw=1.3, ec='black', zorder=4))
    if 'WPT' in layers and cfg.get('include_reference_waypoint'):
        mk = {'circle': 'o', 'triangle': '^', 'square': 's'}
        for wp in lfc.parse_waypoints_from_config(cfg):
            wx, wy = merc(wp['lat'], wp['lon'])
            ax_map.plot(wx, wy, marker=mk.get(wp['symbol'], 'o'), color='black', ms=9, zorder=8, ls='none')
            if wp['name']:
                ax_map.annotate(wp['name'], (wx, wy), xytext=(7, 4), textcoords='offset points', fontsize=10,
                                fontweight='bold', zorder=9,
                                bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#555', lw=0.6, alpha=0.9))
    ax_map.plot(vx, vy, marker='^', color='black', ms=13, mec='white', mew=1, zorder=9, ls='none')

    # scale bar (ground distance)
    ground_w = (x1 - x0) * coslat
    L = nice_scale_length(ground_w)
    bar_len = L / coslat
    sx0 = x0 + (x1 - x0) * 0.03
    sy0 = y0 + (y1 - y0) * 0.035
    ax_map.add_patch(Rectangle((sx0 - (x1 - x0) * 0.01, sy0 - (y1 - y0) * 0.015), bar_len + (x1 - x0) * 0.02,
                               (y1 - y0) * 0.06, fc='white', ec='none', alpha=0.8, zorder=10))
    ax_map.plot([sx0, sx0 + bar_len], [sy0, sy0], color='black', lw=3, zorder=11, solid_capstyle='butt')
    ax_map.text(sx0 + bar_len / 2, sy0 + (y1 - y0) * 0.01, f"{L / 1000:g} km" if L >= 1000 else f"{L:g} m",
                ha='center', va='bottom', fontsize=10, zorder=11)

    # anomaly scatter (size = real pixel footprint, min 3 px)
    px_per_m = box_w_px / (x1 - x0)
    r_px = max(PIXEL_RADIUS_M / coslat * px_per_m, 1.5)
    size_pt2 = (2 * r_px * 72 / DPI) ** 2
    ax_, ay_ = merc(df['latitude'].values, df['longitude'].values)
    xy_all = np.column_stack([ax_, ay_]) if len(df) else np.empty((0, 2))
    past_sc = ax_map.scatter([], [], s=size_pt2, c='#f39c12', alpha=0.55, linewidths=0, zorder=5)
    today_sc = ax_map.scatter([], [], s=size_pt2 * 1.3, c='#e74c3c', edgecolors='black', linewidths=0.6, zorder=6)
    ax_map.legend(handles=[Line2D([], [], marker='o', ls='none', color='#f39c12', label='Previous anomalies'),
                           Line2D([], [], marker='o', ls='none', color='#e74c3c', mec='black',
                                  label=('Anomalies of this 12 h window' if subdaily else
                                         'Anomalies of the day' if step == pd.Timedelta(days=1)
                                         else 'Anomalies of this step')),
                           Line2D([], [], marker='^', ls='none', color='black', label='Vent')],
                  loc='upper right', fontsize=9, framealpha=0.85)

    # title + date
    title = f"{cfg.get('volcano', '')} — thermal anomalies (FIRMS VIIRS)"
    fig.text(0.5, 0.993, title, ha='center', va='top', fontsize=15, fontweight='bold')
    fig.text(0.5, 0.975, f"{start_day.strftime('%d %b %Y')} – {end_day.strftime('%d %b %Y')}",
             ha='center', va='top', fontsize=13, color='#333')
    date_txt = fig.text(0.5 if not subdaily else 0.04, 0.405, '', ha='center' if not subdaily else 'left',
                        va='top', fontsize=18 if not subdaily else 14, fontweight='bold')
    count_txt = fig.text(0.96, 0.405, '', ha='right', va='top', fontsize=10, color='#555')

    # progress bar
    s_num, e_num = mdates.date2num(start_day), mdates.date2num(end_day + pd.Timedelta(days=1))
    ax_bar.set_xlim(s_num, e_num)
    ax_bar.set_ylim(-1, 1)
    ax_bar.plot([s_num, e_num], [0, 0], color='#d5d8dc', lw=6, solid_capstyle='round', zorder=1)
    prog_line, = ax_bar.plot([s_num, s_num], [0, 0], color='#6c3fb5', lw=6, solid_capstyle='round', zorder=2)
    prog_dot, = ax_bar.plot([s_num], [0], 'o', color='#6c3fb5', ms=12, mec='white', mew=2, zorder=3)
    loc = mdates.AutoDateLocator(minticks=4, maxticks=8)
    ax_bar.xaxis.set_major_locator(loc)
    ax_bar.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    ax_bar.tick_params(axis='x', labelsize=9, length=3, color='#999')
    ax_bar.set_yticks([])
    for k in ('left', 'right', 'top'):
        ax_bar.spines[k].set_visible(False)
    ax_bar.spines['bottom'].set_visible(False)
    ax_bar.xaxis.get_offset_text().set_fontsize(8)

    # time series
    ax_frp.set_xlim(s_num, e_num)
    frp_max = float(df['frp'].max()) if len(df) else 1.0
    dist_max = float(df['distance_km'].max()) if len(df) else 1.0
    rad_km = float(cfg.get('ref_radius_m', 5000)) / 1000.0
    show_rad = 'RAD' in layers and cfg.get('include_reference_radius')
    if show_rad:
        dist_max = max(dist_max, rad_km)
    ax_frp.set_ylim(0, frp_max * 1.08)
    ax_dst.set_ylim(0, dist_max * 1.12)
    ax_frp.set_ylabel('FRP (MW)', fontsize=10)
    ax_dst.set_ylabel('Distance (km)', fontsize=10)
    for a in (ax_frp, ax_dst):
        a.grid(True, color='#e5e7e9', lw=0.8)
        a.tick_params(labelsize=9)
        for k in ('top', 'right'):
            a.spines[k].set_visible(False)
    ax_frp.tick_params(labelbottom=False)
    loc2 = mdates.AutoDateLocator(minticks=4, maxticks=9)
    ax_dst.xaxis.set_major_locator(loc2)
    ax_dst.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc2))
    if subdaily:
        # one labelled tick per day, a minor tick at 12:00 UTC
        n_days = int(round(e_num - s_num))
        day_loc = mdates.DayLocator(interval=1 if n_days <= 8 else 2)
        for a in (ax_bar, ax_dst):
            a.xaxis.set_major_locator(day_loc)
            a.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
            a.xaxis.set_minor_locator(mdates.HourLocator(byhour=[12]))
            a.tick_params(axis='x', which='minor', length=3, color='#999')
        ax_dst.set_xlabel(f"Date (UTC) — {start_day.strftime('%Y')}", fontsize=9, color='#555')
    if show_rad:
        ax_dst.axhline(rad_km, color='black', ls='--', lw=1.2, zorder=1)
        ax_dst.text(s_num, rad_km, f" Ref. radius: {rad_km:.2f} km", va='bottom', ha='left', fontsize=8)

    sat_art = {}
    handles = []
    dnum_all = mdates.date2num(df['date']) if len(df) else np.array([])
    for sat, col in lfc.SAT_COLORS.items():
        m = (df['satellite'] == sat).values if len(df) else np.array([], bool)
        if not m.any():
            continue
        fsc = ax_frp.scatter([], [], s=22, c=col, edgecolors='black', linewidths=0.4, zorder=3)
        lc = LineCollection([], colors=col, linewidths=0.9, zorder=2)
        ax_dst.add_collection(lc)
        dsc = ax_dst.scatter([], [], s=12, c=col, zorder=3)
        sat_art[sat] = (m, fsc, lc, dsc)
        handles.append(Line2D([], [], marker='o', ls='none', color=col, mec='black', label=sat))
    ax_frp.legend(handles=handles, loc='upper right', ncol=len(handles), fontsize=9, framealpha=0.85)
    vl1 = ax_frp.axvline(s_num, color='#6c3fb5', lw=1, alpha=0.6)
    vl2 = ax_dst.axvline(s_num, color='#6c3fb5', lw=1, alpha=0.6)

    frp_vals = df['frp'].values if len(df) else np.array([])
    dst_vals = df['distance_km'].values if len(df) else np.array([])
    date_vals = df['date'].values if len(df) else np.array([], dtype='datetime64[ns]')

    def draw(t0, t1):
        vis = date_vals < t1.to_datetime64()
        today = (date_vals >= t0.to_datetime64()) & vis
        past = vis & ~today
        past_sc.set_offsets(xy_all[past] if past.any() else np.empty((0, 2)))
        today_sc.set_offsets(xy_all[today] if today.any() else np.empty((0, 2)))
        for sat, (m, fsc, lc, dsc) in sat_art.items():
            mm = m & vis
            xs, fr, ds = dnum_all[mm], frp_vals[mm], dst_vals[mm]
            fsc.set_offsets(np.column_stack([xs, fr]) if mm.any() else np.empty((0, 2)))
            dsc.set_offsets(np.column_stack([xs, ds]) if mm.any() else np.empty((0, 2)))
            lc.set_segments([[(x, 0), (x, d)] for x, d in zip(xs, ds)])
        dn = mdates.date2num(t1)
        prog_line.set_data([s_num, dn], [0, 0])
        prog_dot.set_data([dn], [0])
        vl1.set_xdata([dn, dn])
        vl2.set_xdata([dn, dn])
        date_txt.set_text(lfc.frame_label(t0, t1, step, date_vals[today] if subdaily else None))
        unit = "12 h" if subdaily else ("Day" if step == pd.Timedelta(days=1) else f"{step.days} days")
        count_txt.set_text(f"{unit}: {int(today.sum())}   Cumulative: {int(vis.sum())}")

    # ---------------- write ----------------
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        matplotlib.rcParams['animation.ffmpeg_path'] = ffmpeg
        writer = animation.FFMpegWriter(fps=in_fps, codec='libx264', bitrate=-1,
                                        extra_args=['-r', str(OUT_FPS), '-pix_fmt', 'yuv420p',
                                                    '-crf', '20', '-preset', 'medium',
                                                    '-movflags', '+faststart'])
    else:
        out_file = os.path.splitext(out_file)[0] + '.gif'
        writer = animation.PillowWriter(fps=in_fps)

    tmp_file = out_file + '.part' + os.path.splitext(out_file)[1]
    n = len(frames)
    try:
        with writer.saving(fig, tmp_file, dpi=DPI):
            for i, (t0, t1) in enumerate(frames):
                check_cancel()
                draw(t0, t1)
                writer.grab_frame()
                if i % 5 == 0 or i == n - 1:
                    report(0.05 + 0.93 * (i + 1) / n, f"Rendering frame {i + 1}/{n}")
    except BaseException:
        try:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        except OSError:
            pass
        raise
    os.replace(tmp_file, out_file)
    report(1.0, "Done")
    return out_file


# ------------------------------------------------------------------
# Background jobs
# ------------------------------------------------------------------
def start_job(folder, cfg, bounds, basemap_url, layers, speed):
    df = lfc.load_filtered_data(folder)
    if df.empty:
        return None, "No mapper results found. Run the LavaFlow Mapper first."
    with _JOBS_LOCK:
        if any(j['status'] == 'running' for j in JOBS.values()):
            return None, "A video is already being rendered. Please wait until it finishes."
        job_id = uuid.uuid4().hex[:8]
        JOBS[job_id] = {'status': 'running', 'progress': 0.0, 'message': 'Starting…', 'file': None,
                        'started': time.time(), 'cancel': False, 'notes': []}

    save_settings(folder, {'bounds': normalise_bounds(bounds), 'basemap_url': basemap_url,
                           'layers': list(layers or []), 'speed': speed})
    out = output_path(folder, cfg)

    def prog(p, msg, notes=None):
        JOBS[job_id].update(progress=p, message=msg)
        if notes:
            JOBS[job_id]['notes'] = list(notes)

    def run():
        try:
            f = render_video(folder, cfg, df, bounds, basemap_url, layers, speed, out, progress=prog,
                             cancel_flag=lambda: JOBS[job_id]['cancel'])
            msg = f"Saved: {f}  ({time.time() - JOBS[job_id]['started']:.0f} s)"
            if JOBS[job_id]['notes']:
                msg += "  —  Note: " + "; ".join(JOBS[job_id]['notes'])
            JOBS[job_id].update(status='done', file=f, progress=1.0, message=msg)
        except RenderCancelled:
            JOBS[job_id].update(status='cancelled', message="Rendering cancelled. No video was written.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            JOBS[job_id].update(status='error', message=f"Rendering failed: {e}")

    threading.Thread(target=run, daemon=True).start()
    return job_id, "Rendering started…"


def cancel_job(job_id):
    job = JOBS.get(job_id)
    if job and job['status'] == 'running':
        job['cancel'] = True
        job['message'] = 'Cancelling…'
        return True
    return False


def job_status(job_id):
    return JOBS.get(job_id)
