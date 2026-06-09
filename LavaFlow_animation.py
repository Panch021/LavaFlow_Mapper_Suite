import dash
from dash import dcc, html, Input, Output, State, ALL
import dash_leaflet as dl
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import urllib.parse


# ==========================================
# 0. CONFIGURATION & DIRECTORY HELPERS
# ==========================================

def get_active_folder():
    """
    Returns the full relative folder path of the active project
    (e.g. 'projects/Wolf_2022' or 'examples/Sangay_2023').
    Works with both the new path-based active_volcano.txt and legacy name-only entries.
    """
    if os.path.exists("active_volcano.txt"):
        with open("active_volcano.txt", "r") as f:
            path = f.read().strip()
        if os.path.isdir(path):
            return path          # new format: full relative path
        # Legacy fallback: treat as bare folder name in root
        legacy = path.replace(" ", "_")
        if os.path.isdir(legacy):
            return legacy
    return None


def load_global_config():
    """Reads project-specific configuration from the volcano subfolder."""
    config = {}
    folder = get_active_folder()
    if not folder:
        return config
    folder_name = os.path.basename(folder)          # e.g. 'Wolf_2022'
    config_path = os.path.join(folder, f"config_{folder_name}.txt")

    if not os.path.exists(config_path):
        return config

    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                k, v = key.strip(), value.strip()
                if v.lower() == 'true':
                    config[k] = True
                elif v.lower() == 'false':
                    config[k] = False
                else:
                    try:
                        config[k] = float(v) if "." in v else int(v)
                    except ValueError:
                        config[k] = v
    return config


# ==========================================
# 0b. MULTI-WAYPOINT PARSER
# ==========================================
def parse_waypoints_from_config(c):
    """
    Parses waypoints from the config dict. Supports both:
      - Legacy single-waypoint format: wpt_names=Foo, wpt_lats=1.0, ...
      - New multi-waypoint format:    wpt_names=Foo;Bar, wpt_lats=1.0;2.0, ...
    Returns a list of dicts {name, lat, lon, symbol}.
    Returns an empty list if no valid waypoints are found.
    """
    def _as_list(v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(';')]
        return [str(v)]

    names = _as_list(c.get('wpt_names', ''))
    lats  = _as_list(c.get('wpt_lats', 0.0))
    lons  = _as_list(c.get('wpt_lons', 0.0))
    syms  = _as_list(c.get('wpt_symbols', 'circle'))

    n = max(len(names), len(lats), len(lons), len(syms))
    waypoints = []
    for i in range(n):
        try:
            name = names[i] if i < len(names) else ''
            lat_raw = lats[i] if i < len(lats) else ''
            lon_raw = lons[i] if i < len(lons) else ''
            sym = syms[i] if i < len(syms) else 'circle'
            # Skip entries with no usable coordinates
            if not str(lat_raw).strip() or not str(lon_raw).strip():
                continue
            lat = float(lat_raw)
            lon = float(lon_raw)
            waypoints.append({
                'name': str(name).strip(),
                'lat': lat,
                'lon': lon,
                'symbol': (str(sym).strip() or 'circle'),
            })
        except (ValueError, IndexError):
            continue
    return waypoints


def get_config_dates():
    """Retrieves simulation bounds from config.txt."""
    config = load_global_config()
    try:
        min_d = pd.to_datetime(config.get('start_day_str'), dayfirst=True).date()
        max_d = pd.to_datetime(config.get('end_day_str'), dayfirst=True).date()
        return min_d, max_d
    except:
        return pd.Timestamp.now().date(), pd.Timestamp.now().date()


def load_data():
    """Load filtered satellite data from the volcano subfolder."""
    folder = get_active_folder()
    if not folder: return pd.DataFrame()

    data_path = os.path.join(folder, "filter_VIIRS_combined.csv")
    if os.path.exists(data_path):
        df = pd.read_csv(data_path)
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date')
    return pd.DataFrame()


sat_colors = {'SNPP': '#FFA500', 'NOAA20': '#800080', 'NOAA21': '#FF0000'}


# ==========================================
# 0c. WAYPOINT SVG ICONS
# ==========================================
# Black filled shapes that mirror the folium output in LavaFlow_mapper.py:
#   - circle    → filled circle
#   - triangle  → upward filled triangle
#   - square    → 4-sided polygon rotated 45° (diamond shape, like folium's rotation=45)
# These SVGs are embedded as data URIs in dash_leaflet's Marker icon prop,
# so we get the same visual identity across folium and dash_leaflet maps.

WPT_SVGS = {
    'circle':   '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
                '<circle cx="8" cy="8" r="6.5" fill="black" stroke="black" stroke-width="1"/></svg>',
    'triangle': '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">'
                '<polygon points="10,2 18,17 2,17" fill="black" stroke="black" stroke-width="1"/></svg>',
    'square':   '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">'
                '<polygon points="10,2 18,10 10,18 2,10" fill="black" stroke="black" stroke-width="1" '
                'style="transform: rotate(45deg); transform-origin: 10px 10px;"/></svg>',
}

WPT_SVG_SIZES = {
    'circle':   (16, 16),
    'triangle': (20, 20),
    'square':   (20, 20),
}


def waypoint_icon(symbol):
    """
    Returns a dash_leaflet icon dict using an SVG data URI for the given symbol.
    All symbols are black filled to match the folium output in LavaFlow_mapper.
    Unknown symbols default to 'circle'.
    """
    sym = symbol if symbol in WPT_SVGS else 'circle'
    svg = WPT_SVGS[sym]
    w, h = WPT_SVG_SIZES[sym]
    uri = "data:image/svg+xml;utf8," + urllib.parse.quote(svg)
    return {
        "iconUrl": uri,
        "iconSize": [w, h],
        "iconAnchor": [w // 2, h // 2],   # anchor at center for clean placement
    }


# ==========================================
# 1. LAYOUT GENERATOR
# ==========================================

def get_layout():
    """
    Generates the full animation layout. Only called when the user clicks RUN.
    Checklist options are built dynamically from config so unavailable layers
    are not shown to the user.
    """
    cfg = load_global_config()
    folder = get_active_folder()

    if not folder:
        return html.Div("⚠️ No active project found. Please configure a volcano first.",
                        style={'textAlign': 'center', 'padding': '20px', 'color': '#e74c3c'})

    data_path = os.path.join(folder, "filter_VIIRS_combined.csv")
    if not os.path.exists(data_path):
        return html.Div([
            html.P("⚠️ No mapper results found.",
                   style={'color': '#e74c3c', 'fontWeight': 'bold', 'fontSize': '16px'}),
            html.P("Please run the 🌋 LavaFlow Mapper (Tab 4) first to generate the required data.",
                   style={'color': '#7f8c8d'})
        ], style={'textAlign': 'center', 'padding': '40px'})

    volcano_name = cfg.get('volcano', folder.replace("_", " ") if folder else 'Volcano')
    volcano_center = [cfg.get('lats_vent', 0.0), cfg.get('longs_vent', 0.0)]

    cfg_min, cfg_max = get_config_dates()
    total_days = (cfg_max - cfg_min).days

    # Slider tick marks
    if total_days <= 31:
        tick_step = 7
    elif total_days <= 95:
        tick_step = 14
    elif total_days <= 366:
        tick_step = 30
    elif total_days <= 731:
        tick_step = 90
    else:
        tick_step = 180

    slider_marks = {
        i: (cfg_min + pd.Timedelta(days=i)).strftime('%d %b %y')
        for i in range(0, total_days + 1, tick_step)
    }

    if slider_marks:
        last_tick_pos = max(slider_marks.keys())
        if (total_days - last_tick_pos) < (tick_step * 0.7):
            del slider_marks[last_tick_pos]
        slider_marks[total_days] = cfg_max.strftime('%d %b %y')

    # Build checklist options dynamically based on what is enabled in config
    layer_options = []
    layer_defaults = []

    has_shapefile = cfg.get('include_shapefile', False) and cfg.get('shapefile_path', '')
    has_radius = cfg.get('include_reference_radius', False)
    has_waypoint = cfg.get('include_reference_waypoint', False)

    if has_shapefile:
        layer_options.append({'label': ' Show Shapefile', 'value': 'SHP'})
        layer_defaults.append('SHP')
    if has_radius:
        layer_options.append({'label': ' Show Reference Radius', 'value': 'RAD'})
        layer_defaults.append('RAD')
    if has_waypoint:
        layer_options.append({'label': ' Show Waypoints', 'value': 'WPT'})
        layer_defaults.append('WPT')

    return html.Div([
        html.Div([
            html.H2("LavaFlow Propagation", style={'margin': '0', 'color': '#2c3e50'}),
            html.P(f"Near Real-time monitoring: {volcano_name}", style={'color': '#7f8c8d'})
        ], style={'padding': '15px', 'backgroundColor': 'white', 'borderBottom': '2px solid #eee'}),

        html.Div([
            # Sidebar Controls
            html.Div([
                html.H4("Control Panel"),
                html.Label("Basemap:", style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='basemap-select',
                    options=[
                        {'label': 'Esri World Imagery',
                         'value': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'},
                        {'label': 'OpenTopoMap', 'value': 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png'},
                        {'label': 'OpenStreetMap', 'value': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'}
                    ],
                    value='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
                    clearable=False
                ),
                html.Br(),

                # Only render the checklist if there is at least one available layer
                html.Div([
                    dcc.Checklist(
                        id='layer-toggle',
                        options=layer_options,
                        value=layer_defaults
                    )
                ] if layer_options else [
                    # Hidden dummy so the callback output 'layer-toggle' still exists in the DOM
                    dcc.Checklist(id='layer-toggle', options=[], value=[],
                                  style={'display': 'none'})
                ]),

                html.Br(),
                html.Label("Animation Speed:", style={'fontWeight': 'bold'}),
                dcc.Slider(id='speed-slider', min=1, max=10, step=1, value=5, marks={1: 'Slow', 10: 'Fast'}),
                html.Br(),
                html.Button("▶ PLAY / PAUSE", id="play-button", n_clicks=0,
                            style={'width': '100%', 'padding': '10px', 'backgroundColor': '#3498db', 'color': 'white',
                                   'borderRadius': '5px', 'fontWeight': 'bold', 'border': 'none'}),
                dcc.Interval(id='anim-interval', interval=500, n_intervals=0, disabled=True),
                html.Div(id='metrics-output',
                         style={'marginTop': '20px', 'padding': '10px', 'backgroundColor': '#f8f9fa'})
            ], style={'width': '20%', 'padding': '20px', 'borderRight': '1px solid #eee'}),

            # Main Map Area
            html.Div([
                dl.Map([
                    dl.TileLayer(id="base-layer"),
                    dl.LayerGroup(id="shapefile-layer"),
                    dl.LayerGroup(id="past-points-layer"),
                    dl.LayerGroup(id="today-points-layer"),
                    dl.LayerGroup(id="static-waypoints-layer"),
                    dl.ScaleControl(position="bottomleft", metric=True),
                    dl.Marker(position=volcano_center, children=[dl.Tooltip("Primary Vent")],
                              icon={
                                  "iconUrl": "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-black.png",
                                  "iconSize": [25, 41], "iconAnchor": [12, 41]})
                ], center=volcano_center, zoom=14, style={'height': '45vh', 'borderRadius': '8px'}, id="main-map"),

                html.Div([
                    html.P(id='current-date-display',
                           style={'textAlign': 'center', 'fontWeight': 'bold', 'fontSize': '18px'}),
                    dcc.Slider(
                        id='time-slider',
                        min=0, max=total_days, value=0, step=1,
                        marks=slider_marks
                    )
                ], style={'padding': '15px 0px'}),

                dcc.Graph(id='timeseries-graph', style={'height': '38vh'})
            ], style={'width': '78%', 'padding': '20px'})
        ], style={'display': 'flex'})
    ])


# ==========================================
# 2. CALLBACK REGISTRATION
# ==========================================
def register_callbacks(app):
    @app.callback(
        [Output('anim-interval', 'disabled'), Output('anim-interval', 'interval')],
        [Input('play-button', 'n_clicks'), Input('speed-slider', 'value')],
        State('anim-interval', 'disabled')
    )
    def control_animation(n_clicks, speed_val, is_disabled):
        actual_delay = 1100 - (speed_val * 100)
        if n_clicks == 0: return True, actual_delay
        ctx = dash.callback_context
        if ctx.triggered and 'play-button' in ctx.triggered[0]['prop_id']:
            return not is_disabled, actual_delay
        return is_disabled, actual_delay

    @app.callback(
        Output('time-slider', 'value'),
        Input('anim-interval', 'n_intervals'),
        State('time-slider', 'value'),
        State('time-slider', 'max')
    )
    def step_forward(n, current_val, max_val):
        if current_val < max_val: return current_val + 1
        return 0

    @app.callback(
        [Output('base-layer', 'url'), Output('shapefile-layer', 'children'),
         Output('past-points-layer', 'children'), Output('today-points-layer', 'children'),
         Output('static-waypoints-layer', 'children'),
         Output('timeseries-graph', 'figure'), Output('metrics-output', 'children'),
         Output('current-date-display', 'children')],
        [Input('time-slider', 'value'), Input('basemap-select', 'value'), Input('layer-toggle', 'value')]
    )
    def update_dashboard(days_passed, basemap_url, layers):
        local_cfg = load_global_config()
        folder = get_active_folder()
        local_df = load_data()

        # layers may be None if checklist has no options
        layers = layers or []

        cfg_min, _ = get_config_dates()
        target_date = pd.Timestamp(cfg_min + pd.Timedelta(days=days_passed))

        all_visible = local_df[local_df['date'].dt.date <= target_date.date()] if not local_df.empty else pd.DataFrame()
        past_data = all_visible[all_visible['date'].dt.date < target_date.date()] if not all_visible.empty else pd.DataFrame()
        today_data = all_visible[all_visible['date'].dt.date == target_date.date()] if not all_visible.empty else pd.DataFrame()

        shape_layer, waypoint_layer = [], []
        shp_name = local_cfg.get('shapefile_path', '')
        if 'SHP' in layers and shp_name:
            if not shp_name.lower().endswith('.shp'): shp_name += '.shp'
            actual_shp = os.path.join(folder, shp_name) if folder else shp_name
            if os.path.exists(actual_shp):
                try:
                    import geopandas as gpd
                    gdf = gpd.read_file(actual_shp).to_crs(epsg=4326)
                    shape_layer.append(
                        dl.GeoJSON(data=gdf.__geo_interface__, style={'color': '#2c3e50', 'weight': 2, 'fill': False}))
                except:
                    pass

        if 'RAD' in layers:
            shape_layer.append(dl.Circle(center=[local_cfg.get('lats_vent', 0), local_cfg.get('longs_vent', 0)],
                                         radius=local_cfg.get('ref_radius_m', 5000), color='black', weight=1,
                                         fill=False, dashArray='5,5'))

        # --- MULTI-WAYPOINT PLOTTING ---
        # All symbols are rendered as black SVG icons matching LavaFlow_mapper.py
        # so the visual identity is identical across the folium and dash_leaflet maps.
        if 'WPT' in layers:
            waypoints = parse_waypoints_from_config(local_cfg)
            for wpt in waypoints:
                lat, lon, name, sym = wpt['lat'], wpt['lon'], wpt['name'], wpt['symbol']
                tooltip_children = [dl.Tooltip(name)] if name else []
                waypoint_layer.append(
                    dl.Marker(
                        position=[lat, lon],
                        icon=waypoint_icon(sym),
                        children=tooltip_children
                    )
                )

        past_circles = [
            dl.Circle(center=[r.latitude, r.longitude], radius=185, color="#f39c12", fill=True, opacity=0.7, weight=0)
            for _, r in past_data.iterrows()]
        today_circles = [
            dl.Circle(center=[r.latitude, r.longitude], radius=185, color="#e74c3c", fill=True, opacity=1.0, weight=1)
            for _, r in today_data.iterrows()]

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)
        if not all_visible.empty:
            for sat, color in sat_colors.items():
                s_df = all_visible[all_visible['satellite'] == sat]
                if not s_df.empty:
                    fig.add_trace(go.Scatter(x=s_df['date'], y=s_df['frp'], mode='markers', name=sat,
                                             marker=dict(color=color, size=6)), row=1, col=1)
                    fig.add_trace(go.Scatter(x=s_df['date'], y=s_df['distance_km'], mode='markers', name=sat,
                                             marker=dict(color=color, size=6), showlegend=False), row=2, col=1)

        fig.update_layout(template="plotly_white", margin=dict(l=50, r=20, t=20, b=20), height=380,
                          legend=dict(orientation="h", y=-0.2))
        fig.update_yaxes(title_text="FRP (MW)", row=1, col=1)
        fig.update_yaxes(title_text="Distance (km)", row=2, col=1)

        metrics = html.Div([
            html.P([html.Strong("Cumulative Alerts: "), f"{len(all_visible)}"]),
            html.P([html.Strong("Today's Alerts: "), f"{len(today_data)}"], style={'color': '#e74c3c'})
        ])

        return basemap_url, shape_layer, past_circles, today_circles, waypoint_layer, fig, metrics, target_date.strftime('%Y-%m-%d')


if __name__ == '__main__':
    app = dash.Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True, port=8075)
