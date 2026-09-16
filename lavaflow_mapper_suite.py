import dash
from dash import dcc, html, Input, Output, State, no_update, ALL
import pandas as pd
import os
import webbrowser
from threading import Timer
from datetime import datetime, date, timedelta

# Shared helpers
import lavaflow_common as lfc

# Technical modules
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

EXAMPLES_DIR = lfc.EXAMPLES_DIR
PROJECTS_DIR = lfc.PROJECTS_DIR
os.makedirs(PROJECTS_DIR, exist_ok=True)

get_active_volcano_name = lfc.get_active_folder
is_example_path = lfc.is_example_path
load_global_config = lfc.load_global_config


def get_display_name(folder_path):
    if not folder_path:
        return None
    return os.path.basename(folder_path).replace("_", " ")


def save_button_class(is_example):
    return "lf-btn lf-btn-warn" if not is_example else "lf-btn"


def volcano_input_style(volcano_value):
    """Highlight the volcano name input once a real volcano has been selected."""
    has_volcano = bool(volcano_value) and str(volcano_value).strip() not in ('', 'Volcano Name')
    base = {'width': '100%'}
    if has_volcano:
        return {**base, 'border': '2px solid #27ae60', 'backgroundColor': '#eafaf1', 'fontWeight': 'bold'}
    return base


# ==========================================
# 0b. WAYPOINT EDITOR HELPERS
# ==========================================

def parse_waypoints_for_editor(c):
    """Waypoints for the Global Config editor. Never invents 0,0 coordinates:
    an empty project shows a single blank row."""
    wpts = lfc.parse_waypoints_from_config(c, keep_empty=True)
    if not wpts:
        wpts = [{'name': '', 'lat': None, 'lon': None, 'symbol': 'circle'}]
    return wpts


def render_waypoint_row(idx, wpt):
    return html.Div([
        html.Div([
            html.Label(f"Waypoint {idx + 1} – name", className='lf-label'),
            dcc.Input(id={'type': 'wpt-name', 'index': idx}, type='text',
                      value=wpt.get('name', ''), placeholder='e.g. Vent NW', style={'width': '100%'})
        ]),
        html.Div([
            html.Label("Latitude", className='lf-label'),
            dcc.Input(id={'type': 'wpt-lat', 'index': idx}, type='number',
                      value=wpt.get('lat'), placeholder='decimal °', style={'width': '100%'})
        ]),
        html.Div([
            html.Label("Longitude", className='lf-label'),
            dcc.Input(id={'type': 'wpt-lon', 'index': idx}, type='number',
                      value=wpt.get('lon'), placeholder='decimal °', style={'width': '100%'})
        ]),
        html.Div([
            html.Label("Symbol", className='lf-label'),
            dcc.Dropdown(id={'type': 'wpt-symbol', 'index': idx},
                         value=wpt.get('symbol', 'circle'), clearable=False,
                         options=[{'label': '● Circle', 'value': 'circle'},
                                  {'label': '▲ Triangle', 'value': 'triangle'},
                                  {'label': '■ Square', 'value': 'square'}])
        ]),
        html.Div([
            html.Button("Remove", id={'type': 'wpt-remove', 'index': idx}, n_clicks=0,
                        className='lf-btn lf-btn-ghost lf-btn-sm')
        ], style={'flex': '0 0 auto', 'minWidth': '0'}),
    ], className='lf-wpt-row')


def list_existing_projects():
    """Scans examples/ and projects/ for valid volcano config files."""
    projects = []
    for base_dir, tag in [(PROJECTS_DIR, ""), (EXAMPLES_DIR, "  (example)")]:
        if not os.path.isdir(base_dir):
            continue
        for item in sorted(os.listdir(base_dir)):
            folder_path = os.path.join(base_dir, item)
            if not os.path.isdir(folder_path) or item.startswith("."):
                continue
            if os.path.exists(os.path.join(folder_path, f"config_{item}.txt")):
                projects.append({'label': f"{item.replace('_', ' ')}{tag}", 'value': folder_path})
    return sorted(projects, key=lambda x: x['label'])


def write_config_file(config_path, vol, latv, lonv, s_d, e_d, frp, frp_mode, trk, m_key,
                      rad_on, rad_m, shp_on, shp_p, wpt_on, wpts):
    names_str = ';'.join(str(w.get('name') or '') for w in wpts)
    lats_str = ';'.join('' if w.get('lat') is None else str(w['lat']) for w in wpts)
    lons_str = ';'.join('' if w.get('lon') is None else str(w['lon']) for w in wpts)
    syms_str = ';'.join(str(w.get('symbol') or 'circle') for w in wpts)
    with open(config_path, "w", encoding='utf-8') as f:
        f.write(f"volcano={vol}\nlats_vent={latv}\nlongs_vent={lonv}\n")
        f.write(f"start_day_str={s_d}\nend_day_str={e_d}\n")
        f.write(f"filter_frp={frp}\nfrp_filter_mode={frp_mode}\nfilter_track={trk}\nmap_key={m_key}\n")
        f.write(f"include_reference_radius={bool(rad_on)}\nref_radius_m={rad_m}\n")
        f.write(f"include_shapefile={bool(shp_on)}\nshapefile_path={shp_p or ''}\n")
        f.write(f"include_reference_waypoint={bool(wpt_on)}\n")
        f.write(f"wpt_names={names_str}\nwpt_lats={lats_str}\nwpt_lons={lons_str}\nwpt_symbols={syms_str}\n")


# ==========================================
# APP
# ==========================================
app = dash.Dash(
    __name__, suppress_callback_exceptions=True,
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}],
)
app.title = "LavaFlow Suite"

active_v = get_active_volcano_name()
active_v_display = get_display_name(active_v)
header_display = f"LavaFlow Mapper Suite: {active_v_display}" if active_v_display else "LavaFlow Mapper Suite"

anim_module.register_callbacks(app)
anomalies_module.register_callbacks(app)
mapper_module.register_callbacks(app)
speed_module.register_callbacks(app)
export_module.register_callbacks(app)

app.layout = html.Div([
    dcc.Store(id='store-stats-status', data={'run': False}, storage_type='session'),
    dcc.Store(id='store-mapper-status', data={'run': False}, storage_type='session'),
    dcc.Store(id='store-speed-status', data={'run': False}, storage_type='session'),

    html.Div([html.H1(id='main-header-title', children=header_display)], className='lf-header'),

    dcc.Tabs(id="suite-tabs", value='tab-config', persistence=True, persistence_type='memory', children=[
        dcc.Tab(label='1. Global Config', value='tab-config'),
        dcc.Tab(label='2. FIRMS Download', value='tab-download'),
        dcc.Tab(label='3. Anomalies Count', value='tab-anomalies'),
        dcc.Tab(label='4. FRP Statistics', value='tab-stats'),
        dcc.Tab(label='5. LavaFlow Mapper', value='tab-mapper'),
        dcc.Tab(label='6. LavaFlow Propagation', value='tab-animation'),
        dcc.Tab(label='7. Propagation Speed', value='tab-speed'),
        dcc.Tab(label='8. Export Report', value='tab-export'),
    ]),
    html.Div(id='tabs-content-container', className='lf-content')
])


# ==========================================
# 1. TAB RENDERING
# ==========================================
def render_config_tab(c):
    existing_projects = list_existing_projects()
    active_path = get_active_volcano_name() or ""
    is_example = is_example_path(active_path)
    initial_waypoints = parse_waypoints_for_editor(c)
    sd_val = str(c.get('start_day_str', '')).split()[0] if c.get('start_day_str') else ''
    ed_val = str(c.get('end_day_str', '')).split()[0] if c.get('end_day_str') else ''

    date_style = {'width': '130px', 'fontFamily': 'monospace'}

    return html.Div([
        # ---- Row 1: project & period | filters & API ----
        html.Div([
            html.Div([
                html.H4("Project"),
                html.Label("Load an existing project", className='lf-label'),
                dcc.Dropdown(id='cfg-load-project', options=existing_projects, value=active_path or None,
                             placeholder="Select project..."),
                html.Label(["Or create a new one from the GVP catalogue ",
                            html.A("[source]", href="https://volcano.si.edu/volcanolist_holocene.cfm",
                                   target="_blank", className='lf-muted')], className='lf-label'),
                dcc.Dropdown(id='cfg-volcano-search', options=gvp_options, placeholder="Search volcano name..."),

                html.Label("Volcano name", className='lf-label'),
                dcc.Input(id='cfg-volcano', value=c.get('volcano'), style=volcano_input_style(c.get('volcano'))),
                html.Div([
                    html.Div([html.Label("Vent latitude", className='lf-label'),
                              dcc.Input(id='cfg-lat-vent', type='number', value=c.get('lats_vent'),
                                        style={'width': '150px'})]),
                    html.Div([html.Label("Vent longitude", className='lf-label'),
                              dcc.Input(id='cfg-lon-vent', type='number', value=c.get('longs_vent'),
                                        style={'width': '150px'})]),
                ], className='lf-inline'),

                html.Label("Analysis period (DD/MM/YYYY)", className='lf-label'),
                html.Div([
                    html.Div([html.Span("Start", className='lf-muted'), html.Br(),
                              dcc.Input(id='cfg-date-start', type='text', debounce=True, value=sd_val,
                                        placeholder='DD/MM/YYYY', style=date_style)]),
                    html.Div([html.Span("End", className='lf-muted'), html.Br(),
                              dcc.Input(id='cfg-date-end', type='text', debounce=True, value=ed_val,
                                        placeholder='DD/MM/YYYY', style=date_style)]),
                    html.Div([html.Span(" ", className='lf-muted'), html.Br(),
                              html.Button("+1 d", id='btn-date-plus1', n_clicks=0, className='lf-btn lf-btn-ghost lf-btn-sm',
                                          title="Advance end date one day", style={'marginRight': '6px'}),
                              html.Button("+7 d", id='btn-date-plus7', n_clicks=0, className='lf-btn lf-btn-ghost lf-btn-sm',
                                          title="Advance end date one week")]),
                ], className='lf-inline'),
                html.Div(id='cfg-date-validation', className='lf-muted', style={'minHeight': '16px', 'marginTop': '4px'}),
            ], className='lf-card lf-col'),

            html.Div([
                html.H4("Filters"),
                html.Label(["FRP threshold (MW) ",
                            html.A("[ref]", href="https://doi.org/10.3390/rs14143483", target="_blank", className='lf-muted')],
                           className='lf-label'),
                dcc.RadioItems(id='cfg-frp-mode',
                               options=[{'label': ' ≥ threshold (lava flows)', 'value': 'gt'},
                                        {'label': ' ≤ threshold (other pyroclastic material)', 'value': 'lt'}],
                               value=c.get('frp_filter_mode', 'gt'), labelStyle={'display': 'block'}),
                dcc.Input(id='cfg-frp', type='number', value=c.get('filter_frp'), style={'width': '100px', 'marginTop': '6px'}),
                html.Label(["Track (max. pixel size) ",
                            html.A("[ref]", href="https://www.mdpi.com/2072-4292/9/10/974", target="_blank", className='lf-muted')],
                           className='lf-label'),
                dcc.Input(id='cfg-track', type='number', value=c.get('filter_track'), step=0.1, style={'width': '100px'}),

                html.H4("FIRMS API", style={'marginTop': '18px'}),
                html.Label(["MAP_KEY ",
                            html.A("[get a key]", href="https://firms.modaps.eosdis.nasa.gov/api/map_key/",
                                   target="_blank", className='lf-muted')], className='lf-label'),
                dcc.Input(id='cfg-map-key', value=c.get('map_key'), style={'width': '100%', 'fontFamily': 'monospace'}),
            ], className='lf-card lf-col'),
        ], className='lf-row'),

        # ---- Row 2: optional layers ----
        html.Div([
            html.H4("Optional map layers"),
            html.P("These layers are off by default. Enable them once the values below are meaningful for your case study.",
                   className='lf-note'),
            html.Div([
                dcc.Checklist(id='cfg-chk-rad', options=[{'label': ' Reference radius (m)', 'value': 'True'}],
                              value=['True'] if c.get('include_reference_radius') else []),
                dcc.Input(id='cfg-radius-m', type='number', value=c.get('ref_radius_m'), style={'width': '140px'}),
            ], className='lf-inline', style={'marginBottom': '8px'}),
            html.Div([
                dcc.Checklist(id='cfg-chk-shp', options=[{'label': ' Shapefile (inside the project folder)', 'value': 'True'}],
                              value=['True'] if c.get('include_shapefile') else []),
                dcc.Input(id='cfg-shp-path', value=c.get('shapefile_path'), placeholder="name.shp",
                          style={'width': 'min(360px, 100%)'}),
            ], className='lf-inline', style={'marginBottom': '12px'}),

            html.Div([
                dcc.Checklist(id='cfg-chk-wpt', options=[{'label': ' Reference waypoints', 'value': 'True'}],
                              value=['True'] if c.get('include_reference_waypoint') else []),
                html.Button("+ Add waypoint", id='btn-add-wpt', n_clicks=0, className='lf-btn lf-btn-ghost lf-btn-sm'),
            ], className='lf-inline', style={'marginBottom': '8px'}),
            dcc.Store(id='wpt-list-store', data=initial_waypoints),
            html.Div(id='wpt-container'),
            html.P("Waypoints without coordinates are ignored, so the map always stays centred on the vent.",
                   className='lf-muted'),
        ], className='lf-card'),

        html.Div([
            html.Button("SAVE ALL PARAMETERS", id="btn-save-config", n_clicks=0, disabled=is_example,
                        className=save_button_class(is_example)),
            html.Span("Example project — read only. Create your own project from the GVP catalogue." if is_example else "",
                      id='example-readonly-msg', className='lf-muted', style={'marginLeft': '12px'}),
        ], className='lf-inline'),
        html.Div(id="config-save-status", style={'marginTop': '10px', 'fontWeight': '600', 'color': '#27ae60'})
    ])


@app.callback(
    Output('tabs-content-container', 'children'),
    Input('suite-tabs', 'value'),
    [State('store-stats-status', 'data'), State('store-mapper-status', 'data'),
     State('store-speed-status', 'data')]
)
def render_tab(tab, stats_data, mapper_data, speed_data):
    c = load_global_config()

    if tab == 'tab-config':
        return render_config_tab(c)

    elif tab == 'tab-download':
        return html.Div([
            html.Div([
                html.H3("FIRMS data downloader"),
                html.P(["Updates the project's FIRMS records. Large ranges are split into 5-day chunks. "
                        "The API only serves the previous year; for older records use the ",
                        html.A("FIRMS Download Service", href="https://firms.modaps.eosdis.nasa.gov/download/",
                               target="_blank"), "."], className='lf-note'),
                html.Label("Download radius (m)", className='lf-label'),
                dcc.Input(id='dl-radius', type='number', value=c.get('ref_radius_m', 10000), style={'width': '150px'}),
                html.Label("Date range", className='lf-label'),
                dcc.DatePickerRange(id='dl-date-picker', start_date=date.today() - timedelta(days=4),
                                    end_date=date.today(), display_format='YYYY-MM-DD'),
                html.Br(), html.Br(),
                html.Button("START DOWNLOAD", id="btn-run-download", n_clicks=0, className='lf-btn lf-btn-warn'),
            ], className='lf-card', style={'maxWidth': '620px', 'margin': '0 auto'}),
            dcc.Loading(html.Div(id="dl-output-log",
                                 style={'marginTop': '16px', 'whiteSpace': 'pre-line', 'fontFamily': 'monospace',
                                        'fontSize': '12px'}))
        ])

    elif tab == 'tab-anomalies':
        start_dt, end_dt = lfc.get_period(c)
        if pd.isna(start_dt) or pd.isna(end_dt):
            start_dt, end_dt = datetime(2026, 1, 1), datetime(2026, 5, 1)
        return anomalies_module.get_layout(start_date=start_dt, end_date=end_dt)

    elif tab == 'tab-stats':
        initial_content = stats_module.get_layout() if stats_data['run'] else html.P(
            "No results yet. Click run to generate the statistics.", className='lf-note')
        return html.Div([html.Button("RUN FRP STATISTICS", id="btn-run-stats", n_clicks=0, className='lf-btn'),
                         dcc.Loading(html.Div(id="out-stats-results", children=initial_content,
                                              style={'marginTop': '14px'}))])

    elif tab == 'tab-mapper':
        initial_content = mapper_module.get_layout() if mapper_data['run'] else html.P(
            "No results yet. Click run to generate the map.", className='lf-note')
        return html.Div([html.Button("RUN MAPPER ENGINE", id="btn-run-mapper", n_clicks=0, className='lf-btn lf-btn-ok'),
                         dcc.Loading(html.Div(id="out-mapper-results", children=initial_content,
                                              style={'marginTop': '14px'}))])

    elif tab == 'tab-animation':
        return anim_module.get_layout()

    elif tab == 'tab-speed':
        initial_content = speed_module.get_layout() if speed_data['run'] else html.P(
            "No results yet. Run the Mapper first, then calculate the speed.", className='lf-note')
        return html.Div([html.Button("CALCULATE SPEED", id="btn-run-speed", n_clicks=0,
                                     className='lf-btn', style={'backgroundColor': '#8e44ad'}),
                         dcc.Loading(html.Div(id="out-speed-results", children=initial_content,
                                              style={'marginTop': '14px'}))])

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
     Output('cfg-chk-rad', 'value', allow_duplicate=True),
     Output('cfg-chk-shp', 'value', allow_duplicate=True),
     Output('cfg-chk-wpt', 'value', allow_duplicate=True),
     Output('cfg-date-start', 'value', allow_duplicate=True),
     Output('cfg-date-end', 'value', allow_duplicate=True),
     Output('cfg-shp-path', 'value', allow_duplicate=True),
     Output('wpt-list-store', 'data', allow_duplicate=True),
     Output('config-save-status', 'children', allow_duplicate=True),
     Output('main-header-title', 'children', allow_duplicate=True),
     Output('cfg-load-project', 'options', allow_duplicate=True),
     Output('cfg-load-project', 'value', allow_duplicate=True)],
    Input('cfg-volcano-search', 'value'),
    State('cfg-map-key', 'value'),
    prevent_initial_call=True
)
def gvp_search_cb(selected_volcano, current_key):
    """GVP search: creates a new project folder inside projects/ with safe defaults
    (optional layers OFF, no placeholder waypoints) and makes it active."""
    if not selected_volcano or df_gvp.empty:
        return [no_update] * 17
    row = df_gvp[df_gvp['Volcano Name'] == selected_volcano].iloc[0]
    lat, lon = float(row['Latitude']), float(row['Longitude'])
    folder_name = lfc.safe_name(selected_volcano.strip().replace(" ", "_"))
    folder_path = os.path.join(PROJECTS_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    lfc.set_active_folder(folder_path)
    config_path = lfc.config_path_for(folder_path)

    d = lfc.DEFAULT_CONFIG
    key = current_key if current_key and current_key != d['map_key'] else d['map_key']
    if not os.path.exists(config_path):
        write_config_file(config_path, selected_volcano, lat, lon, d['start_day_str'], d['end_day_str'],
                          d['filter_frp'], d['frp_filter_mode'], d['filter_track'], key,
                          False, d['ref_radius_m'], False, '', False,
                          [{'name': '', 'lat': None, 'lon': None, 'symbol': 'circle'}])

    c = load_global_config()
    return (c.get('volcano'), c.get('lats_vent'), c.get('longs_vent'), c.get('filter_frp'), c.get('filter_track'),
            c.get('ref_radius_m'),
            ['True'] if c.get('include_reference_radius') else [],
            ['True'] if c.get('include_shapefile') else [],
            ['True'] if c.get('include_reference_waypoint') else [],
            str(c.get('start_day_str')).split()[0], str(c.get('end_day_str')).split()[0],
            c.get('shapefile_path', ''),
            parse_waypoints_for_editor(c),
            f"New project initialised: {selected_volcano} (saved in {folder_path})",
            f"LavaFlow Mapper Suite: {selected_volcano}",
            list_existing_projects(), folder_path)


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
def load_existing_project_cb(selected_project):
    if not selected_project or selected_project == (get_active_volcano_name() or ""):
        return [no_update] * 17
    lfc.set_active_folder(selected_project)
    c = load_global_config()
    display_name = get_display_name(selected_project)
    return (c.get('volcano'), c.get('lats_vent'), c.get('longs_vent'),
            c.get('filter_frp'), c.get('filter_track'), c.get('frp_filter_mode', 'gt'),
            ['True'] if c.get('include_shapefile') else [], c.get('shapefile_path', ''),
            c.get('map_key'),
            str(c.get('start_day_str')).split()[0], str(c.get('end_day_str')).split()[0],
            ['True'] if c.get('include_reference_radius') else [], c.get('ref_radius_m'),
            ['True'] if c.get('include_reference_waypoint') else [],
            parse_waypoints_for_editor(c),
            f"Loaded project: {display_name}",
            f"LavaFlow Mapper Suite: {display_name}")


@app.callback(
    [Output('btn-save-config', 'disabled'),
     Output('btn-save-config', 'className'),
     Output('example-readonly-msg', 'children')],
    [Input('cfg-volcano-search', 'value'),
     Input('cfg-load-project', 'value')],
    prevent_initial_call=True
)
def update_save_button_state(gvp_selected, loaded_project):
    from dash import ctx
    trigger = ctx.triggered_id
    if trigger == 'cfg-volcano-search' and gvp_selected:
        is_example = False
    elif trigger == 'cfg-load-project' and loaded_project:
        is_example = is_example_path(loaded_project)
    else:
        return no_update, no_update, no_update
    msg = "Example project — read only. Create your own project from the GVP catalogue." if is_example else ""
    return is_example, save_button_class(is_example), msg


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
     State({'type': 'wpt-name', 'index': ALL}, 'value'),
     State({'type': 'wpt-lat', 'index': ALL}, 'value'),
     State({'type': 'wpt-lon', 'index': ALL}, 'value'),
     State({'type': 'wpt-symbol', 'index': ALL}, 'value')],
    prevent_initial_call=True
)
def save_all(n, vol, latv, lonv, sd, ed, frp, frp_mode, trk, m_key,
             rad_chk, rad_m, shp_chk, shp_p, wpt_chk,
             wpt_names, wpt_lats, wpt_lons, wpt_syms):
    if not n:
        return no_update, no_update
    if not vol or not str(vol).strip() or str(vol).strip() == 'Volcano Name':
        return "Please enter a volcano name (or pick one from the GVP catalogue).", no_update
    if latv is None or lonv is None:
        return "Please enter the vent coordinates before saving.", no_update

    active_path = get_active_volcano_name() or ""
    if is_example_path(active_path):
        return ("Examples are read-only. To create your own project, use the GVP search above.", no_update)

    # Save into the active project folder; create one only if none is active.
    if active_path and os.path.isdir(active_path):
        folder_path = active_path
    else:
        folder_path = os.path.join(PROJECTS_DIR, lfc.safe_name(str(vol).strip().replace(" ", "_")))
        os.makedirs(folder_path, exist_ok=True)
    config_path = lfc.config_path_for(folder_path)

    try:
        datetime.strptime(sd.strip(), '%d/%m/%Y')
        s_d = sd.strip() + " 00:00"
    except Exception:
        return "Start date must be DD/MM/YYYY.", no_update
    try:
        datetime.strptime(ed.strip(), '%d/%m/%Y')
        e_d = ed.strip() + " 23:59"
    except Exception:
        return "End date must be DD/MM/YYYY.", no_update

    wpts = []
    for i in range(len(wpt_names or [])):
        wpts.append({'name': wpt_names[i] or '', 'lat': wpt_lats[i], 'lon': wpt_lons[i],
                     'symbol': wpt_syms[i] or 'circle'})
    wpt_on = 'True' in (wpt_chk or []) and any(w['lat'] is not None and w['lon'] is not None for w in wpts)

    write_config_file(config_path, vol, latv, lonv, s_d, e_d, frp, frp_mode, trk, m_key,
                      'True' in (rad_chk or []), rad_m, 'True' in (shp_chk or []), shp_p, wpt_on, wpts)
    lfc.set_active_folder(folder_path)

    extra = "" if wpt_on or 'True' not in (wpt_chk or []) else " (waypoints disabled: no coordinates given)"
    return f"Project saved: {vol} → {config_path}{extra}", f"LavaFlow Mapper Suite: {vol}"


@app.callback(Output("dl-output-log", "children"), Input("btn-run-download", "n_clicks"),
              [State('dl-date-picker', 'start_date'), State('dl-date-picker', 'end_date'), State('dl-radius', 'value')],
              prevent_initial_call=True)
def dl_cb(n, s, e, radius):
    if n > 0:
        return download_logic.process_download(s.split('T')[0], e.split('T')[0], radius or 10000)
    return ""


@app.callback([Output("out-stats-results", "children"), Output('store-stats-status', 'data')],
              Input("btn-run-stats", "n_clicks"), prevent_initial_call=True)
def stats_cb(n):
    if n > 0:
        return stats_module.get_layout(), {'run': True}
    return no_update, no_update


@app.callback([Output("out-mapper-results", "children"), Output('store-mapper-status', 'data')],
              Input("btn-run-mapper", "n_clicks"), prevent_initial_call=True)
def mapper_cb(n):
    if n > 0:
        return mapper_module.get_layout(), {'run': True}
    return no_update, no_update


@app.callback([Output("out-speed-results", "children"), Output('store-speed-status', 'data')],
              Input("btn-run-speed", "n_clicks"), prevent_initial_call=True)
def speed_cb(n):
    if n > 0:
        return speed_module.get_layout(), {'run': True}
    return no_update, no_update


# ==========================================
# 3. DATE HELPERS
# ==========================================

@app.callback(
    Output('cfg-date-end', 'value', allow_duplicate=True),
    [Input('btn-date-plus1', 'n_clicks'), Input('btn-date-plus7', 'n_clicks')],
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
    dt += timedelta(days=1 if ctx.triggered_id == 'btn-date-plus1' else 7)
    return dt.strftime('%d/%m/%Y')


@app.callback(
    Output('cfg-date-validation', 'children'),
    [Input('cfg-date-start', 'value'), Input('cfg-date-end', 'value')],
    prevent_initial_call=True
)
def validate_dates(sd, ed):
    sd_dt = ed_dt = None
    try:
        sd_dt = datetime.strptime((sd or '').strip(), '%d/%m/%Y')
    except ValueError:
        pass
    try:
        ed_dt = datetime.strptime((ed or '').strip(), '%d/%m/%Y')
    except ValueError:
        pass
    if sd_dt and ed_dt:
        if ed_dt <= sd_dt:
            return html.Span("End date must be after the start date.", style={'color': '#c0392b'})
        return html.Span(f"Period: {(ed_dt - sd_dt).days} days "
                         f"({sd_dt.strftime('%d %b %Y')} → {ed_dt.strftime('%d %b %Y')})", style={'color': '#27ae60'})
    if sd and not sd_dt:
        return html.Span("Start date: use DD/MM/YYYY.", style={'color': '#c0392b'})
    if ed and not ed_dt:
        return html.Span("End date: use DD/MM/YYYY.", style={'color': '#c0392b'})
    return ""


@app.callback(Output('cfg-volcano', 'style'), Input('cfg-volcano', 'value'), prevent_initial_call=True)
def highlight_volcano_name(volcano_value):
    return volcano_input_style(volcano_value)


# ==========================================
# 4. WAYPOINT EDITOR CALLBACKS
# ==========================================

@app.callback(Output('wpt-container', 'children'), Input('wpt-list-store', 'data'))
def render_waypoint_container(waypoints):
    if not waypoints:
        return html.Div("No waypoints. Click “+ Add waypoint” to add one.", className='lf-muted',
                        style={'padding': '8px'})
    return [render_waypoint_row(i, w) for i, w in enumerate(waypoints)]


def _collect_wpts(names, lats, lons, syms, skip=None):
    out = []
    for i in range(len(names or [])):
        if i == skip:
            continue
        out.append({'name': names[i] or '', 'lat': lats[i], 'lon': lons[i], 'symbol': syms[i] or 'circle'})
    return out


@app.callback(
    Output('wpt-list-store', 'data', allow_duplicate=True),
    Input('btn-add-wpt', 'n_clicks'),
    [State({'type': 'wpt-name', 'index': ALL}, 'value'), State({'type': 'wpt-lat', 'index': ALL}, 'value'),
     State({'type': 'wpt-lon', 'index': ALL}, 'value'), State({'type': 'wpt-symbol', 'index': ALL}, 'value')],
    prevent_initial_call=True
)
def add_waypoint_cb(n, names, lats, lons, syms):
    wpts = _collect_wpts(names, lats, lons, syms)
    wpts.append({'name': '', 'lat': None, 'lon': None, 'symbol': 'circle'})
    return wpts


@app.callback(
    Output('wpt-list-store', 'data', allow_duplicate=True),
    Input({'type': 'wpt-remove', 'index': ALL}, 'n_clicks'),
    [State({'type': 'wpt-name', 'index': ALL}, 'value'), State({'type': 'wpt-lat', 'index': ALL}, 'value'),
     State({'type': 'wpt-lon', 'index': ALL}, 'value'), State({'type': 'wpt-symbol', 'index': ALL}, 'value')],
    prevent_initial_call=True
)
def remove_waypoint_cb(n_clicks_list, names, lats, lons, syms):
    from dash import ctx
    if not isinstance(ctx.triggered_id, dict) or not any(n for n in (n_clicks_list or []) if n):
        return no_update
    return _collect_wpts(names, lats, lons, syms, skip=ctx.triggered_id.get('index'))


if __name__ == '__main__':
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        Timer(1.5, lambda: webbrowser.open_new("http://127.0.0.1:9050/")).start()
    app.run(debug=True, port=9050, dev_tools_hot_reload=False)
