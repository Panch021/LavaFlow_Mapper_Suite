import dash
from dash import dcc, html, Input, Output, State, no_update, ALL
import pandas as pd
import os
import webbrowser
from threading import Timer
from datetime import datetime, date, timedelta

# Technical modules import
import FIRMS_download as download_logic
import Anomalies_count as anomalies_module
import FRP_Statistics as stats_module
import LavaFlow_mapper as mapper_module
import LavaFlow_animation as anim_module
import LavaFlow_speed as speed_module
import Export_report as export_module

# ==========================================
# 0. CONFIGURATION & DATA ENGINE
# ==========================================

GVP_FILE = 'GVP_Volcano_List_Holocene.csv'
if os.path.exists(GVP_FILE):
    df_gvp = pd.read_csv(GVP_FILE)
    gvp_options = [{'label': row['Volcano Name'], 'value': row['Volcano Name']} for _, row in df_gvp.iterrows()]
else:
    df_gvp = pd.DataFrame()
    gvp_options = []

# ---- Project directory structure ----
EXAMPLES_DIR = "examples"
PROJECTS_DIR = "projects"
os.makedirs(PROJECTS_DIR, exist_ok=True)


# ---- Volcano name input styling helpers ----
VOLCANO_INPUT_BASE = {
    'width': '100%', 'marginBottom': '10px',
    'padding': '6px 8px', 'borderRadius': '5px',
}

def volcano_input_style(volcano_value):
    """Highlight the volcano name input once a real volcano has been selected."""
    has_volcano = bool(volcano_value) and str(volcano_value).strip() not in ('', 'Volcano Name')
    if has_volcano:
        return {**VOLCANO_INPUT_BASE,
                'border': '2px solid #27ae60',
                'backgroundColor': '#eafaf1',
                'fontWeight': 'bold'}
    return {**VOLCANO_INPUT_BASE,
            'border': '1px solid #ccc',
            'backgroundColor': 'white',
            'fontWeight': 'normal'}


# ==========================================
# 0b. WAYPOINT HELPERS (multi-waypoint support)
# ==========================================

def parse_waypoints_from_config(c):
    """
    Parses waypoints from the config dict. Supports both:
      - Legacy single-waypoint format: wpt_names=Foo, wpt_lats=1.0, ...
      - New multi-waypoint format:    wpt_names=Foo;Bar, wpt_lats=1.0;2.0, ...
    Returns a list of dicts {name, lat, lon, symbol}. Ensures at least one entry.
    Downstream modules (LavaFlow_mapper, Export_report) should also use this
    function (or replicate its logic) to read the multi-waypoint config.
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
            lat_raw = lats[i] if i < len(lats) else '0.0'
            lon_raw = lons[i] if i < len(lons) else '0.0'
            sym = syms[i] if i < len(syms) else 'circle'
            lat = float(lat_raw) if str(lat_raw).strip() else 0.0
            lon = float(lon_raw) if str(lon_raw).strip() else 0.0
            waypoints.append({
                'name': str(name).strip(),
                'lat': lat,
                'lon': lon,
                'symbol': str(sym).strip() or 'circle',
            })
        except (ValueError, IndexError):
            continue

    if not waypoints:
        waypoints = [{'name': '', 'lat': 0.0, 'lon': 0.0, 'symbol': 'circle'}]
    return waypoints


def render_waypoint_row(idx, wpt):
    """Renders a single waypoint row with pattern-matched IDs so callbacks
    can read/remove individual waypoints. idx is the position in the list."""
    return html.Div([
        html.Div([
            html.Span(f"📍 Waypoint {idx + 1}", style={
                'fontWeight': 'bold', 'fontSize': '13px', 'color': '#2c3e50'}),
            html.Button("× Remove",
                id={'type': 'wpt-remove', 'index': idx},
                n_clicks=0,
                style={'marginLeft': 'auto', 'padding': '3px 10px',
                       'backgroundColor': '#e74c3c', 'color': 'white',
                       'border': 'none', 'borderRadius': '4px',
                       'cursor': 'pointer', 'fontSize': '11px',
                       'fontWeight': 'bold'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '8px'}),
        html.Div([
            html.Div([
                html.Label("Name:", style={'display': 'block', 'fontSize': '11px',
                                            'color': '#7f8c8d'}),
                dcc.Input(id={'type': 'wpt-name', 'index': idx},
                          type='text', value=wpt.get('name', ''),
                          style={'width': '140px'})
            ], style={'display': 'inline-block', 'marginRight': '10px'}),
            html.Div([
                html.Label("Latitude:", style={'display': 'block', 'fontSize': '11px',
                                                'color': '#7f8c8d'}),
                dcc.Input(id={'type': 'wpt-lat', 'index': idx},
                          type='number', value=wpt.get('lat', 0.0),
                          style={'width': '150px'})
            ], style={'display': 'inline-block', 'marginRight': '10px'}),
            html.Div([
                html.Label("Longitude:", style={'display': 'block', 'fontSize': '11px',
                                                 'color': '#7f8c8d'}),
                dcc.Input(id={'type': 'wpt-lon', 'index': idx},
                          type='number', value=wpt.get('lon', 0.0),
                          style={'width': '150px'})
            ], style={'display': 'inline-block', 'marginRight': '10px'}),
            html.Div([
                html.Label("Symbol:", style={'display': 'block', 'fontSize': '11px',
                                              'color': '#7f8c8d'}),
                dcc.Dropdown(id={'type': 'wpt-symbol', 'index': idx},
                             value=wpt.get('symbol', 'circle'),
                             clearable=False,
                             style={'width': '160px'},
                             options=[
                                 {'label': '● Circle',   'value': 'circle'},
                                 {'label': '▲ Triangle', 'value': 'triangle'},
                                 {'label': '■ Square',   'value': 'square'},
                             ])
            ], style={'display': 'inline-block', 'verticalAlign': 'top'}),
        ]),
    ], style={
        'padding': '12px', 'marginBottom': '10px',
        'backgroundColor': 'white', 'borderRadius': '5px',
        'border': '1px solid #ddd',
    })


def list_existing_projects():
    """Scans examples/ and projects/ for valid volcano config files."""
    projects = []
    scan_dirs = [(PROJECTS_DIR, ""), (EXAMPLES_DIR, " 📌 Example")]
    for base_dir, tag in scan_dirs:
        if not os.path.isdir(base_dir):
            continue
        for item in sorted(os.listdir(base_dir)):
            folder_path = os.path.join(base_dir, item)
            if not os.path.isdir(folder_path) or item.startswith("."):
                continue
            config_file = os.path.join(folder_path, f"config_{item}.txt")
            if os.path.exists(config_file):
                display_name = item.replace("_", " ")
                projects.append({
                    'label': f"📁 {display_name}{tag}",
                    'value': folder_path
                })
    return sorted(projects, key=lambda x: x['label'])


def get_active_volcano_name():
    if os.path.exists("active_volcano.txt"):
        with open("active_volcano.txt", "r") as f:
            return f.read().strip()
    return None


def get_display_name(folder_path):
    if not folder_path:
        return None
    return os.path.basename(folder_path).replace("_", " ")


def load_global_config():
    """Loads configuration from the active project folder."""
    default_params = {
        'volcano': 'Volcano Name', 'lats_vent': 0.0, 'longs_vent': 0.0,
        'start_day_str': '01/01/2026 00:00', 'end_day_str': '01/05/2026 23:59',
        'filter_frp': 35, 'frp_filter_mode': 'gt', 'filter_track': 0.5, 'map_key': 'INSERT_YOUR_MAP_KEY_HERE',
        'include_reference_radius': True, 'ref_radius_m': 5000,
        'include_shapefile': False, 'shapefile_path': '',
        'include_reference_waypoint': False,
        'wpt_names': 'Reference Point', 'wpt_lats': 0.0, 'wpt_lons': 0.0, 'wpt_symbols': 'circle'
    }

    active_path = get_active_volcano_name()
    config_path = None
    if active_path:
        folder_name = os.path.basename(active_path)
        candidate = os.path.join(active_path, f"config_{folder_name}.txt")
        if os.path.exists(candidate):
            config_path = candidate

    if not config_path or not os.path.exists(config_path):
        return default_params

    config = {}
    with open(config_path, "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                parts = line.strip().split("=", 1)
                if len(parts) == 2:
                    k, v = parts
                    # NOTE: do NOT strip commas/semicolons on wpt_* keys —
                    # multi-waypoint support uses ';' as a separator.
                    if v.lower() == 'true':
                        config[k] = True
                    elif v.lower() == 'false':
                        config[k] = False
                    else:
                        try:
                            config[k] = float(v) if "." in v else int(v)
                        except ValueError:
                            config[k] = v

    final_cfg = default_params.copy()
    final_cfg.update(config)
    return final_cfg


# Initialize Dashboard Instance
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "LavaFlow Suite"

active_v = get_active_volcano_name()
active_v_display = get_display_name(active_v)
header_display = f"LavaFlow Mapper Suite: {active_v_display}" if active_v_display else "LavaFlow Mapper Suite"

anim_module.register_callbacks(app)
anomalies_module.register_callbacks(app)
export_module.register_callbacks(app)

app.layout = html.Div([
    dcc.Store(id='store-stats-status', data={'run': False}, storage_type='session'),
    dcc.Store(id='store-mapper-status', data={'run': False}, storage_type='session'),
    dcc.Store(id='store-speed-status', data={'run': False}, storage_type='session'),

    html.Div([
        html.H1(id='main-header-title', children=header_display, style={'margin': '0', 'color': '#2c3e50'}),
    ], style={'padding': '20px', 'backgroundColor': 'white', 'borderBottom': '2px solid #eee'}),

    dcc.Tabs(id="suite-tabs", value='tab-config', persistence=True, persistence_type='memory', children=[
        dcc.Tab(label='⚙️ 1. Global Config', value='tab-config'),
        dcc.Tab(label='🛰️ 2. FIRMS Download', value='tab-download'),
        dcc.Tab(label='📈 3. Anomalies Count', value='tab-anomalies'),
        dcc.Tab(label='📊 4. FRP Statistics', value='tab-stats'),
        dcc.Tab(label='🌋 5. LavaFlow Mapper', value='tab-mapper'),
        dcc.Tab(label='🗺️ 6. LavaFlow Propagation', value='tab-animation'),
        dcc.Tab(label='🚀 7. Propagation Speed', value='tab-speed'),
        dcc.Tab(label='📤 8. Export Report', value='tab-export'),
    ]),
    html.Div(id='tabs-content-container', style={'padding': '20px'})
])


# ==========================================
# 1. TAB RENDERING LOGIC
# ==========================================
@app.callback(
    Output('tabs-content-container', 'children'),
    Input('suite-tabs', 'value'),
    [State('store-stats-status', 'data'), State('store-mapper-status', 'data'),
     State('store-speed-status', 'data')]
)
def render_tab(tab, stats_data, mapper_data, speed_data):
    c = load_global_config()

    if tab == 'tab-config':
        existing_projects = list_existing_projects()
        active_path = get_active_volcano_name() or ""
        is_example = active_path.startswith(EXAMPLES_DIR)
        initial_waypoints = parse_waypoints_from_config(c)

        return html.Div([
            html.Div([
                # Left Column: Volcano Setup
                html.Div([
                    html.H4("📂 Load Existing Project", style={'color': '#2c3e50'}),
                    dcc.Dropdown(id='cfg-load-project', options=existing_projects, placeholder="Select project...",
                                 style={'marginBottom': '20px'}),
                    html.Hr(),
                    html.H4("🌋 Create / Edit Volcano Config", style={'color': '#2980b9'}),
                    html.Label(["Search GVP: ",
                                html.A("[Source]", href="https://volcano.si.edu/volcanolist_holocene.cfm",
                                       target="_blank", style={'fontSize': '11px'})], style={'fontWeight': 'bold'}),
                    dcc.Dropdown(id='cfg-volcano-search', options=gvp_options, placeholder="Auto-fill...",
                                 style={'marginBottom': '10px'}),
                    html.Label("Volcano Name: "),
                    dcc.Input(id='cfg-volcano', value=c.get('volcano'),
                              style=volcano_input_style(c.get('volcano'))),
                    html.Div([
                        html.Label("Vent Lat: "), dcc.Input(id='cfg-lat-vent', type='number', value=c.get('lats_vent'),
                                                            style={'width': '80px', 'marginRight': '10px'}),
                        html.Label("Vent Long: "),
                        dcc.Input(id='cfg-lon-vent', type='number', value=c.get('longs_vent'), style={'width': '80px'})
                    ]),
                    html.Label("Analysis Period (DD/MM/YYYY):", style={'marginTop': '12px', 'display': 'block', 'fontWeight': 'bold'}),
                    html.Div([
                        html.Div([
                            html.Label("Start date:", style={'fontSize': '12px', 'color': '#7f8c8d', 'marginBottom': '3px', 'display': 'block'}),
                            dcc.Input(
                                id='cfg-date-start', type='text', debounce=True,
                                value=c.get('start_day_str', '').split()[0],
                                placeholder='DD/MM/YYYY',
                                style={'width': '130px', 'fontFamily': 'monospace', 'fontSize': '14px',
                                       'padding': '6px 8px', 'border': '1px solid #ccc', 'borderRadius': '5px'}
                            ),
                        ], style={'marginRight': '20px'}),
                        html.Div([
                            html.Label("End date:", style={'fontSize': '12px', 'color': '#7f8c8d', 'marginBottom': '3px', 'display': 'block'}),
                            html.Div([
                                dcc.Input(
                                    id='cfg-date-end', type='text', debounce=True,
                                    value=c.get('end_day_str', '').split()[0],
                                    placeholder='DD/MM/YYYY',
                                    style={'width': '130px', 'fontFamily': 'monospace', 'fontSize': '14px',
                                           'padding': '6px 8px', 'border': '1px solid #ccc', 'borderRadius': '5px',
                                           'marginRight': '12px'}
                                ),
                                html.Button("+1d", id='btn-date-plus1', n_clicks=0, title="Advance end date +1 day",
                                    style={'padding': '6px 9px', 'fontSize': '12px', 'fontWeight': 'bold',
                                           'backgroundColor': '#3498db', 'color': 'white',
                                           'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer', 'marginRight': '8px'}),
                                html.Button("+7d", id='btn-date-plus7', n_clicks=0, title="Advance end date +7 days",
                                    style={'padding': '6px 9px', 'fontSize': '12px', 'fontWeight': 'bold',
                                           'backgroundColor': '#27ae60', 'color': 'white',
                                           'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer'}),
                            ], style={'display': 'flex', 'alignItems': 'center'}),
                        ]),
                    ], style={'display': 'flex', 'alignItems': 'flex-end', 'marginTop': '8px'}),
                    html.Div(id='cfg-date-validation', style={'fontSize': '11px', 'marginTop': '5px', 'minHeight': '16px'})
                ], style={'flex': '1.5', 'padding': '20px', 'border': '1px solid #eee', 'marginRight': '15px',
                          'borderRadius': '10px'}),

                # Right Column: Filters & API
                html.Div([
                    html.H4("Threshold Filters", style={'color': '#2980b9'}),
                    html.Label(["FRP filter (MW): ",
                                html.A("[Ref]", href="https://doi.org/10.3390/rs14143483", target="_blank",
                                       style={'fontSize': '11px'})]),
                    html.Div([
                        dcc.RadioItems(
                            id='cfg-frp-mode',
                            options=[
                                {'label': ' ≥ (for lava flows)', 'value': 'gt'},
                                {'label': ' ≤ (other pyroclastic material)', 'value': 'lt'},
                            ],
                            value=c.get('frp_filter_mode', 'gt'),
                            labelStyle={'display': 'block', 'fontSize': '14px'}
                        ),
                        dcc.Input(id='cfg-frp', type='number', value=c.get('filter_frp'),
                                  style={'width': '80px', 'marginTop': '5px'})
                    ], style={'marginBottom': '10px'}),
                    html.Label(["Track: ",
                                html.A("[Ref]", href="https://www.mdpi.com/2072-4292/9/10/974", target="_blank",
                                       style={'fontSize': '11px'})]),
                    dcc.Input(id='cfg-track', type='number', value=c.get('filter_track'), step=0.1,
                              style={'width': '80px', 'display': 'block', 'marginBottom': '20px'}),

                    html.Hr(),
                    html.H4("API Credentials", style={'color': '#2980b9'}),
                    html.Label(["FIRMS API MAP_KEY: ",
                                html.A("[Get API Key]", href="https://firms.modaps.eosdis.nasa.gov/api/map_key/",
                                       target="_blank", style={'fontSize': '11px'})]),
                    dcc.Input(id='cfg-map-key', value=c.get('map_key'),
                              style={'width': '100%', 'fontFamily': 'monospace', 'marginTop': '5px'})
                ], style={'flex': '1', 'padding': '20px', 'border': '1px solid #eee', 'borderRadius': '10px'}),
            ], style={'display': 'flex', 'marginBottom': '20px'}),

            # Row 2: Geospatial & Waypoints
            html.Div([
                html.H4("Geospatial Layers & Reference Waypoints", style={'color': '#2980b9'}),
                html.Div([
                    dcc.Checklist(id='cfg-chk-rad', options=[{'label': ' Include Radius (m)', 'value': 'True'}],
                                  value=['True'] if c.get('include_reference_radius') else []),
                    dcc.Input(id='cfg-radius-m', type='number', value=c.get('ref_radius_m'),
                              style={'width': '100px', 'marginLeft': '10px'})
                ], style={'marginBottom': '15px'}),
                html.Div([
                    html.Label("Include Shapefile (include .shp): ", style={'fontWeight': 'bold'}),
                    dcc.Checklist(id='cfg-chk-shp', options=[{'label': ' Show Shapefile', 'value': 'True'}],
                                  value=['True'] if c.get('include_shapefile') else []),
                    dcc.Input(id='cfg-shp-path', value=c.get('shapefile_path'), placeholder="Path/to/shapefile.shp",
                              style={'width': '350px', 'marginLeft': '10px'})
                ], style={'marginBottom': '25px'}),

                # --- Multi-waypoint section ---
                html.Div([
                    # Header row: label, "show" checkbox, and the "+ Add Waypoint" button
                    html.Div([
                        html.Label("Reference Waypoints:", style={'fontWeight': 'bold'}),
                        dcc.Checklist(
                            id='cfg-chk-wpt',
                            options=[{'label': ' Show Waypoints', 'value': 'True'}],
                            value=['True'] if c.get('include_reference_waypoint') else [],
                            style={'marginLeft': '15px'}
                        ),
                        html.Button("+ Add Waypoint", id='btn-add-wpt', n_clicks=0,
                            style={'marginLeft': 'auto', 'padding': '6px 14px',
                                   'backgroundColor': '#27ae60', 'color': 'white',
                                   'border': 'none', 'borderRadius': '4px',
                                   'cursor': 'pointer', 'fontWeight': 'bold',
                                   'fontSize': '13px'}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '12px'}),

                    # Store holds the current waypoint list; container is rebuilt from it
                    dcc.Store(id='wpt-list-store', data=initial_waypoints),
                    html.Div(id='wpt-container'),
                ], style={'padding': '15px', 'border': '1px solid #ddd', 'borderRadius': '5px',
                          'backgroundColor': '#f9f9f9'})
            ], style={'padding': '20px', 'border': '1px solid #eee', 'marginBottom': '20px', 'borderRadius': '10px'}),

            html.Button("SAVE ALL PARAMETERS", id="btn-save-config", n_clicks=0,
                        disabled=is_example,
                        style={'padding': '15px 30px',
                               'backgroundColor': '#95a5a6' if is_example else '#e67e22',
                               'color': 'white', 'fontWeight': 'bold', 'border': 'none',
                               'borderRadius': '5px',
                               'cursor': 'not-allowed' if is_example else 'pointer'}),
            html.Div(
                "📌 Example project — read only. Use GVP Search to create your own project." if is_example else "",
                style={'marginTop': '10px', 'fontSize': '13px', 'color': '#7f8c8d', 'fontStyle': 'italic'}
            ),
            html.Div(id="config-save-status", style={'marginTop': '10px', 'fontWeight': 'bold', 'color': '#27ae60'})
        ])

    elif tab == 'tab-download':
        return html.Div([
            html.H3("🛰️ Step 1: FIRMS Data Downloader"),
            html.Div([
                html.P("Updates volcano FIRMS records. Large ranges are automatically split into 5-day chunks."),
                html.Div([html.Label("Download Radius (m):"),
                          dcc.Input(id='dl-radius', type='number', value=c.get('ref_radius_m', 10000),
                                    style={'width': '150px', 'display': 'block', 'margin': '10px auto'})]),
                dcc.DatePickerRange(id='dl-date-picker', start_date=date.today() - timedelta(days=4),
                                    end_date=date.today(), display_format='YYYY-MM-DD'),
                html.Br(), html.Br(),
                html.Button("START DOWNLOAD", id="btn-run-download", n_clicks=0,
                            style={'backgroundColor': '#e67e22', 'color': 'white', 'padding': '12px 24px',
                                   'border': 'none', 'borderRadius': '5px'}),
            ], style={'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '10px',
                      'border': '1px solid #ddd', 'maxWidth': '600px', 'margin': 'auto'}),
            dcc.Loading(html.Div(id="dl-output-log",
                                 style={'marginTop': '20px', 'whiteSpace': 'pre-line', 'fontFamily': 'monospace'}))
        ], style={'textAlign': 'center'})

    elif tab == 'tab-anomalies':
        try:
            sd_str = c.get('start_day_str').split()[0]
            ed_str = c.get('end_day_str').split()[0]
            start_dt = datetime.strptime(sd_str, '%d/%m/%Y')
            end_dt = datetime.strptime(ed_str, '%d/%m/%Y')
        except:
            start_dt, end_dt = datetime(2026, 1, 1), datetime(2026, 5, 1)
        return anomalies_module.get_layout(start_date=start_dt, end_date=end_dt)

    elif tab == 'tab-stats':
        initial_content = stats_module.get_layout() if stats_data['run'] else html.P(
            "No results yet. Click run to generate statistics.")
        return html.Div([html.Button("RUN FRP STATISTICS", id="btn-run-stats", n_clicks=0,
                                     style={'padding': '10px 20px', 'backgroundColor': '#3498db', 'color': 'white',
                                            'border': 'none', 'borderRadius': '5px', 'marginBottom': '20px'}),
                         dcc.Loading(html.Div(id="out-stats-results", children=initial_content))],
                        style={'textAlign': 'center'})

    elif tab == 'tab-mapper':
        initial_content = mapper_module.get_layout() if mapper_data['run'] else html.P(
            "No results yet. Click run to generate the map.")
        return html.Div([html.Button("RUN MAPPER ENGINE", id="btn-run-mapper", n_clicks=0,
                                     style={'padding': '10px 20px', 'backgroundColor': '#27ae60', 'color': 'white',
                                            'border': 'none', 'borderRadius': '5px'}),
                         dcc.Loading(html.Div(id="out-mapper-results", children=initial_content))],
                        style={'textAlign': 'center'})

    elif tab == 'tab-animation':
        return anim_module.get_layout()

    elif tab == 'tab-speed':
        initial_content = speed_module.get_layout() if speed_data['run'] else html.P(
            "No results yet. Run Mapper first.")
        return html.Div([html.Button("CALCULATE SPEED", id="btn-run-speed", n_clicks=0,
                                     style={'padding': '10px 20px', 'backgroundColor': '#9b59b6', 'color': 'white',
                                            'border': 'none', 'borderRadius': '5px', 'marginBottom': '20px'}),
                         dcc.Loading(html.Div(id="out-speed-results", children=initial_content))],
                        style={'textAlign': 'center'})

    elif tab == 'tab-export':
        return export_module.get_layout()


# ==========================================
# 2. LOGIC CALLBACKS
# ==========================================

@app.callback(
    [Output('cfg-volcano', 'value', allow_duplicate=True),
     Output('cfg-lat-vent', 'value', allow_duplicate=True),
     Output('cfg-lon-vent', 'value', allow_duplicate=True),
     Output('cfg-frp', 'value', allow_duplicate=True),
     Output('cfg-track', 'value', allow_duplicate=True),
     Output('cfg-radius-m', 'value', allow_duplicate=True),
     Output('cfg-date-start', 'value', allow_duplicate=True),
     Output('cfg-date-end', 'value', allow_duplicate=True),
     Output('cfg-shp-path', 'value', allow_duplicate=True),
     Output('wpt-list-store', 'data', allow_duplicate=True),
     Output('config-save-status', 'children', allow_duplicate=True),
     Output('main-header-title', 'children', allow_duplicate=True)],
    Input('cfg-volcano-search', 'value'),
    prevent_initial_call=True
)
def gvp_search_cb(selected_volcano):
    """GVP Search: Fills defaults and creates config folder inside projects/."""
    if not selected_volcano or df_gvp.empty: return [no_update] * 12
    row = df_gvp[df_gvp['Volcano Name'] == selected_volcano].iloc[0]
    lat, lon = row['Latitude'], row['Longitude']
    folder_name = selected_volcano.strip().replace(" ", "_")
    folder_path = os.path.join(PROJECTS_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    with open("active_volcano.txt", "w") as f:
        f.write(folder_path)
    config_path = os.path.join(folder_path, f"config_{folder_name}.txt")

    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write(f"volcano={selected_volcano}\nlats_vent={lat}\nlongs_vent={lon}\n")
            f.write("start_day_str=01/01/2026 00:00\nend_day_str=01/05/2026 23:59\nfilter_frp=35\nfilter_track=0.5\n")
            f.write("include_reference_radius=True\nref_radius_m=5000\ninclude_shapefile=False\nshapefile_path=\n")
            f.write("include_reference_waypoint=False\nwpt_names=\nwpt_lats=0.0\nwpt_lons=0.0\nwpt_symbols=circle\n")

    initial_waypoints = [{'name': '', 'lat': 0.0, 'lon': 0.0, 'symbol': 'circle'}]
    return (selected_volcano, lat, lon, 35, 0.5, 5000,
            "01/01/2026", "01/05/2026", "",
            initial_waypoints,
            f"New volcano project initialized: {selected_volcano}",
            f"LavaFlow Mapper Suite: {selected_volcano}")


@app.callback(
    [Output('cfg-volcano', 'value', allow_duplicate=True),
     Output('cfg-lat-vent', 'value', allow_duplicate=True),
     Output('cfg-lon-vent', 'value', allow_duplicate=True),
     Output('cfg-frp', 'value', allow_duplicate=True),
     Output('cfg-track', 'value', allow_duplicate=True),
     Output('cfg-frp-mode', 'value', allow_duplicate=True),
     Output('cfg-chk-shp', 'value', allow_duplicate=True),
     Output('cfg-shp-path', 'value', allow_duplicate=True),
     Output('cfg-map-key', 'value', allow_duplicate=True),
     Output('cfg-date-start', 'value', allow_duplicate=True),
     Output('cfg-date-end', 'value', allow_duplicate=True),
     Output('cfg-chk-rad', 'value', allow_duplicate=True),
     Output('cfg-radius-m', 'value', allow_duplicate=True),
     Output('cfg-chk-wpt', 'value', allow_duplicate=True),
     Output('wpt-list-store', 'data', allow_duplicate=True),
     Output('config-save-status', 'children', allow_duplicate=True),
     Output('main-header-title', 'children', allow_duplicate=True)],
    Input('cfg-load-project', 'value'),
    prevent_initial_call=True
)
def load_existing_project_cb(selected_volcano):
    if not selected_volcano: return [no_update] * 17
    with open("active_volcano.txt", "w") as f:
        f.write(selected_volcano)
    c = load_global_config()
    shp_v = ['True'] if c.get('include_shapefile') else []
    rad_v = ['True'] if c.get('include_reference_radius') else []
    wpt_v = ['True'] if c.get('include_reference_waypoint') else []
    sd = c.get('start_day_str', '01/01/2026 00:00').split()[0]
    ed = c.get('end_day_str', '01/05/2026 00:00').split()[0]
    display_name = get_display_name(selected_volcano)
    waypoints = parse_waypoints_from_config(c)

    return (c.get('volcano'), c.get('lats_vent'), c.get('longs_vent'),
            c.get('filter_frp'), c.get('filter_track'), c.get('frp_filter_mode', 'gt'),
            shp_v, c.get('shapefile_path'),
            c.get('map_key'), sd, ed, rad_v, c.get('ref_radius_m'), wpt_v,
            waypoints,
            f"Loaded project: {display_name}",
            f"LavaFlow Mapper Suite: {display_name}")


@app.callback(
    [Output("config-save-status", "children", allow_duplicate=True),
     Output('main-header-title', 'children', allow_duplicate=True)],
    Input("btn-save-config", "n_clicks"),
    [State('cfg-volcano', 'value'), State('cfg-lat-vent', 'value'), State('cfg-lon-vent', 'value'),
     State('cfg-date-start', 'value'), State('cfg-date-end', 'value'),
     State('cfg-frp', 'value'), State('cfg-frp-mode', 'value'), State('cfg-track', 'value'), State('cfg-map-key', 'value'),
     State('cfg-chk-rad', 'value'), State('cfg-radius-m', 'value'),
     State('cfg-chk-shp', 'value'), State('cfg-shp-path', 'value'),
     State('cfg-chk-wpt', 'value'),
     # Multi-waypoint values via pattern matching
     State({'type': 'wpt-name',   'index': ALL}, 'value'),
     State({'type': 'wpt-lat',    'index': ALL}, 'value'),
     State({'type': 'wpt-lon',    'index': ALL}, 'value'),
     State({'type': 'wpt-symbol', 'index': ALL}, 'value')],
    prevent_initial_call=True
)
def save_all(n, vol, latv, lonv, sd, ed, frp, frp_mode, trk, m_key,
             rad_chk, rad_m, shp_chk, shp_p, wpt_chk,
             wpt_names, wpt_lats, wpt_lons, wpt_syms):
    if n > 0:
        folder_name = vol.strip().replace(" ", "_")
        active_path = get_active_volcano_name() or ""

        if active_path.startswith(EXAMPLES_DIR):
            return (
                "⚠️ Examples are read-only. To create your own project, use the GVP Search above.",
                no_update
            )

        folder_path = os.path.join(PROJECTS_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        config_path = os.path.join(folder_path, f"config_{folder_name}.txt")

        try:
            datetime.strptime(sd.strip(), '%d/%m/%Y')
            s_d = sd.strip() + " 00:00"
        except:
            s_d = "01/01/2026 00:00"
        try:
            datetime.strptime(ed.strip(), '%d/%m/%Y')
            e_d = ed.strip() + " 23:59"
        except:
            e_d = "01/05/2026 23:59"

        # Serialize waypoints as ';'-separated lists for downstream modules
        names_str = ';'.join([str(w or '') for w in (wpt_names or [])])
        lats_str  = ';'.join([str(w if w is not None else 0.0) for w in (wpt_lats or [])])
        lons_str  = ';'.join([str(w if w is not None else 0.0) for w in (wpt_lons or [])])
        syms_str  = ';'.join([str(w or 'circle') for w in (wpt_syms or [])])

        with open(config_path, "w") as f:
            f.write(f"volcano={vol}\nlats_vent={latv}\nlongs_vent={lonv}\n")
            f.write(f"start_day_str={s_d}\nend_day_str={e_d}\nfilter_frp={frp}\nfrp_filter_mode={frp_mode}\nfilter_track={trk}\nmap_key={m_key}\n")
            f.write(f"include_reference_radius={'True' in (rad_chk or [])}\nref_radius_m={rad_m}\n")
            f.write(f"include_shapefile={'True' in (shp_chk or [])}\nshapefile_path={str(shp_p or '')}\n")
            f.write(f"include_reference_waypoint={'True' in (wpt_chk or [])}\n")
            f.write(f"wpt_names={names_str}\nwpt_lats={lats_str}\nwpt_lons={lons_str}\nwpt_symbols={syms_str}\n")

        with open("active_volcano.txt", "w") as f:
            f.write(folder_path)

        return f"✅ Research project saved: {vol}", f"LavaFlow Mapper Suite: {vol}"
    return no_update, no_update


@app.callback(Output("dl-output-log", "children"), Input("btn-run-download", "n_clicks"),
              [State('dl-date-picker', 'start_date'), State('dl-date-picker', 'end_date'), State('dl-radius', 'value')],
              prevent_initial_call=True)
def dl_cb(n, s, e, radius):
    if n > 0: return download_logic.process_download(s.split('T')[0], e.split('T')[0], radius or 10000)
    return ""


@app.callback([Output("out-stats-results", "children"), Output('store-stats-status', 'data')],
              Input("btn-run-stats", "n_clicks"), prevent_initial_call=True)
def stats_cb(n):
    if n > 0: return stats_module.get_layout(), {'run': True}
    return no_update, no_update


@app.callback([Output("out-mapper-results", "children"), Output('store-mapper-status', 'data')],
              Input("btn-run-mapper", "n_clicks"), prevent_initial_call=True)
def mapper_cb(n):
    if n > 0: return mapper_module.get_layout(), {'run': True}
    return no_update, no_update


@app.callback([Output("out-speed-results", "children"), Output('store-speed-status', 'data')],
              Input("btn-run-speed", "n_clicks"), prevent_initial_call=True)
def speed_cb(n):
    if n > 0: return speed_module.get_layout(), {'run': True}
    return no_update, no_update


# ==========================================
# 3. DATE QUICK-ADVANCE CALLBACKS
# ==========================================

@app.callback(
    Output('cfg-date-end', 'value', allow_duplicate=True),
    [Input('btn-date-plus1', 'n_clicks'),
     Input('btn-date-plus7', 'n_clicks')],
    State('cfg-date-end', 'value'),
    prevent_initial_call=True
)
def advance_end_date(n1, n7, current_end):
    from dash import ctx
    if not current_end:
        return no_update
    try:
        dt = datetime.strptime(current_end.strip(), '%d/%m/%Y')
    except ValueError:
        return no_update
    triggered = ctx.triggered_id
    if triggered == 'btn-date-plus1':
        dt += timedelta(days=1)
    elif triggered == 'btn-date-plus7':
        dt += timedelta(days=7)
    return dt.strftime('%d/%m/%Y')


@app.callback(
    [Output('cfg-date-start', 'style', allow_duplicate=True),
     Output('cfg-date-end', 'style', allow_duplicate=True),
     Output('cfg-date-validation', 'children')],
    [Input('cfg-date-start', 'value'),
     Input('cfg-date-end', 'value')],
    prevent_initial_call=True
)
def validate_dates(sd, ed):
    base_style = {'width': '130px', 'fontFamily': 'monospace', 'fontSize': '14px',
                  'padding': '6px 8px', 'borderRadius': '5px', 'marginRight': '12px'}
    ok_style  = {**base_style, 'border': '1px solid #27ae60'}
    err_style = {**base_style, 'border': '2px solid #e74c3c'}
    neu_style = {**base_style, 'border': '1px solid #ccc'}

    sd_ok = ed_ok = False
    sd_dt = ed_dt = None
    try:
        sd_dt = datetime.strptime((sd or '').strip(), '%d/%m/%Y'); sd_ok = True
    except ValueError:
        pass
    try:
        ed_dt = datetime.strptime((ed or '').strip(), '%d/%m/%Y'); ed_ok = True
    except ValueError:
        pass

    if sd_ok and ed_ok and ed_dt <= sd_dt:
        msg = html.Span("⚠️ End date must be after start date.", style={'color': '#e74c3c'})
        return err_style, err_style, msg

    if not sd and not ed:
        return neu_style, neu_style, ""

    s_style = ok_style if sd_ok else (err_style if sd else neu_style)
    e_style = ok_style if ed_ok else (err_style if ed else neu_style)

    if sd_ok and ed_ok:
        delta = (ed_dt - sd_dt).days
        msg = html.Span(f"✅ Period: {delta} days ({sd_dt.strftime('%d %b %Y')} → {ed_dt.strftime('%d %b %Y')})",
                        style={'color': '#27ae60'})
    elif not sd_ok and sd:
        msg = html.Span("⚠️ Start date: use DD/MM/YYYY format.", style={'color': '#e74c3c'})
    elif not ed_ok and ed:
        msg = html.Span("⚠️ End date: use DD/MM/YYYY format.", style={'color': '#e74c3c'})
    else:
        msg = ""
    return s_style, e_style, msg


# ==========================================
# 4. VOLCANO NAME HIGHLIGHT CALLBACK
# ==========================================

@app.callback(
    Output('cfg-volcano', 'style'),
    Input('cfg-volcano', 'value'),
    prevent_initial_call=True
)
def highlight_volcano_name(volcano_value):
    return volcano_input_style(volcano_value)


# ==========================================
# 5. DYNAMIC WAYPOINT CALLBACKS
# ==========================================

@app.callback(
    Output('wpt-container', 'children'),
    Input('wpt-list-store', 'data')
)
def render_waypoint_container(waypoints):
    """Rebuilds the waypoint rows from the store whenever it changes."""
    if not waypoints:
        return html.Div(
            "No waypoints. Click + Add Waypoint to add one.",
            style={'color': '#999', 'fontStyle': 'italic',
                   'padding': '12px', 'textAlign': 'center'}
        )
    return [render_waypoint_row(i, w) for i, w in enumerate(waypoints)]


@app.callback(
    Output('wpt-list-store', 'data', allow_duplicate=True),
    Input('btn-add-wpt', 'n_clicks'),
    [State({'type': 'wpt-name',   'index': ALL}, 'value'),
     State({'type': 'wpt-lat',    'index': ALL}, 'value'),
     State({'type': 'wpt-lon',    'index': ALL}, 'value'),
     State({'type': 'wpt-symbol', 'index': ALL}, 'value')],
    prevent_initial_call=True
)
def add_waypoint_cb(n, names, lats, lons, syms):
    """Reads current input values to preserve typed input, then appends a new empty waypoint."""
    waypoints = []
    for i in range(len(names)):
        waypoints.append({
            'name': names[i] or '',
            'lat':  lats[i] if lats[i] is not None else 0.0,
            'lon':  lons[i] if lons[i] is not None else 0.0,
            'symbol': syms[i] or 'circle',
        })
    waypoints.append({'name': '', 'lat': 0.0, 'lon': 0.0, 'symbol': 'circle'})
    return waypoints


@app.callback(
    Output('wpt-list-store', 'data', allow_duplicate=True),
    Input({'type': 'wpt-remove', 'index': ALL}, 'n_clicks'),
    [State({'type': 'wpt-name',   'index': ALL}, 'value'),
     State({'type': 'wpt-lat',    'index': ALL}, 'value'),
     State({'type': 'wpt-lon',    'index': ALL}, 'value'),
     State({'type': 'wpt-symbol', 'index': ALL}, 'value')],
    prevent_initial_call=True
)
def remove_waypoint_cb(n_clicks_list, names, lats, lons, syms):
    """Pattern-matched remove: drops the waypoint at the clicked index."""
    from dash import ctx
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return no_update
    # Only proceed if at least one button has actually been clicked
    if not any(n for n in (n_clicks_list or []) if n):
        return no_update
    remove_idx = ctx.triggered_id.get('index')
    if remove_idx is None:
        return no_update

    waypoints = []
    for i in range(len(names)):
        if i == remove_idx:
            continue
        waypoints.append({
            'name': names[i] or '',
            'lat':  lats[i] if lats[i] is not None else 0.0,
            'lon':  lons[i] if lons[i] is not None else 0.0,
            'symbol': syms[i] or 'circle',
        })
    return waypoints


if __name__ == '__main__':
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        Timer(1.5, lambda: webbrowser.open_new("http://127.0.0.1:9050/")).start()
    app.run(debug=True, port=9050, dev_tools_hot_reload=False)