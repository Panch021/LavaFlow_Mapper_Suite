"""
LavaFlow_animation.py
=====================
Interactive day-by-day playback of the filtered thermal anomalies and
a RENDER button that saves the same animation as a portrait MP4
(map on top, date bar, FRP/distance series below). The video uses the
current map view (or the full anomaly extent), the selected basemap,
the layer toggles and the playback speed chosen in this tab.
"""
import os
import urllib.parse

import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_leaflet as dl
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import lavaflow_common as lfc
import LavaFlow_video as video

get_active_folder = lfc.get_active_folder
load_global_config = lfc.load_global_config
parse_waypoints_from_config = lfc.parse_waypoints_from_config
sat_colors = lfc.SAT_COLORS

BASEMAP_OPTIONS = [
    {'label': 'Esri World Imagery', 'value': video.BASEMAPS['esri']},
    {'label': 'OpenTopoMap', 'value': video.BASEMAPS['topo']},
    {'label': 'OpenStreetMap', 'value': video.BASEMAPS['osm']},
]


def get_config_dates():
    s, e = lfc.get_period()
    if pd.isna(s) or pd.isna(e):
        today = pd.Timestamp.now().normalize()
        return today.date(), today.date()
    return s.date(), e.date()


_CACHE = {'key': None, 'df': None}


def load_data():
    """filter_VIIRS_combined.csv of the active project (cached by mtime)."""
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


# ------------------------------------------------------------------
# Waypoint icons (black shapes, same identity as the folium map)
# ------------------------------------------------------------------
WPT_SVGS = {
    'circle': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">'
              '<circle cx="7" cy="7" r="6" fill="black"/></svg>',
    'triangle': '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">'
                '<polygon points="9,1 17,16 1,16" fill="black"/></svg>',
    'square': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">'
              '<rect x="1" y="1" width="12" height="12" fill="black"/></svg>',
}


def waypoint_icon(symbol):
    sym = symbol if symbol in WPT_SVGS else 'circle'
    size = 18 if sym == 'triangle' else 14
    return {"iconUrl": "data:image/svg+xml;utf8," + urllib.parse.quote(WPT_SVGS[sym]),
            "iconSize": [size, size], "iconAnchor": [size // 2, size // 2]}


VENT_ICON = {"iconUrl": "data:image/svg+xml;utf8," + urllib.parse.quote(
    '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="20" viewBox="0 0 22 20">'
    '<polygon points="11,1 21,19 1,19" fill="black" stroke="white" stroke-width="1.5"/></svg>'),
    "iconSize": [22, 20], "iconAnchor": [11, 12]}


def get_frames():
    """Animation windows for the active period: 12 h up to two weeks, daily otherwise."""
    s, e = lfc.get_period()
    if pd.isna(s) or pd.isna(e):
        s = e = pd.Timestamp.now().normalize()
    return lfc.animation_frames(s, e)


def frame_marks(frames, step):
    """Slider marks: one per day (12-h mode) or date-based (daily mode)."""
    if step < pd.Timedelta(days=1):
        n_days = len(frames) // 2
        every = 1 if n_days <= 7 else 2
        marks = {i: t0.strftime('%d %b') for i, (t0, _) in enumerate(frames)
                 if t0.hour == 0 and (t0.normalize() - frames[0][0]).days % every == 0}
        last = len(frames) - 1
        marks[last] = frames[last][0].strftime('%d %b %Hh')
        return marks
    return date_marks(frames[0][0], len(frames) - 1)


def date_marks(cfg_min, total_days):
    """Slider marks adapted to the period length (days → years)."""
    start = pd.Timestamp(cfg_min)
    end = start + pd.Timedelta(days=total_days)
    if total_days <= 14:
        rng, fmt = pd.date_range(start, end, freq='2D'), '%d %b'
    elif total_days <= 45:
        rng, fmt = pd.date_range(start, end, freq='7D'), '%d %b'
    elif total_days <= 120:
        rng, fmt = pd.date_range(start, end, freq='14D'), '%d %b'
    elif total_days <= 400:
        rng, fmt = pd.date_range(start, end, freq='MS'), '%b %y'
    elif total_days <= 1100:
        rng, fmt = pd.date_range(start, end, freq='QS'), '%b %y'
    else:
        rng, fmt = pd.date_range(start, end, freq='YS'), '%Y'
    marks = {int((d - start).days): d.strftime(fmt) for d in rng}
    marks[0] = start.strftime('%d %b %y')
    min_gap = max(total_days * 0.06, 1)
    for k in [k for k in marks if 0 < k and total_days - k < min_gap]:
        del marks[k]
    marks[total_days] = end.strftime('%d %b %y')
    return marks


# ==========================================
# 1. LAYOUT
# ==========================================
def get_layout():
    cfg = load_global_config()
    folder = get_active_folder()
    if not folder:
        return html.Div("No active project found. Please configure a volcano first.", className='lf-msg lf-msg-warn')
    if not os.path.exists(os.path.join(folder, "filter_VIIRS_combined.csv")):
        return html.Div("No mapper results found. Run the LavaFlow Mapper (tab 5) first.",
                        className='lf-msg lf-msg-warn')

    volcano = cfg.get('volcano', 'Volcano')
    vent = [float(cfg.get('lats_vent', 0)), float(cfg.get('longs_vent', 0))]
    frames, step = get_frames()
    n_frames = len(frames)
    step_note = ("Period ≤ 2 weeks: the animation advances every 12 hours (times in UTC)."
                 if step < pd.Timedelta(days=1) else "The animation advances one day per step.")

    layer_options, layer_defaults = [], []
    if cfg.get('include_shapefile') and cfg.get('shapefile_path'):
        layer_options.append({'label': ' Shapefile', 'value': 'SHP'})
        layer_defaults.append('SHP')
    if cfg.get('include_reference_radius'):
        layer_options.append({'label': ' Reference radius', 'value': 'RAD'})
        layer_defaults.append('RAD')
    if cfg.get('include_reference_waypoint') and parse_waypoints_from_config(cfg):
        layer_options.append({'label': ' Waypoints', 'value': 'WPT'})
        layer_defaults.append('WPT')

    df = load_data()
    init_bounds = video.full_extent(df, cfg, layer_defaults)
    out_name = os.path.basename(video.output_path(folder, cfg))

    return html.Div([
        html.Div([
            html.H2(f"LavaFlow propagation — {volcano}"),
            html.P("Play the eruption step by step, adjust the view, then render it as a video. " + step_note,
                   className='lf-note'),
        ]),
        html.Div([
            # ---------------- sidebar ----------------
            html.Div([
                html.H4("1 · Display"),
                html.Label("Basemap", className='lf-label'),
                dcc.Dropdown(id='basemap-select', options=BASEMAP_OPTIONS, value=video.BASEMAPS['topo'],
                             clearable=False),
                html.Label("Layers", className='lf-label'),
                dcc.Checklist(id='layer-toggle', options=layer_options, value=layer_defaults,
                              className='lf-checks') if layer_options else html.Div([
                    html.Span("No optional layers enabled in Global Config.", className='lf-muted'),
                    dcc.Checklist(id='layer-toggle', options=[], value=[], style={'display': 'none'})]),

                html.H4("2 · Playback", style={'marginTop': '16px'}),
                html.Label("Speed", className='lf-label'),
                dcc.Slider(id='speed-slider', min=1, max=10, step=1, value=5,
                           marks={1: 'slow', 5: '5', 10: 'fast'}, **lfc.slider_kwargs()),
                html.Button("▶ Play / Pause", id="play-button", n_clicks=0, className='lf-btn lf-btn-block'),
                dcc.Interval(id='anim-interval', interval=600, n_intervals=0, disabled=True),
                html.Div(id='metrics-output', className='lf-stats', style={'marginTop': '10px'}),

                html.H4("3 · Video", style={'marginTop': '16px'}),
                html.Label("Map extent in the video", className='lf-label'),
                dcc.RadioItems(id='render-extent', value='view', labelStyle={'display': 'block'},
                               options=[{'label': ' Current map view', 'value': 'view'},
                                        {'label': ' All anomalies', 'value': 'all'}]),
                html.Button("RENDER MP4", id='btn-render', n_clicks=0, className='lf-btn lf-btn-warn lf-btn-block',
                            style={'marginTop': '8px'}),
                html.Div(f"Output: {out_name}", className='lf-muted', style={'marginTop': '4px',
                                                                               'wordBreak': 'break-all'}),
                dcc.Store(id='render-job'),
                html.Button("CANCEL RENDER", id='btn-render-cancel', n_clicks=0, disabled=True,
                            className='lf-btn lf-btn-ghost lf-btn-block', style={'marginTop': '6px'}),
                dcc.Interval(id='render-poll', interval=1000, disabled=True),
                html.Div(id='render-status'),
            ], className='lf-card lf-sidebar'),

            # ---------------- main ----------------
            html.Div([
                dl.Map([
                    dl.TileLayer(id="base-layer", url=video.BASEMAPS['topo'], maxZoom=17),
                    dl.LayerGroup(id="shapefile-layer"),
                    dl.LayerGroup(id="past-points-layer"),
                    dl.LayerGroup(id="today-points-layer"),
                    dl.LayerGroup(id="static-waypoints-layer"),
                    dl.ScaleControl(position="bottomleft", metric=True, imperial=False),
                    dl.Marker(position=vent, children=[dl.Tooltip("Vent")], icon=VENT_ICON),
                ], id="main-map", bounds=init_bounds, center=vent, zoom=12,
                    style={'height': 'clamp(320px, 50vh, 640px)', 'width': '100%', 'borderRadius': '8px'}),

                html.Div([
                    html.Div(id='current-date-display',
                             style={'textAlign': 'center', 'fontWeight': '700', 'fontSize': '18px', 'margin': '8px 0'}),
                    dcc.Slider(id='time-slider', min=0, max=max(n_frames - 1, 1), value=0, step=1,
                               marks=frame_marks(frames, step), updatemode='drag',
                               **lfc.slider_kwargs()),
                ], style={'padding': '4px 6px'}),

                dcc.Graph(id='timeseries-graph', className='lf-graph',
                          style={'height': 'clamp(300px, 38vh, 520px)'},
                          config={'responsive': True, 'displaylogo': False}),
            ], className='lf-card lf-main'),
        ], className='lf-module'),
    ])


# ==========================================
# 2. CALLBACKS
# ==========================================
def build_anim_timeseries(all_visible, cfg, layers, window_end):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    # placeholder traces keep both panels (and the radius line) visible before the first detection
    s0, _ = lfc.get_period(cfg)
    for r in (1, 2):
        fig.add_trace(go.Scatter(x=[s0], y=[None], mode='markers', showlegend=False, hoverinfo='skip'),
                      row=r, col=1)
    for sat, color in sat_colors.items():
        s_df = all_visible[all_visible['satellite'] == sat] if not all_visible.empty else all_visible
        if s_df is None or s_df.empty:
            continue
        fig.add_trace(go.Scattergl(x=s_df['date'], y=s_df['frp'], mode='markers', name=sat, legendgroup=sat,
                                   marker=dict(color=color, size=6, line=dict(width=0.6, color='black')),
                                   hovertemplate="%{x|%d/%m/%Y %H:%M}<br>FRP: %{y:.1f} MW<extra></extra>"),
                      row=1, col=1)
        sx, sy = lfc.stem_xy(s_df['date'], s_df['distance_km'])
        fig.add_trace(go.Scatter(x=sx, y=sy, mode='lines', line=dict(color=color, width=1),
                                 legendgroup=sat, showlegend=False, hoverinfo='skip'), row=2, col=1)
        fig.add_trace(go.Scattergl(x=s_df['date'], y=s_df['distance_km'], mode='markers', legendgroup=sat,
                                   showlegend=False, marker=dict(color=color, size=5),
                                   hovertemplate="%{x|%d/%m/%Y %H:%M}<br>Distance: %{y:.2f} km<extra></extra>"),
                      row=2, col=1)

    if 'RAD' in layers:
        rk = float(cfg.get('ref_radius_m', 5000)) / 1000.0
        fig.add_hline(y=rk, row=2, col=1, line=dict(color='black', width=1.2, dash='dash'),
                      annotation_text=f"Ref. radius: {rk:.2f} km", annotation_position="top left",
                      annotation_font=dict(size=10))
    fig.add_vline(x=window_end, line=dict(color='#6c3fb5', width=1))

    s, e = lfc.get_period(cfg)
    df_all = load_data()
    fig.update_layout(template="plotly_white", autosize=True, margin=dict(l=55, r=15, t=10, b=10),
                      legend=dict(orientation="h", y=1.02, yanchor='bottom', x=1, xanchor='right'),
                      uirevision='anim')
    if not pd.isna(s):
        e_excl = e.normalize() + pd.Timedelta(days=1)
        fig.update_xaxes(range=[s.normalize(), e_excl])
        n_days = (e_excl - s.normalize()).days
        if n_days <= lfc.SUBDAILY_MAX_DAYS:
            # 12-hour mode: ticks every 12 h (≤ 1 week) or every day, with the hour shown
            fig.update_xaxes(dtick=(12 if n_days <= 7 else 24) * 3600 * 1000, tick0=s.normalize(),
                             tickformat='%d %b<br>%H:%M', showgrid=True)
    if not df_all.empty:
        fig.update_yaxes(range=[0, df_all['frp'].max() * 1.08], row=1, col=1)
        dmax = df_all['distance_km'].max()
        if 'RAD' in layers:
            dmax = max(dmax, float(cfg.get('ref_radius_m', 5000)) / 1000.0)
        fig.update_yaxes(range=[0, dmax * 1.12], row=2, col=1)
    fig.update_yaxes(title_text="FRP (MW)", row=1, col=1)
    fig.update_yaxes(title_text="Distance (km)", row=2, col=1)
    return fig


def register_callbacks(app):
    @app.callback(
        [Output('anim-interval', 'disabled'), Output('anim-interval', 'interval'),
         Output('play-button', 'children')],
        [Input('play-button', 'n_clicks'), Input('speed-slider', 'value')],
        State('anim-interval', 'disabled')
    )
    def control_animation(n_clicks, speed_val, is_disabled):
        delay = 1100 - (speed_val or 5) * 100
        if not n_clicks:
            return True, delay, "▶ Play"
        if dash.ctx.triggered_id == 'play-button':
            is_disabled = not is_disabled
        return is_disabled, delay, ("▶ Play" if is_disabled else "❚❚ Pause")

    @app.callback(
        Output('time-slider', 'value'),
        Input('anim-interval', 'n_intervals'),
        State('time-slider', 'value'), State('time-slider', 'max'),
        prevent_initial_call=True
    )
    def step_forward(n, current_val, max_val):
        return current_val + 1 if current_val < max_val else 0

    @app.callback(
        [Output('base-layer', 'url'), Output('base-layer', 'maxZoom'), Output('shapefile-layer', 'children'),
         Output('past-points-layer', 'children'), Output('today-points-layer', 'children'),
         Output('static-waypoints-layer', 'children'),
         Output('timeseries-graph', 'figure'), Output('metrics-output', 'children'),
         Output('current-date-display', 'children')],
        [Input('time-slider', 'value'), Input('basemap-select', 'value'), Input('layer-toggle', 'value')]
    )
    def update_dashboard(days_passed, basemap_url, layers):
        cfg = load_global_config()
        folder = get_active_folder()
        df = load_data()
        layers = layers or []

        frames, step = get_frames()
        idx = min(max(int(days_passed or 0), 0), len(frames) - 1)
        target, nxt = frames[idx]
        subdaily = step < pd.Timedelta(days=1)

        if df.empty:
            all_visible = past = today = df
        else:
            all_visible = df[df['date'] < nxt]
            today = all_visible[all_visible['date'] >= target]
            past = all_visible[all_visible['date'] < target]

        shape_layer, wpt_layer = [], []
        if 'SHP' in layers:
            shp = lfc.shapefile_path(cfg, folder)
            if shp:
                try:
                    gj = lfc.shapefile_geojson(shp)
                    shape_layer.append(dl.GeoJSON(data=gj,
                                                  style={'color': 'black', 'weight': 2, 'fill': False}))
                except Exception as e:
                    print(f"[Animation] shapefile not drawn: {e}")
        if 'RAD' in layers:
            shape_layer.append(dl.Circle(center=[cfg.get('lats_vent', 0), cfg.get('longs_vent', 0)],
                                         radius=float(cfg.get('ref_radius_m', 5000)), color='black', weight=1.5,
                                         fill=False, dashArray='6,6'))
        if 'WPT' in layers:
            for w in parse_waypoints_from_config(cfg):
                wpt_layer.append(dl.Marker(position=[w['lat'], w['lon']], icon=waypoint_icon(w['symbol']),
                                           children=[dl.Tooltip(w['name'], permanent=True, direction='right')]
                                           if w['name'] else []))

        past_c = [dl.Circle(center=[r.latitude, r.longitude], radius=187.5, color="#f39c12",
                            fillOpacity=0.55, weight=0) for r in past.itertuples()]
        today_c = [dl.Circle(center=[r.latitude, r.longitude], radius=187.5, color="black", weight=1,
                             fillColor="#e74c3c", fillOpacity=1.0) for r in today.itertuples()]

        fig = build_anim_timeseries(all_visible, cfg, layers, nxt)
        metrics = [
            html.Div([html.Div("This 12 h" if subdaily else "Day", className='k'), html.Div(len(today), className='v')],
                     className='lf-stat alert'),
            html.Div([html.Div("Cumulative", className='k'), html.Div(len(all_visible), className='v')],
                     className='lf-stat'),
        ]
        max_zoom = 17 if basemap_url and 'opentopomap' in basemap_url else 19
        return (basemap_url, max_zoom, shape_layer, past_c, today_c, wpt_layer, fig, metrics,
                lfc.frame_label(target, nxt, step, today['date'].values if subdaily and len(today) else None))

    # ---------------- video rendering ----------------
    @app.callback(
        [Output('render-job', 'data'), Output('render-poll', 'disabled'),
         Output('render-status', 'children'), Output('btn-render', 'disabled'),
         Output('btn-render-cancel', 'disabled')],
        Input('btn-render', 'n_clicks'),
        [State('main-map', 'bounds'), State('render-extent', 'value'), State('basemap-select', 'value'),
         State('layer-toggle', 'value'), State('speed-slider', 'value')],
        prevent_initial_call=True
    )
    def start_render(n, bounds, extent_mode, basemap_url, layers, speed):
        if not n:
            return no_update, no_update, no_update, no_update, no_update
        folder = get_active_folder()
        cfg = load_global_config()
        use_bounds = bounds if extent_mode == 'view' else None
        job_id, msg = video.start_job(folder, cfg, use_bounds, basemap_url, layers or [], speed or 5)
        if not job_id:
            return None, True, html.Div(msg, className='lf-msg lf-msg-err'), False, True
        return job_id, False, html.Div(msg, className='lf-msg lf-msg-info'), True, False

    @app.callback(
        [Output('render-status', 'children', allow_duplicate=True), Output('render-poll', 'disabled', allow_duplicate=True),
         Output('btn-render', 'disabled', allow_duplicate=True),
         Output('btn-render-cancel', 'disabled', allow_duplicate=True)],
        Input('render-poll', 'n_intervals'),
        State('render-job', 'data'),
        prevent_initial_call=True
    )
    def poll_render(_, job_id):
        status, poll_off, btn_off = render_status_view(job_id)
        return status, poll_off, btn_off, not btn_off

    @app.callback(
        Output('btn-render-cancel', 'disabled', allow_duplicate=True),
        Input('btn-render-cancel', 'n_clicks'),
        State('render-job', 'data'),
        prevent_initial_call=True
    )
    def cancel_render(n, job_id):
        if n and job_id:
            video.cancel_job(job_id)
        return True


def render_status_view(job_id):
    """(status children, poll disabled, button disabled) for a render job."""
    job = video.job_status(job_id) if job_id else None
    if not job:
        return no_update, True, False
    pct = int(job['progress'] * 100)
    bar = html.Div(html.Div(style={'width': f'{pct}%', 'height': '100%', 'background': '#e67e22',
                                   'borderRadius': '4px'}),
                   style={'height': '8px', 'background': '#eee', 'borderRadius': '4px', 'margin': '6px 0'})
    if job['status'] == 'running':
        return html.Div([bar, html.Div(f"{pct}% · {job['message']}", className='lf-muted')]), False, True
    if job['status'] == 'done':
        cls = 'lf-msg lf-msg-warn' if job.get('notes') else 'lf-msg lf-msg-ok'
        return html.Div(job['message'], className=cls, style={'wordBreak': 'break-all'}), True, False
    if job['status'] == 'cancelled':
        return html.Div(job['message'], className='lf-msg lf-msg-warn'), True, False
    return html.Div(job['message'], className='lf-msg lf-msg-err'), True, False


if __name__ == '__main__':
    app = dash.Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True, port=8075)
