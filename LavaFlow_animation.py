import dash
from dash import dcc, html, Input, Output, State, ALL
import dash_leaflet as dl
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os


# ==========================================
# 0. CONFIGURATION LOADER
# ==========================================
def load_global_config():
    """Reads global variables from config.txt with list support."""
    config = {}
    config_path = "config.txt"
    if not os.path.exists(config_path):
        return config
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                k, v = key.strip(), value.strip()
                if k.startswith("wpt_") and "," in v:
                    config[k] = v.split(",")
                elif v.lower() == 'true':
                    config[k] = True
                elif v.lower() == 'false':
                    config[k] = False
                else:
                    try:
                        config[k] = float(v) if "." in v else int(v)
                    except ValueError:
                        config[k] = v
    return config


# Global constants referencing root directory
cfg = load_global_config()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "filter_VIIRS_combined.csv")
volcano = cfg.get('volcano', 'Volcano')
volcano_center = [cfg.get('lats_vent', 0.0), cfg.get('longs_vent', 0.0)]
sat_colors = {'SNPP': '#FFA500', 'NOAA20': '#800080', 'NOAA21': '#FF0000'}


# Forced slider bounds from config.txt
def get_config_dates():
    config = load_global_config()
    try:
        # Parse dates using dayfirst=True to match your format DD/MM/YYYY
        min_d = pd.to_datetime(config.get('start_day_str'), dayfirst=True).date()
        max_d = pd.to_datetime(config.get('end_day_str'), dayfirst=True).date()
        return min_d, max_d
    except:
        return pd.Timestamp.now().date(), pd.Timestamp.now().date()


min_date, max_date = get_config_dates()


def load_data():
    """Load normalized satellite data from root CSV."""
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date')
    return pd.DataFrame()


# ==========================================
# 2. LAYOUT GENERATOR
# ==========================================
def get_layout():
    """Returns the layout with fixed slider bounds from config."""
    # Recalculate range based on current config
    cfg_min, cfg_max = get_config_dates()
    total_days = (cfg_max - cfg_min).days

    return html.Div([
        html.Div([
            html.H2("LavaFlow Propagation", style={'margin': '0', 'color': '#2c3e50'}),
            html.P(f"Near Real-time monitoring: {volcano}", style={'color': '#7f8c8d'})
        ], style={'padding': '15px', 'backgroundColor': 'white', 'borderBottom': '1px solid #eee'}),

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
                        {'label': 'OpenStreetMap Mapnik', 'value': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'}
                    ],
                    value='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    clearable=False
                ),
                html.Br(),
                html.Label("Geospatial Layers:", style={'fontWeight': 'bold'}),
                dcc.Checklist(
                    id='layer-toggle',
                    options=[
                        {'label': ' Show Shapefile', 'value': 'SHP'},
                        {'label': ' Show Reference Radius', 'value': 'RAD'},
                        {'label': ' Show Waypoints', 'value': 'WPT'}
                    ],
                    value=['SHP', 'RAD', 'WPT']
                ),
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

            # Main Map & Graphs
            html.Div([
                dl.Map([
                    dl.TileLayer(id="base-layer"),
                    dl.LayerGroup(id="shapefile-layer"),
                    dl.LayerGroup(id="past-points-layer"),
                    dl.LayerGroup(id="today-points-layer"),
                    dl.LayerGroup(id="static-waypoints-layer"),
                    dl.ScaleControl(position="bottomleft", metric=True, imperial=False),
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
                        min=0,
                        max=total_days,
                        value=0, step=1,
                        # Labels calculated from config date + days increment
                        marks={i: (cfg_min + pd.Timedelta(days=i)).strftime('%b %y') for i in
                               range(0, total_days + 1, 180)}
                    )
                ], style={'padding': '15px 0px'}),

                dcc.Graph(id='timeseries-graph', style={'height': '38vh'})
            ], style={'width': '78%', 'padding': '20px'})
        ], style={'display': 'flex'})
    ])


# ==========================================
# 3. CALLBACK REGISTRATION
# ==========================================
def register_callbacks(app):
    """Registers dashboard animation logic callbacks."""

    @app.callback(
        [Output('anim-interval', 'disabled'), Output('anim-interval', 'interval')],
        [Input('play-button', 'n_clicks'), Input('speed-slider', 'value')],
        State('anim-interval', 'disabled')
    )
    def control_animation(n_clicks, speed_val, is_disabled):
        actual_delay = 1100 - (speed_val * 100)
        if n_clicks == 0: return True, actual_delay
        ctx = dash.callback_context
        if ctx.triggered and ctx.triggered[0]['prop_id'].split('.')[0] == 'play-button':
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
        local_df = load_data()

        cfg_min, _ = get_config_dates()
        target_date = pd.Timestamp(cfg_min + pd.Timedelta(days=days_passed))

        # Filter data based on simulation time
        all_visible = local_df[local_df['date'].dt.date <= target_date.date()] if not local_df.empty else pd.DataFrame()
        past_data = all_visible[
            all_visible['date'].dt.date < target_date.date()] if not all_visible.empty else pd.DataFrame()
        today_data = all_visible[
            all_visible['date'].dt.date == target_date.date()] if not all_visible.empty else pd.DataFrame()

        shape_layer = []
        waypoint_layer = []

        # Feature Loaders
        shp_path = local_cfg.get('shapefile_path', '')
        actual_shp = os.path.join(SCRIPT_DIR, shp_path if shp_path.endswith('.shp') else shp_path + '.shp')
        if 'SHP' in layers and os.path.exists(actual_shp):
            import geopandas as gpd
            gdf = gpd.read_file(actual_shp).to_crs(epsg=4326)
            shape_layer.append(
                dl.GeoJSON(data=gdf.__geo_interface__, style={'color': '#2c3e50', 'weight': 2, 'fill': False}))

        if 'RAD' in layers:
            shape_layer.append(dl.Circle(
                center=[local_cfg.get('lats_vent', 0), local_cfg.get('longs_vent', 0)],
                radius=local_cfg.get('ref_radius_m', 5000),
                color='black', weight=1, fill=False, dashArray='5,5'
            ))

        if 'WPT' in layers:
            def to_list(v):
                return v if isinstance(v, list) else [v] if v is not None else []

            w_names = to_list(local_cfg.get('wpt_names', []))
            w_lats = to_list(local_cfg.get('wpt_lats', []))
            w_lons = to_list(local_cfg.get('wpt_lons', []))
            w_syms = to_list(local_cfg.get('wpt_symbols', []))

            for i in range(len(w_names)):
                try:
                    lat, lon = float(w_lats[i]), float(w_lons[i])
                    sym = w_syms[i].strip() if i < len(w_syms) else 'circle'
                    if sym == 'circle':
                        waypoint_layer.append(
                            dl.CircleMarker(center=[lat, lon], radius=7, color='darkred', fill=True, fillOpacity=1.0,
                                            children=[dl.Tooltip(w_names[i])]))
                    else:
                        color_map = {'square': 'blue', 'diamond': 'green', 'star': 'gold', 'cross': 'violet'}
                        color = color_map.get(sym, 'red')
                        waypoint_layer.append(dl.Marker(position=[lat, lon], children=[dl.Tooltip(w_names[i])],
                                                        icon={
                                                            "iconUrl": f"https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-{color}.png",
                                                            "iconSize": [25, 41], "iconAnchor": [12, 41]}))
                except:
                    continue

        past_circles = [
            dl.Circle(center=[r.latitude, r.longitude], radius=150, color="#f39c12", fill=True, opacity=0.3, weight=0)
            for _, r in past_data.iterrows()] if not past_data.empty else []
        today_circles = [
            dl.Circle(center=[r.latitude, r.longitude], radius=200, color="#e74c3c", fill=True, opacity=1.0, weight=1)
            for _, r in today_data.iterrows()] if not today_data.empty else []

        # Subplots
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

        return basemap_url, shape_layer, past_circles, today_circles, waypoint_layer, fig, metrics, target_date.strftime(
            '%Y-%m-%d')


if __name__ == '__main__':
    app = dash.Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True)