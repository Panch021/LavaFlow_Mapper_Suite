import dash
from dash import dcc, html, Input, Output, State, no_update, ALL
import pandas as pd
import os
from datetime import datetime, date, timedelta

# Technical modules import
import FIRMS_download as download_logic
import Anomalies_count as anomalies_module
import FRP_Statistics as stats_module
import LavaFlow_mapper as mapper_module
import LavaFlow_animation as anim_module
import LavaFlow_speed as speed_module

# ==========================================
# 0. CONFIGURATION & DATA ENGINE
# ==========================================

# Load GVP database for auto-fill features
GVP_FILE = 'GVP_Volcano_List_Holocene.csv'
if os.path.exists(GVP_FILE):
    df_gvp = pd.read_csv(GVP_FILE)
    gvp_options = [{'label': row['Volcano Name'], 'value': row['Volcano Name']} for _, row in df_gvp.iterrows()]
else:
    df_gvp = pd.DataFrame()
    gvp_options = []


def load_global_config():
    """Load configuration parameters. Creates config.txt with defaults if missing."""
    # Default parameters for first-time usage or missing keys
    default_params = {
        'volcano': 'Volcano Name',
        'lats_vent': 0.0,
        'longs_vent': 0.0,
        'start_day_str': '01/01/2024 00:00',
        'end_day_str': '01/01/2026 00:00',
        'filter_frp': 0,
        'filter_track': 0.5,  # Default track filter set to 0.5
        'map_key': 'INSERT_YOUR_MAP_KEY_HERE',
        'include_reference_radius': True,
        'ref_radius_m': 3000,  # Default radius set to 3000 m
        'include_shapefile': False,
        'shapefile_path': '',
        'include_reference_waypoint': False,
        'wpt_names': 'Reference Point',
        'wpt_lats': '0.0',
        'wpt_lons': '0.0',
        'wpt_symbols': 'circle'
    }

    # Automatically create config.txt if it does not exist
    if not os.path.exists("config.txt"):
        with open("config.txt", "w") as f:
            for k, v in default_params.items():
                f.write(f"{k}={v}\n")
        return default_params

    # Load configuration from file
    config = {}
    with open("config.txt", "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                k, v = key.strip(), value.strip()

                # Handle waypoint lists
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

    # Ensure all default keys exist in the loaded dictionary
    final_config = default_params.copy()
    final_config.update(config)
    return final_config


def create_wpt_row(i, name="", lat=0.0, lon=0.0, symbol="circle"):
    """Creates a dynamic UI row for waypoint input."""
    return html.Div([
        dcc.Input(id={'type': 'wpt-name', 'index': i}, type='text', value=name, placeholder="Name",
                  style={'width': '150px', 'marginRight': '10px'}),
        dcc.Input(id={'type': 'wpt-lat', 'index': i}, type='number', value=lat, placeholder="Lat",
                  style={'width': '100px', 'marginRight': '10px'}),
        dcc.Input(id={'type': 'wpt-lon', 'index': i}, type='number', value=lon, placeholder="Lon",
                  style={'width': '100px', 'marginRight': '10px'}),
        dcc.Dropdown(id={'type': 'wpt-symbol', 'index': i}, value=symbol, clearable=False,
                     style={'width': '130px', 'marginRight': '10px'},
                     options=[{'label': '● Circle', 'value': 'circle'}, {'label': '■ Square', 'value': 'square'},
                              {'label': '◆ Diamond', 'value': 'diamond'}, {'label': '★ Star', 'value': 'star'}]),
        html.Button("❌", id={'type': 'btn-remove-wpt', 'index': i}, n_clicks=0,
                    style={'color': 'red', 'border': 'none', 'background': 'none', 'cursor': 'pointer'})
    ], id={'type': 'wpt-row', 'index': i}, style={'marginBottom': '10px', 'display': 'flex', 'alignItems': 'center'})


# Initial config load
cfg = load_global_config()
volcano_name = cfg.get('volcano', 'Volcano Name')

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = f"LavaFlow Suite - {volcano_name}"

# Register module callbacks
anim_module.register_callbacks(app)
anomalies_module.register_callbacks(app)

app.layout = html.Div([
    dcc.Store(id='store-stats-status', data={'run': False}, storage_type='session'),
    dcc.Store(id='store-mapper-status', data={'run': False}, storage_type='session'),
    dcc.Store(id='store-speed-status', data={'run': False}, storage_type='session'),
    dcc.Store(id='wpt-counter', data=30),

    html.Div([
        html.H1(id='main-header-title', children=f"LavaFlow Mapper Suite: {volcano_name}",
                style={'margin': '0', 'color': '#2c3e50'}),
    ], style={'padding': '20px', 'backgroundColor': 'white', 'borderBottom': '2px solid #eee'}),

    dcc.Tabs(id="suite-tabs", value='tab-config', persistence=True, children=[
        dcc.Tab(label='⚙️ 0. Global Config', value='tab-config'),
        dcc.Tab(label='🛰️ 1. FIRMS Download', value='tab-download'),
        dcc.Tab(label='📈 2. Anomalies Count', value='tab-anomalies'),
        dcc.Tab(label='📊 3. FRP Statistics', value='tab-stats'),
        dcc.Tab(label='🌋 4. LavaFlow Mapper', value='tab-mapper'),
        dcc.Tab(label='🗺️ 5. LavaFlow Propagation', value='tab-animation'),
        dcc.Tab(label='📈 6. Propagation Speed', value='tab-speed'),
    ]),
    html.Div(id='tabs-content-container', style={'padding': '20px'})
])


# ==========================================
# 1. TAB RENDERING LOGIC
# ==========================================
@app.callback(
    Output('tabs-content-container', 'children'),
    Input('suite-tabs', 'value'),
    [State('store-stats-status', 'data'),
     State('store-mapper-status', 'data'),
     State('store-speed-status', 'data')]
)
def render_tab(tab, stats_data, mapper_data, speed_data):
    current_cfg = load_global_config()

    if tab == 'tab-config':
        def to_list(val):
            if isinstance(val, list): return val
            return [val] if val is not None else []

        w_names = to_list(current_cfg.get('wpt_names', ["Reference Point"]))
        w_lats = to_list(current_cfg.get('wpt_lats', [0.0]))
        w_lons = to_list(current_cfg.get('wpt_lons', [0.0]))
        w_syms = to_list(current_cfg.get('wpt_symbols', ["circle"]))
        initial_rows = [create_wpt_row(i, w_names[i], w_lats[i], w_lons[i], w_syms[i]) for i in range(len(w_names))]

        return html.Div([
            html.Div([
                html.Div([
                    html.H4("Volcano & Vent Location", style={'color': '#2980b9'}),
                    html.Label([
                        "Search GVP Database: ",
                        html.A("[Source]", href="https://volcano.si.edu/volcanolist_holocene.cfm", target="_blank",
                               style={'fontSize': '11px', 'marginLeft': '5px'})
                    ], style={'fontWeight': 'bold', 'color': '#e67e22'}),
                    dcc.Dropdown(id='cfg-volcano-search', options=gvp_options, placeholder="Auto-fill from GVP...",
                                 style={'marginBottom': '10px'}),
                    html.Label("Volcano Name: "), dcc.Input(id='cfg-volcano', value=current_cfg.get('volcano'),
                                                            style={'width': '100%', 'marginBottom': '10px'}),
                    html.Div([
                        html.Label("Vent Lat: "),
                        dcc.Input(id='cfg-lat-vent', type='number', value=current_cfg.get('lats_vent'),
                                  style={'width': '80px', 'marginRight': '10px'}),
                        html.Label("Vent Long: "),
                        dcc.Input(id='cfg-lon-vent', type='number', value=current_cfg.get('longs_vent'),
                                  style={'width': '80px'})
                    ]),
                    html.Label("Analysis Period: ", style={'marginTop': '10px', 'display': 'block'}),
                    dcc.DatePickerRange(id='cfg-dates', display_format='DD/MM/YYYY',
                                        start_date=datetime.strptime(current_cfg.get('start_day_str').split()[0],
                                                                     '%d/%m/%Y'),
                                        end_date=datetime.strptime(current_cfg.get('end_day_str').split()[0],
                                                                   '%d/%m/%Y'))
                ], style={'flex': '1.5', 'padding': '20px', 'border': '1px solid #eee', 'marginRight': '15px',
                          'borderRadius': '10px'}),
                html.Div([
                    html.H4("Threshold Filters", style={'color': '#2980b9'}),
                    html.Label([
                        "FRP filter (MW): ",
                        html.A("[Ref]", href="https://doi.org/10.3390/rs14143483", target="_blank",
                               style={'fontSize': '11px'})
                    ]),
                    dcc.Input(id='cfg-frp', type='number', value=current_cfg.get('filter_frp'),
                              style={'width': '80px', 'display': 'block', 'marginBottom': '10px'}),
                    html.Label([
                        "Track: ",
                        html.A("[Ref]", href="https://www.mdpi.com/2072-4292/9/10/974", target="_blank",
                               style={'fontSize': '11px'})
                    ]),
                    dcc.Input(id='cfg-track', type='number', value=current_cfg.get('filter_track'), step=0.1,
                              style={'width': '80px', 'display': 'block'})
                ], style={'flex': '1', 'padding': '20px', 'border': '1px solid #eee', 'borderRadius': '10px'}),
            ], style={'display': 'flex', 'marginBottom': '20px'}),
            html.Div([
                html.H4("API Credentials", style={'color': '#2980b9'}),
                html.Label([
                    "FIRMS API MAP_KEY: ",
                    html.A("[Get API Key]", href="https://firms.modaps.eosdis.nasa.gov/api/map_key/", target="_blank",
                           style={'fontSize': '11px'})
                ]),
                dcc.Input(id='cfg-map-key', value=current_cfg.get('map_key'),
                          style={'width': '400px', 'fontFamily': 'monospace', 'display': 'block', 'marginTop': '5px'})
            ], style={'padding': '20px', 'border': '1px solid #eee', 'marginBottom': '20px', 'borderRadius': '10px',
                      'backgroundColor': '#fcfcfc'}),
            html.Div([
                html.H4("Geospatial Layers & Reference Waypoints", style={'color': '#2980b9'}),
                html.Div([
                    dcc.Checklist(id='cfg-chk-rad', options=[{'label': ' Include Radius', 'value': 'True'}],
                                  value=['True'] if current_cfg.get('include_reference_radius') else []),
                    dcc.Input(id='cfg-radius-m', type='number', value=current_cfg.get('ref_radius_m'),
                              style={'width': '100px', 'marginLeft': '10px'})
                ], style={'marginBottom': '15px'}),
                html.Div([
                    dcc.Checklist(id='cfg-chk-shp', options=[{'label': ' Include Shapefile', 'value': 'True'}],
                                  value=['True'] if current_cfg.get('include_shapefile') else []),
                    dcc.Input(id='cfg-shp-path', value=current_cfg.get('shapefile_path'),
                              placeholder="Path/to/shapefile.shp", style={'width': '300px', 'marginLeft': '10px'})
                ], style={'marginBottom': '20px'}),
                html.Label("Waypoints:", style={'fontWeight': 'bold'}),
                dcc.Checklist(id='cfg-chk-wpt', options=[{'label': ' Show Waypoints', 'value': 'True'}],
                              value=['True'] if current_cfg.get('include_reference_waypoint') else []),
                html.Div(id='wpt-list-container', children=initial_rows, style={'marginTop': '10px'}),
                html.Button("➕ ADD NEW WAYPOINT", id="btn-add-wpt", n_clicks=0,
                            style={'marginTop': '10px', 'backgroundColor': '#3498db', 'color': 'white',
                                   'border': 'none', 'padding': '8px 15px', 'borderRadius': '5px'})
            ], style={'padding': '20px', 'border': '1px solid #eee', 'marginBottom': '20px', 'borderRadius': '10px'}),
            html.Button("SAVE ALL PARAMETERS", id="btn-save-config", n_clicks=0,
                        style={'padding': '15px 30px', 'backgroundColor': '#e67e22', 'color': 'white',
                               'fontWeight': 'bold', 'border': 'none', 'borderRadius': '5px'}),
            html.Div(id="config-save-status", style={'marginTop': '20px', 'fontWeight': 'bold', 'color': '#27ae60'})
        ])

    elif tab == 'tab-download':
        default_dl_radius = current_cfg.get('ref_radius_m', 3000)
        return html.Div([
            html.H3("🛰️ Step 1: FIRMS Data Downloader"),
            html.Div([
                html.P("Updates root historical files. Select the spatial and temporal range."),
                html.Div([
                    html.Label("Download Radius (meters):", style={'fontWeight': 'bold'}),
                    dcc.Input(id='dl-radius', type='number', value=default_dl_radius,
                              style={'width': '150px', 'display': 'block', 'margin': '10px auto'})
                ], style={'marginBottom': '20px'}),
                html.Label("Select Download Period:", style={'fontWeight': 'bold'}),
                html.Br(),
                dcc.DatePickerRange(id='dl-date-picker', start_date=date.today() - timedelta(days=2),
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
        return anomalies_module.get_layout()

    elif tab == 'tab-stats':
        initial_content = stats_module.get_layout() if stats_data['run'] else html.P(
            "No results yet. Click run to generate.")
        return html.Div([
            html.Button("RUN FRP STATISTICS", id="btn-run-stats", n_clicks=0,
                        style={'padding': '10px 20px', 'backgroundColor': '#3498db', 'color': 'white', 'border': 'none',
                               'borderRadius': '5px', 'marginBottom': '20px'}),
            dcc.Loading(html.Div(id="out-stats-results", children=initial_content))
        ], style={'textAlign': 'center'})

    elif tab == 'tab-mapper':
        initial_content = mapper_module.get_layout() if mapper_data['run'] else html.P(
            "No results yet. Click run to generate.")
        return html.Div([
            html.Button("RUN MAPPER ENGINE", id="btn-run-mapper", n_clicks=0,
                        style={'padding': '10px 20px', 'backgroundColor': '#27ae60', 'color': 'white', 'border': 'none',
                               'borderRadius': '5px'}),
            dcc.Loading(html.Div(id="out-mapper-results", children=initial_content))
        ], style={'textAlign': 'center'})

    elif tab == 'tab-animation':
        return anim_module.get_layout()

    elif tab == 'tab-speed':
        initial_content = speed_module.get_layout() if speed_data['run'] else html.P(
            "No results yet. Run Mapper first, then click calculate.")
        return html.Div([
            html.Button("CALCULATE PROPAGATION SPEED", id="btn-run-speed", n_clicks=0,
                        style={'padding': '10px 20px', 'backgroundColor': '#9b59b6', 'color': 'white', 'border': 'none',
                               'borderRadius': '5px', 'marginBottom': '20px'}),
            dcc.Loading(html.Div(id="out-speed-results", children=initial_content))
        ], style={'textAlign': 'center'})


# ==========================================
# 2. CALLBACKS
# ==========================================

@app.callback(
    [Output('cfg-volcano', 'value'), Output('cfg-lat-vent', 'value'), Output('cfg-lon-vent', 'value')],
    Input('cfg-volcano-search', 'value'), prevent_initial_call=True
)
def autofill_gvp(sel):
    if sel and not df_gvp.empty:
        match = df_gvp[df_gvp['Volcano Name'] == sel].iloc[0]
        return match['Volcano Name'], match['Latitude'], match['Longitude']
    return no_update, no_update, no_update


@app.callback(
    Output('wpt-list-container', 'children'),
    [Input('btn-add-wpt', 'n_clicks'), Input({'type': 'btn-remove-wpt', 'index': ALL}, 'n_clicks')],
    [State('wpt-list-container', 'children'), State('wpt-counter', 'data')],
    prevent_initial_call=True
)
def manage_wpt(n_add, n_rem, cur, count):
    ctx = dash.callback_context
    trig = ctx.triggered[0]['prop_id']
    if "btn-add-wpt" in trig: return (cur or []) + [create_wpt_row(count + 1)]
    if "btn-remove-wpt" in trig:
        idx = eval(trig.split('.')[0])['index']
        return [r for r in cur if f"'index': {idx}" not in str(r)]
    return no_update


@app.callback(
    [Output("config-save-status", "children"), Output("main-header-title", "children"), Output('wpt-counter', 'data')],
    Input("btn-save-config", "n_clicks"),
    [State('cfg-volcano', 'value'), State('cfg-lat-vent', 'value'), State('cfg-lon-vent', 'value'),
     State('cfg-dates', 'start_date'), State('cfg-dates', 'end_date'),
     State('cfg-frp', 'value'), State('cfg-track', 'value'), State('cfg-map-key', 'value'),
     State('cfg-chk-rad', 'value'), State('cfg-radius-m', 'value'),
     State('cfg-chk-shp', 'value'), State('cfg-shp-path', 'value'),
     State('cfg-chk-wpt', 'value'),
     State({'type': 'wpt-name', 'index': ALL}, 'value'),
     State({'type': 'wpt-lat', 'index': ALL}, 'value'),
     State({'type': 'wpt-lon', 'index': ALL}, 'value'),
     State({'type': 'wpt-symbol', 'index': ALL}, 'value')],
    prevent_initial_call=True
)
def save_all(n, vol, latv, lonv, sd, ed, frp, trk, m_key, rad_chk, rad_m, shp_chk, shp_p, wpt_chk, w_n, w_la, w_lo,
             w_s):
    if n > 0:
        s_d = datetime.strptime(sd.split('T')[0], '%Y-%m-%d').strftime('%d/%m/%Y 00:00')
        e_d = datetime.strptime(ed.split('T')[0], '%Y-%m-%d').strftime('%d/%m/%Y 00:00')
        new_params = {
            'volcano': vol, 'lats_vent': latv, 'longs_vent': lonv,
            'start_day_str': s_d, 'end_day_str': e_d,
            'filter_frp': frp, 'filter_track': trk, 'map_key': m_key,
            'include_reference_radius': 'True' in rad_chk, 'ref_radius_m': rad_m,
            'include_shapefile': 'True' in shp_chk, 'shapefile_path': str(shp_p) if shp_p else "",
            'include_reference_waypoint': 'True' in wpt_chk,
            'wpt_names': ",".join(filter(None, w_n)),
            'wpt_lats': ",".join(map(str, filter(None, w_la))),
            'wpt_lons': ",".join(map(str, filter(None, w_lo))),
            'wpt_symbols': ",".join(filter(None, w_s))
        }
        with open("config.txt", "w") as f:
            for k, v in new_params.items(): f.write(f"{k}={v}\n")
        return "Config Saved!", f"LavaFlow Suite: {vol}", len(w_n) + 30
    return no_update, no_update, no_update


@app.callback(
    Output("dl-output-log", "children"),
    Input("btn-run-download", "n_clicks"),
    [State('dl-date-picker', 'start_date'),
     State('dl-date-picker', 'end_date'),
     State('dl-radius', 'value')],
    prevent_initial_call=True
)
def dl_cb(n, s, e, radius):
    if n > 0:
        rd = radius if radius is not None else 3000
        return html.Div(download_logic.process_download(s.split('T')[0], e.split('T')[0], rd))
    return ""


@app.callback(
    [Output("out-stats-results", "children"), Output('store-stats-status', 'data')],
    Input("btn-run-stats", "n_clicks"),
    prevent_initial_call=True
)
def stats_cb(n):
    if n > 0:
        return stats_module.get_layout(), {'run': True}
    return no_update, no_update


@app.callback(
    [Output("out-mapper-results", "children"), Output('store-mapper-status', 'data')],
    Input("btn-run-mapper", "n_clicks"),
    prevent_initial_call=True
)
def mapper_cb(n):
    if n > 0:
        return mapper_module.get_layout(), {'run': True}
    return no_update, no_update


@app.callback(
    [Output("out-speed-results", "children"), Output('store-speed-status', 'data')],
    Input("btn-run-speed", "n_clicks"),
    prevent_initial_call=True
)
def speed_cb(n):
    if n > 0:
        return speed_module.get_layout(), {'run': True}
    return no_update, no_update


if __name__ == '__main__':
    app.run(debug=True, port=8050, dev_tools_hot_reload=False)
