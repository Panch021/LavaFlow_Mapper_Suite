"""
LavaFlow_mapper.py
==================
Filters the FIRMS VIIRS detections of the active project, computes the
distance of each anomaly to the vent, saves the results
(filter_VIIRS_combined.csv, max_distance_per_day_VIIRS.csv) and shows:

  * an interactive folium map (anomalies coloured by date),
  * FRP and distance time series whose mean / P95 / max statistics are
    recomputed for the time window currently visible on screen
    (zoom, pan or reset).

The figure and map builders are reused by Export_report.py so the HTML
report is identical to what the user sees in the app.
"""
import glob
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
import branca.colormap as bcm
from dash import html, dcc, Input, Output, no_update

try:
    from folium.plugins import RegularPolygonMarker
except ImportError:
    from folium.features import RegularPolygonMarker

import lavaflow_common as lfc

get_active_folder = lfc.get_active_folder
load_global_config = lfc.load_global_config
parse_waypoints_from_config = lfc.parse_waypoints_from_config


# ==========================================
# 1. DATA ENGINE
# ==========================================
def load_and_tag_data(folder=None):
    """Reads the VIIRS CSV files of the project folder."""
    folder = folder or get_active_folder()
    if not folder:
        return pd.DataFrame()
    name = os.path.basename(folder)
    sats = [(f"*SNPP*{name}.csv", "SNPP", 1), (f"*NOAA20*{name}.csv", "NOAA20", 2),
            (f"*NOAA21*{name}.csv", "NOAA21", 3)]
    frames = []
    for pattern, sat, sid in sats:
        for f in glob.glob(os.path.join(folder, pattern)):
            try:
                df = lfc.read_csv_any(f)
                for col in ['latitude', 'longitude', 'frp', 'track']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                day = lfc.parse_firms_date(df['acq_date'])
                t = df['acq_time'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(4).str[-4:]
                df['date'] = day + pd.to_timedelta(t.str[:2].astype(int), unit='h') \
                    + pd.to_timedelta(t.str[2:].astype(int), unit='m')
                df = df.dropna(subset=['date', 'latitude', 'longitude'])
                df['satellite'], df['source'] = sat, sid
                frames.append(df)
            except Exception as e:
                print(f"[Mapper] could not read {f}: {e}")
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(subset=['latitude', 'longitude', 'date', 'satellite'])


def haversine_km(lat0, lon0, lats, lons):
    p = np.pi / 180
    a = (np.sin((lats * p - lat0 * p) / 2) ** 2
         + np.cos(lat0 * p) * np.cos(lats * p) * np.sin((lons * p - lon0 * p) / 2) ** 2)
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def run_filter(cfg, folder):
    """Applies the FRP/track/date filters and writes the output CSVs."""
    comb = load_and_tag_data(folder)
    if comb.empty:
        return comb
    start_dt, end_dt = lfc.get_period(cfg)
    thr = float(cfg.get('filter_frp', 0) or 0)
    frp_mask = comb['frp'] >= thr if cfg.get('frp_filter_mode', 'gt') == 'gt' else comb['frp'] <= thr
    filtered = comb[(comb['track'] <= float(cfg.get('filter_track', 1.0) or 1.0)) & frp_mask &
                    (comb['date'] >= start_dt) & (comb['date'] <= end_dt)].sort_values('date').copy()
    if filtered.empty:
        return filtered
    filtered['distance_km'] = haversine_km(float(cfg.get('lats_vent', 0)), float(cfg.get('longs_vent', 0)),
                                           filtered['latitude'].values, filtered['longitude'].values)
    filtered.to_csv(os.path.join(folder, "filter_VIIRS_combined.csv"), index=False)

    daily = filtered.copy()
    daily['date_only'] = daily['date'].dt.date
    # keep the coordinates of the farthest anomaly of each day (not just the first row)
    idx = daily.groupby(['date_only', 'satellite'])['distance_km'].idxmax()
    summary = daily.loc[idx, ['date_only', 'satellite', 'distance_km', 'latitude', 'longitude', 'source']]
    summary = summary.merge(daily.groupby(['date_only', 'satellite'])['frp'].max().reset_index(),
                            on=['date_only', 'satellite'])
    summary = summary[['date_only', 'satellite', 'distance_km', 'frp', 'latitude', 'longitude', 'source']]
    summary.sort_values(['date_only', 'satellite']).to_csv(
        os.path.join(folder, "max_distance_per_day_VIIRS.csv"), index=False)
    return filtered


# ==========================================
# 2. MAP HELPERS (shared with the export)
# ==========================================
def build_vertical_colorbar(start_dt, end_dt, n_ticks=6):
    """Vertical date colour bar (newest on top) matching the anomaly colours."""
    gradient = ", ".join(lfc.DATE_RAMP)
    total = (end_dt - start_dt).total_seconds()
    ticks = [start_dt + pd.Timedelta(seconds=total * i / (n_ticks - 1)) for i in range(n_ticks)]
    labels = "".join(
        f'<div style="font-size:11px;color:#333;white-space:nowrap;line-height:1;">{d.strftime("%d/%m/%Y")}</div>'
        for d in reversed(ticks))
    return f"""
    <div style="position:absolute;bottom:70px;left:10px;z-index:9999;display:flex;
                height:170px;pointer-events:none;background:rgba(255,255,255,0.9);
                padding:6px 8px;border-radius:5px;box-shadow:0 1px 4px rgba(0,0,0,0.2);">
        <div style="width:14px;height:100%;background:linear-gradient(to top, {gradient});
                    border:1px solid #aaa;border-radius:3px;margin-right:6px;"></div>
        <div style="display:flex;flex-direction:column;justify-content:space-between;height:100%;">{labels}</div>
    </div>"""


def build_lock_zoom_script():
    """Adds a 'lock / unlock scroll zoom' button to the folium map (top-left, under +/-)."""
    return """
    <script>
    (function() {
        function attach() {
            var key = Object.keys(window).find(function(k) {
                return k.startsWith('map_') && window[k] && window[k]._container; });
            if (!key) { setTimeout(attach, 150); return; }
            var m = window[key];
            var Ctl = L.Control.extend({
                options: { position: 'topleft' },
                onAdd: function(map) {
                    var b = L.DomUtil.create('button', 'leaflet-bar');
                    b.style.cssText = 'padding:4px 8px;background:white;border:1px solid #bbb;' +
                                      'border-radius:4px;cursor:pointer;font-size:12px;';
                    var locked = true;
                    function apply() {
                        ['scrollWheelZoom','doubleClickZoom','touchZoom','boxZoom'].forEach(function(h){
                            locked ? map[h].disable() : map[h].enable(); });
                        b.innerHTML = locked ? '&#128274; Scroll zoom off' : '&#128275; Scroll zoom on';
                    }
                    apply();
                    L.DomEvent.disableClickPropagation(b);
                    L.DomEvent.on(b, 'click', function() { locked = !locked; apply(); });
                    return b;
                }
            });
            m.addControl(new Ctl());
        }
        if (document.readyState === 'complete') attach(); else window.addEventListener('load', attach);
    })();
    </script>"""


def build_basemap_fallback_script(map_var, topo_var, esri_var):
    """If OpenTopoMap tiles fail (and none loaded), switch to Esri imagery and say so."""
    return f"""
    <script>
    (function() {{
        function attach() {{
            var m = window['{map_var}'], topo = window['{topo_var}'], esri = window['{esri_var}'];
            if (!m || !topo || !esri) {{ setTimeout(attach, 150); return; }}
            var ok = 0, err = 0, switched = false;
            function fallback() {{
                if (switched || ok > 0) return;
                switched = true;
                m.removeLayer(topo);
                esri.addTo(m);
                var note = L.control({{position: 'bottomright'}});
                note.onAdd = function() {{
                    var d = L.DomUtil.create('div');
                    d.style.cssText = 'background:rgba(255,255,255,0.9);padding:3px 8px;border-radius:4px;' +
                                      'font-size:11px;color:#555;margin-bottom:18px;';
                    d.innerHTML = 'OpenTopoMap unavailable here &rarr; Esri imagery shown';
                    return d;
                }};
                note.addTo(m);
            }}
            function loadedTiles() {{
                var n = 0;
                for (var k in (topo._tiles || {{}})) {{
                    var el = topo._tiles[k].el;
                    if (el && el.complete && el.naturalWidth > 0) n++;
                }}
                return n;
            }}
            topo.on('tileload', function() {{ ok++; }});
            topo.on('tileerror', function() {{ err++; if (err >= 3 && loadedTiles() === 0) fallback(); }});
            // check repeatedly: errors may have happened before this script started listening
            var tries = 0;
            (function check() {{
                if (switched || !m.hasLayer(topo)) return;
                ok = Math.max(ok, loadedTiles());
                if (ok > 0) return;
                if (++tries >= 12) {{ fallback(); return; }}      // ~6 s without a single tile
                setTimeout(check, 500);
            }})();
        }}
        attach();
    }})();
    </script>"""


def build_refit_script(bounds):
    """Re-fits the map once the (i)frame has its final size. Inside a lazily laid-out
    iframe the initial fitBounds runs on a 0-px map and ends at the wrong zoom."""
    return f"""
    <script>
    (function() {{
        var B = {bounds};
        function refit() {{
            var key = Object.keys(window).find(function(k) {{
                return k.startsWith('map_') && window[k] && window[k]._container; }});
            if (!key) {{ setTimeout(refit, 150); return; }}
            var m = window[key];
            if (!m._container.clientHeight) {{ setTimeout(refit, 200); return; }}
            m.invalidateSize();
            m.fitBounds(B, {{padding: [20, 20]}});
        }}
        if (document.readyState === 'complete') refit(); else window.addEventListener('load', refit);
        var t; window.addEventListener('resize', function() {{
            clearTimeout(t); t = setTimeout(function() {{
                var key = Object.keys(window).find(function(k) {{ return k.startsWith('map_') && window[k] && window[k]._container; }});
                if (key) window[key].invalidateSize(); }}, 200); }});
    }})();
    </script>"""


MAP_CSS = """
<style>
  .leaflet-control-scale { margin-bottom: 20px !important; }
  .leaflet-tooltip.wpt-label { background: rgba(255,255,255,0.95); border: 1px solid #555;
      border-radius: 4px; padding: 1px 6px; font-size: 11px; font-weight: bold; color: #2c3e50; }
</style>"""


def add_waypoint_marker(feature_group, lat, lon, name, symbol, permanent_label=False):
    tooltip = folium.Tooltip(name or "Waypoint", permanent=bool(permanent_label and name),
                             direction='right', offset=(8, 0), class_name='wpt-label')
    kw = dict(color='black', fill=True, fill_color='black', fill_opacity=1.0, tooltip=tooltip)
    if symbol == "triangle":
        RegularPolygonMarker([lat, lon], number_of_sides=3, radius=9, rotation=30, **kw).add_to(feature_group)
    elif symbol == "square":
        RegularPolygonMarker([lat, lon], number_of_sides=4, radius=7, rotation=45, **kw).add_to(feature_group)
    else:
        folium.CircleMarker([lat, lon], radius=6, **kw).add_to(feature_group)


def build_folium_map(folder, cfg, df, labels=False, fit='all', default_basemap='esri'):
    """
    Folium map of the filtered anomalies. Returns (html, warning).
    The map is fitted to anomalies + vent (+ radius / waypoints only when
    those layers are enabled and valid), so it never drifts to (0, 0).
    """
    lat_v, lon_v = float(cfg.get('lats_vent', 0)), float(cfg.get('longs_vent', 0))
    start_dt, end_dt = lfc.get_period(cfg)
    if pd.isna(start_dt):
        start_dt = df['date'].min()
    if pd.isna(end_dt):
        end_dt = df['date'].max()

    m = folium.Map(location=[lat_v, lon_v], zoom_start=13, control_scale=True, tiles=None)
    m.get_root().header.add_child(folium.Element(MAP_CSS))
    # Esri imagery is the visible default: OSM/OpenTopoMap refuse tile requests that come from a
    # local HTML file (no HTTP referer), which left the exported map blank.
    # default_basemap='topo' shows OpenTopoMap first; if its tiles fail to load (some tile servers
    # refuse requests coming from a local HTML file) the map switches to Esri automatically.
    topo_first = default_basemap == 'topo'
    tl_esri = folium.TileLayer('Esri World Imagery', name='Esri World Imagery', show=not topo_first)
    tl_topo = folium.TileLayer('OpenTopoMap', name='OpenTopoMap', show=topo_first)
    tl_osm = folium.TileLayer('OpenStreetMap', name='OpenStreetMap', show=False)
    for tl in (tl_topo, tl_esri, tl_osm) if topo_first else (tl_esri, tl_topo, tl_osm):
        tl.add_to(m)

    cmap = bcm.LinearColormap(colors=lfc.DATE_RAMP, vmin=start_dt.timestamp(),
                              vmax=max(end_dt.timestamp(), start_dt.timestamp() + 1))
    m.get_root().html.add_child(folium.Element(build_vertical_colorbar(start_dt, end_dt)))

    fg = folium.FeatureGroup(name="Thermal anomalies")
    for r in df.itertuples():
        folium.Circle(location=[r.latitude, r.longitude], radius=187.5,
                      color=cmap(r.date.timestamp()), weight=1, fill=True, fill_opacity=0.7,
                      popup=f"{r.date.strftime('%Y-%m-%d %H:%M')} UTC<br>{r.satellite}<br>"
                            f"FRP: {r.frp} MW<br>Distance: {r.distance_km:.2f} km").add_to(fg)
    fg.add_to(m)

    warning = None
    if cfg.get('include_shapefile') and cfg.get('shapefile_path'):
        shp = lfc.shapefile_path(cfg, folder)
        if not shp:
            warning = f"Shapefile not found: {cfg.get('shapefile_path')} (expected inside {folder})"
        else:
            try:
                gj = lfc.shapefile_geojson(shp)
                folium.GeoJson(gj, name="Shapefile",
                               style_function=lambda x: {'color': 'black', 'weight': 2, 'fill': False}).add_to(m)
            except Exception as e:
                warning = f"Error loading shapefile: {e}"

    lats = list(df['latitude'].values) + [lat_v]
    lons = list(df['longitude'].values) + [lon_v]
    anom_lats, anom_lons = list(lats), list(lons)

    if cfg.get('include_reference_radius'):
        rad = float(cfg.get('ref_radius_m', 5000))
        fg_r = folium.FeatureGroup(name='Reference radius')
        folium.Circle(location=[lat_v, lon_v], radius=rad, color='black', weight=1.5,
                      fill=False, dash_array='6,6').add_to(fg_r)
        fg_r.add_to(m)
        dlat = rad / 111000.0
        dlon = rad / (111000.0 * max(np.cos(np.radians(lat_v)), 1e-6))
        lats += [lat_v - dlat, lat_v + dlat]
        lons += [lon_v - dlon, lon_v + dlon]

    wpts = parse_waypoints_from_config(cfg) if cfg.get('include_reference_waypoint') else []
    if wpts:
        fg_w = folium.FeatureGroup(name="Waypoints")
        for w in wpts:
            add_waypoint_marker(fg_w, w['lat'], w['lon'], w['name'], w['symbol'], permanent_label=labels)
            lats.append(w['lat'])
            lons.append(w['lon'])
        fg_w.add_to(m)

    folium.Marker([lat_v, lon_v], tooltip="Vent", icon=folium.DivIcon(
        html='<div style="width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;'
             'border-bottom:18px solid black;transform:translate(-50%,-50%);"></div>')).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)

    if fit == 'anomalies':            # export: zoom to the anomalies (and the vent) only
        lats, lons = anom_lats, anom_lons
    s, n, w_, e = min(lats), max(lats), min(lons), max(lons)
    if n - s < 0.01:
        s, n = s - 0.005, n + 0.005
    if e - w_ < 0.01:
        w_, e = w_ - 0.005, e + 0.005
    bounds = [[s, w_], [n, e]]
    m.fit_bounds(bounds, padding=(20, 20))
    m.get_root().html.add_child(folium.Element(build_lock_zoom_script()))
    m.get_root().html.add_child(folium.Element(build_refit_script(bounds)))
    if topo_first:
        m.get_root().html.add_child(folium.Element(
            build_basemap_fallback_script(m.get_name(), tl_topo.get_name(), tl_esri.get_name())))
    return m.get_root().render(), warning


# ==========================================
# 3. TIME SERIES (shared with the export)
# ==========================================
def compute_ts_stats(df, x0=None, x1=None):
    """mean / P95 / max of FRP and distance inside [x0, x1]."""
    d = df
    if x0 is not None and not pd.isna(x0):
        d = d[d['date'] >= pd.Timestamp(x0)]
    if x1 is not None and not pd.isna(x1):
        d = d[d['date'] <= pd.Timestamp(x1)]
    return {'n': int(len(d)),
            'frp': lfc.robust_stats(d['frp']) if len(d) else None,
            'dist': lfc.robust_stats(d['distance_km']) if len(d) else None,
            'x0': x0, 'x1': x1}


def build_ts_stats_panel(st):
    def fmt(x0):
        return pd.Timestamp(x0).strftime('%d/%m/%Y %H:%M') if x0 is not None and not pd.isna(x0) else '–'

    def tiles(title, s, unit, dec):
        if not s:
            return html.Div([html.Div(title, className='lf-stat-group-title'),
                             html.Div("no data in view", className='lf-muted')], className='lf-col')
        return html.Div([
            html.Div(title, className='lf-stat-group-title'),
            html.Div([
                html.Div([html.Div("Mean", className='k'), html.Div(f"{s['mean']:.{dec}f} {unit}", className='v')],
                         className='lf-stat'),
                html.Div([html.Div("P95", className='k'), html.Div(f"{s['p95']:.{dec}f} {unit}", className='v')],
                         className='lf-stat accent'),
                html.Div([html.Div("Max", className='k'), html.Div(f"{s['max']:.{dec}f} {unit}", className='v')],
                         className='lf-stat alert'),
            ], className='lf-stats', style={'margin': '0'}),
        ], className='lf-col')

    return html.Div([
        html.Div([
            html.Span("Statistics for the visible window: ", style={'fontWeight': '600'}),
            html.Span(f"{fmt(st['x0'])} → {fmt(st['x1'])} · {st['n']} anomalies", className='lf-muted'),
            html.Span("  (zoom or pan the chart to update; double-click to reset)", className='lf-muted'),
        ]),
        html.Div([tiles("FRP", st['frp'], "MW", 1), tiles("Distance to vent", st['dist'], "km", 2)],
                 className='lf-row', style={'marginTop': '6px'}),
    ])


def build_timeseries_figure(df, cfg, title=True):
    """FRP (top) and distance-to-vent stems (bottom), one colour per satellite."""
    start_dt, end_dt = lfc.get_period(cfg)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.07)

    for sat, color in lfc.SAT_COLORS.items():
        d = df[df['satellite'] == sat]
        if d.empty:
            continue
        fig.add_trace(go.Scattergl(
            x=d['date'], y=d['frp'], mode='markers', name=sat, legendgroup=sat,
            marker=dict(color=color, size=7, line=dict(width=0.6, color='black')),
            hovertemplate="%{x|%d/%m/%Y %H:%M}<br>FRP: %{y:.1f} MW<extra>" + sat + "</extra>"), row=1, col=1)
        sx, sy = lfc.stem_xy(d['date'], d['distance_km'])
        fig.add_trace(go.Scatter(x=sx, y=sy, mode='lines', line=dict(color=color, width=1),
                                 legendgroup=sat, showlegend=False, hoverinfo='skip'), row=2, col=1)
        fig.add_trace(go.Scattergl(
            x=d['date'], y=d['distance_km'], mode='markers', legendgroup=sat, showlegend=False,
            marker=dict(color=color, size=5),
            hovertemplate="%{x|%d/%m/%Y %H:%M}<br>Distance: %{y:.2f} km<extra>" + sat + "</extra>"), row=2, col=1)

    menus = []
    if cfg.get('include_reference_radius') and not pd.isna(start_dt):
        rk = float(cfg.get('ref_radius_m', 5000)) / 1000.0
        fig.add_trace(go.Scatter(
            x=[start_dt, end_dt], y=[rk, rk], mode='lines', name=f"Ref. radius ({rk:.2f} km)",
            line=dict(color='black', width=1.5, dash='dash'), meta='ref_radius',
            hovertemplate=f"Ref. radius: {rk:.2f} km<extra></extra>"), row=2, col=1)
        idx = len(fig.data) - 1
        menus = [dict(type='buttons', direction='right', x=1.0, xanchor='right', y=1.02, yanchor='bottom',
                      showactive=True, active=0, pad=dict(r=2, t=2, b=2, l=2), font=dict(size=11),
                      bgcolor='white', bordercolor='#cfd4da',
                      buttons=[dict(label='Radius on', method='restyle', args=[{'visible': True}, [idx]]),
                               dict(label='Radius off', method='restyle', args=[{'visible': False}, [idx]])])]

    s_lbl = start_dt.strftime('%d/%m/%Y') if not pd.isna(start_dt) else ''
    e_lbl = end_dt.strftime('%d/%m/%Y') if not pd.isna(end_dt) else ''
    fig.update_layout(
        title=dict(text=f"FIRMS thermal anomalies — {cfg.get('volcano', '')}<br><sup>{s_lbl} – {e_lbl}</sup>",
                   x=0.5, font=dict(size=17)) if title else None,
        template="plotly_white", autosize=True, margin=dict(t=80 if title else 40, b=40, l=65, r=20),
        legend=dict(orientation="h", yanchor="top", y=-0.07, xanchor="left", x=0),
        updatemenus=menus, uirevision='mapper-ts',
    )
    if not pd.isna(start_dt) and not pd.isna(end_dt):
        fig.update_xaxes(range=[start_dt, end_dt])
    fig.update_yaxes(title_text="FRP (MW)", row=1, col=1, rangemode='tozero')
    fig.update_yaxes(title_text="Distance to vent (km)", row=2, col=1, rangemode='tozero')
    return fig


# ==========================================
# 4. DASH LAYOUT
# ==========================================
def get_layout():
    cfg = load_global_config()
    folder = get_active_folder()
    if not folder:
        return html.Div("No active project found. Please configure a volcano first.", className='lf-msg lf-msg-warn')
    volcano = cfg.get('volcano', 'Volcano')

    filtered = run_filter(cfg, folder)
    if filtered.empty:
        return html.Div(f"No anomalies found for the current filters and period in '{folder}'.",
                        className='lf-msg lf-msg-warn')

    map_html, warning = build_folium_map(folder, cfg, filtered, default_basemap='topo')
    fig = build_timeseries_figure(filtered, cfg)
    s, e = lfc.get_period(cfg)
    stats = compute_ts_stats(filtered, s, e)

    children = []
    if warning:
        children.append(html.Div(warning, className='lf-msg lf-msg-warn'))
    children += [
        html.Div([
            html.Iframe(srcDoc=map_html, className='lf-map-frame',
                        style={'height': 'clamp(380px, 62vh, 760px)'}),
        ], className='lf-card', style={'padding': '6px'}),
        html.Div([
            html.Div(id='mapper-ts-stats', children=build_ts_stats_panel(stats)),
            dcc.Graph(id='mapper-ts-graph', figure=fig, className='lf-graph',
                      style={'height': 'clamp(520px, 75vh, 900px)'},
                      config={'responsive': True, 'displaylogo': False,
                              'toImageButtonOptions': {'format': 'png', 'filename': f'{lfc.safe_name(volcano)}_timeseries',
                                                       'height': 900, 'width': 1200, 'scale': 3}}),
        ], className='lf-card'),
    ]
    return html.Div(children)


# ==========================================
# 5. CALLBACKS
# ==========================================
_CACHE = {'key': None, 'df': None}


def _cached_filtered():
    folder = get_active_folder()
    if not folder:
        return pd.DataFrame()
    fp = os.path.join(folder, "filter_VIIRS_combined.csv")
    if not os.path.exists(fp):
        return pd.DataFrame()
    key = (fp, os.path.getmtime(fp))
    if _CACHE['key'] != key:
        _CACHE['key'], _CACHE['df'] = key, lfc.load_filtered_data(folder)
    return _CACHE['df']


def register_callbacks(app):
    @app.callback(
        Output('mapper-ts-stats', 'children'),
        Input('mapper-ts-graph', 'relayoutData'),
        prevent_initial_call=True
    )
    def update_ts_stats(relayout):
        df = _cached_filtered()
        if df.empty:
            return no_update
        s, e = lfc.get_period()
        x0, x1 = lfc.xrange_from_relayout(relayout, fallback=(None, None))
        if x0 is None and relayout and not any(k.endswith('autorange') for k in relayout):
            return no_update          # e.g. legend click / y-zoom only
        if x0 is None:
            x0, x1 = s, e
        return build_ts_stats_panel(compute_ts_stats(df, x0, x1))


if __name__ == "__main__":
    from dash import Dash
    app = Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True, port=8070)
