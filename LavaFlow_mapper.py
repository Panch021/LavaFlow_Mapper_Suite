import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from dash import html, dcc
import glob
import os

# Robust import for geometric symbols
try:
    from folium.plugins import RegularPolygonMarker
except ImportError:
    from folium.features import RegularPolygonMarker
import branca.colormap as bcm


# ==========================================
# 0. CONFIGURATION LOADER
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
            return path  # new format: full relative path
        # Legacy fallback: treat as bare folder name in root
        legacy = path.replace(" ", "_")
        if os.path.isdir(legacy):
            return legacy
    return None


def load_global_config():
    """Reads variables from the specific volcano config file inside its folder."""
    config = {}
    folder = get_active_folder()
    if not folder:
        return config
    folder_name = os.path.basename(folder)  # e.g. 'Wolf_2022'
    config_path = os.path.join(folder, f"config_{folder_name}.txt")

    if not os.path.exists(config_path):
        return config

    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                val = value.strip()
                if val.lower() == 'true':
                    config[key.strip()] = True
                elif val.lower() == 'false':
                    config[key.strip()] = False
                else:
                    try:
                        config[key.strip()] = float(val) if "." in val else int(val)
                    except ValueError:
                        config[key.strip()] = val
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
    lats = _as_list(c.get('wpt_lats', 0.0))
    lons = _as_list(c.get('wpt_lons', 0.0))
    syms = _as_list(c.get('wpt_symbols', 'circle'))

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


# ==========================================
# 1. DATA ENGINE
# ==========================================
def load_and_tag_data():
    """Reads satellite CSV files from the volcano subfolder."""
    all_data = []
    folder = get_active_folder()
    if not folder:
        return pd.DataFrame()
    folder_name = os.path.basename(folder)  # e.g. 'Wolf' not 'projects/Wolf'

    configs = [{"pattern": f"*SNPP*{folder_name}.csv", "name": "SNPP", "id": 1},
               {"pattern": f"*NOAA20*{folder_name}.csv", "name": "NOAA20", "id": 2},
               {"pattern": f"*NOAA21*{folder_name}.csv", "name": "NOAA21", "id": 3}]

    for c in configs:
        search_path = os.path.join(folder, c["pattern"])
        for f in glob.glob(search_path):
            try:
                try:
                    df = pd.read_csv(f, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(f, encoding='latin-1')

                for col in ['latitude', 'longitude', 'frp', 'track']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                # Robust multi-format date parser — handles:
                # YYYY-MM-DD (ISO), DD/MM/YYYY (legacy), D/M/YY (NASA API short)
                date_str = df['acq_date'].astype(str) + " " + df['acq_time'].astype(str).str.zfill(4)
                parsed = pd.to_datetime(date_str, format="%Y-%m-%d %H%M", errors='coerce')
                if parsed.isna().all():
                    parsed = pd.to_datetime(date_str, format="%d/%m/%Y %H%M", errors='coerce')
                if parsed.isna().all():
                    parsed = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
                df['date'] = parsed

                df['satellite'], df['source'] = c["name"], c["id"]
                all_data.append(df)
            except Exception:
                continue

    return pd.concat(all_data) if all_data else pd.DataFrame()


# ==========================================
# 2. VERTICAL COLORBAR BUILDER
# ==========================================
def build_vertical_colorbar(start_dt, end_dt, n_ticks=6):
    """
    Returns an HTML block rendering a vertical CSS gradient colorbar
    with date labels, positioned to sit above the scale bar.
    Colors match the branca LinearColormap used on the map points.
    """
    colors = ['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c']
    gradient = ", ".join(colors)

    total_seconds = (end_dt - start_dt).total_seconds()
    tick_dates = [
        start_dt + pd.Timedelta(seconds=total_seconds * i / (n_ticks - 1))
        for i in range(n_ticks)
    ]
    # Labels go from bottom (oldest) to top (newest)
    tick_labels = [d.strftime('%d/%m/%Y') for d in reversed(tick_dates)]

    label_items = "".join([
        f'<div style="flex:1;display:flex;align-items:center;'
        f'font-size:10px;color:#333;white-space:nowrap;">{lbl}</div>'
        for lbl in tick_labels
    ])

    html_block = f"""
    <div style="
        position: absolute;
        bottom: 160px;
        left: 10px;
        z-index: 9999;
        display: flex;
        flex-direction: row;
        align-items: stretch;
        height: 160px;
        pointer-events: none;
        background-color: white;
        padding: 5px 7px;
        border-radius: 5px;
    ">
        <!-- Gradient bar -->
        <div style="
            width: 14px;
            height: 100%;
            background: linear-gradient(to top, {gradient});
            border: 1px solid #aaa;
            border-radius: 3px;
            margin-right: 5px;
            flex-shrink: 0;
        "></div>
        <!-- Date tick labels -->
        <div style="
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
        ">
            {label_items}
        </div>
    </div>
    """
    return html_block


# ==========================================
# 2b. LOCK-ZOOM CONTROL (injected into folium)
# ==========================================
def build_lock_zoom_script():
    """
    Returns a <script> block that adds a Leaflet control button at the
    bottom-right of the folium map. The button toggles scrollWheelZoom,
    doubleClickZoom, touchZoom and boxZoom on the leaflet map instance.
    Works inside the iframe because it manipulates the leaflet map directly,
    finding it via the global `map_*` variable folium auto-creates.
    """
    return """
    <script>
    (function() {
        function attachLockButton() {
            // Find folium's auto-generated map variable (e.g. map_abc123)
            var mapKey = Object.keys(window).find(function(k) {
                return k.startsWith('map_') && window[k] && window[k]._container;
            });
            if (!mapKey) { setTimeout(attachLockButton, 150); return; }
            var leafletMap = window[mapKey];

            var LockControl = L.Control.extend({
                options: { position: 'bottomright' },
                onAdd: function(map) {
                    var btn = L.DomUtil.create('button', 'leaflet-bar lock-zoom-btn');
                    btn.innerHTML = '🔓 Unlock zoom';
                    btn.style.cssText = 'padding:6px 10px;background:#c0392b;color:white;' +
                        'border:none;border-radius:4px;cursor:pointer;' +
                        'font-weight:bold;font-size:12px;' +
                        'box-shadow:0 1px 5px rgba(0,0,0,0.3);' +
                        'margin-bottom:400px;';
                    var locked = true;
                    // Apply locked state immediately on map load
                    map.scrollWheelZoom.disable();
                    map.doubleClickZoom.disable();
                    map.touchZoom.disable();
                    map.boxZoom.disable();

                    L.DomEvent.disableClickPropagation(btn);
                    L.DomEvent.on(btn, 'click', function() {
                        locked = !locked;
                     if (locked) {
                        map.scrollWheelZoom.disable();
                        map.doubleClickZoom.disable();
                        map.touchZoom.disable();
                        map.boxZoom.disable();
                        btn.innerHTML = '🔓 Unlock zoom';
                        btn.style.background = '#c0392b';
                     } else {
                        map.scrollWheelZoom.enable();
                        map.doubleClickZoom.enable();
                        map.touchZoom.enable();
                        map.boxZoom.enable();
                        btn.innerHTML = '🔒 Lock zoom';
                        btn.style.background = '#7f8c8d';
                     }
                    });
                    return btn;
                }

            });
            leafletMap.addControl(new LockControl());
        }
        if (document.readyState === 'complete') {
            attachLockButton();
        } else {
            window.addEventListener('load', attachLockButton);
        }
    })();
    </script>
    """


# ==========================================
# 2c. WAYPOINT MARKER HELPER
# ==========================================
def add_waypoint_marker(feature_group, lat, lon, name, symbol):
    """Adds a single waypoint to a folium FeatureGroup with the requested symbol."""
    if symbol == "circle":
        folium.CircleMarker(
            [lat, lon], radius=7, color='black', fill=True, fill_opacity=1.0,
            tooltip=name or "Waypoint"
        ).add_to(feature_group)
    elif symbol == "triangle":
        RegularPolygonMarker(
            [lat, lon], number_of_sides=3, radius=9, rotation=30,
            color='black', fill=True, fill_opacity=1.0,
            tooltip=name or "Waypoint"
        ).add_to(feature_group)
    else:  # square or anything else falls back to square
        RegularPolygonMarker(
            [lat, lon], number_of_sides=4, radius=7, rotation=45,
            color='black', fill=True, fill_opacity=1.0,
            tooltip=name or "Waypoint"
        ).add_to(feature_group)


# ==========================================
# 3. DASHBOARD GENERATOR
# ==========================================
def get_layout():
    """Returns the finalized layout and saves necessary CSV files to the volcano folder."""
    cfg = load_global_config()
    folder = get_active_folder()
    volcano = cfg.get('volcano', 'Volcano')
    LATS_vent = cfg.get('lats_vent', 0.0)
    LONGS_vent = cfg.get('longs_vent', 0.0)

    comb = load_and_tag_data()
    if comb.empty:
        return html.Div(f"Error: No data files found in folder '{folder}'.")

    start_dt = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True)
    end_dt = pd.to_datetime(cfg.get('end_day_str'), dayfirst=True)

    # Apply FRP filter direction based on frp_filter_mode: 'gt' = >= threshold, 'lt' = <= threshold
    frp_threshold = cfg.get('filter_frp', 0.0)
    frp_mode = cfg.get('frp_filter_mode', 'gt')
    frp_mask = comb['frp'] >= frp_threshold if frp_mode == 'gt' else comb['frp'] <= frp_threshold

    filtered = comb[(comb['track'] <= cfg.get('filter_track', 1.0)) &
                    frp_mask &
                    (comb['date'] >= start_dt) & (comb['date'] <= end_dt)].sort_values('date').copy()

    if filtered.empty:
        return html.Div("No anomalies found in this range.")

    R_earth = 6371.0
    p = np.pi / 180
    lat1, lon1 = LATS_vent * p, LONGS_vent * p
    lat2, lon2 = filtered['latitude'].values * p, filtered['longitude'].values * p
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    filtered['distance_km'] = R_earth * 2 * np.arcsin(np.sqrt(a))

    # --- SAVE RESULTS TO VOLCANO FOLDER ---
    if folder:
        filtered.to_csv(os.path.join(folder, "filter_VIIRS_combined.csv"), index=False)
        daily_max = filtered.copy()
        daily_max['date_only'] = daily_max['date'].dt.date
        summary = daily_max.groupby(['date_only', 'satellite']).agg({
            'distance_km': 'max', 'frp': 'max', 'latitude': 'first',
            'longitude': 'first', 'source': 'first'
        }).reset_index()
        summary.to_csv(os.path.join(folder, "max_distance_per_day_VIIRS.csv"), index=False)

    # --- FOLIUM MAP ---
    m = folium.Map(location=[LATS_vent, LONGS_vent], zoom_start=13, control_scale=True, tiles=None)

    custom_css = """
    <style>
        .leaflet-control-scale {
            position: absolute !important;
            bottom: 100px !important;
            left: 10px !important;
            z-index: 9999 !important;
            visibility: visible !important;
        }
        .legend {
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
        }
        .legend .caption {
            font-size: 13px !important;
            font-weight: bold !important;
            color: black !important;
            margin-bottom: 5px !important;
            order: -1 !important;
        }
    </style>
    """
    m.get_root().header.add_child(folium.Element(custom_css))

    folium.TileLayer('Esri World Imagery', name='Esri World Imagery').add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    folium.TileLayer('OpenTopoMap', name='OpenTopoMap').add_to(m)

    min_ts, max_ts = start_dt.timestamp(), end_dt.timestamp()
    # Keep the branca colormap for circle coloring but hide its default legend
    colormap = bcm.LinearColormap(
        colors=['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c'],
        vmin=min_ts, vmax=max_ts
    )

    s_label, e_label = start_dt.strftime("%d/%m/%Y"), end_dt.strftime("%d/%m/%Y")

    # Inject the vertical colorbar as a custom HTML element instead of branca's default
    colorbar_html = build_vertical_colorbar(start_dt, end_dt, n_ticks=6)
    m.get_root().html.add_child(folium.Element(colorbar_html))

    fg_anomalies = folium.FeatureGroup(name="Thermal Anomalies")
    for _, row in filtered.iterrows():
        folium.Circle(
            location=[row['latitude'], row['longitude']], radius=192.5,
            color=colormap(row['date'].timestamp()), fill=True, fill_opacity=0.7,
            popup=f"Date: {row['date'].strftime('%Y-%m-%d %H:%M')}<br>FRP: {row['frp']} MW"
        ).add_to(fg_anomalies)
    fg_anomalies.add_to(m)

    # --- SHAPEFILE: errors are now shown to the user in the layout ---
    shapefile_warning = None
    if cfg.get('include_shapefile') and cfg.get('shapefile_path'):
        shp_name = str(cfg.get('shapefile_path'))
        if not shp_name.lower().endswith(".shp"):
            shp_name += ".shp"
        actual_path = os.path.join(folder, shp_name) if folder else shp_name

        if not os.path.exists(actual_path):
            shapefile_warning = f"⚠️ Shapefile not found: {actual_path}"
        else:
            try:
                import geopandas as gpd
                gdf = gpd.read_file(actual_path).to_crs(epsg=4326)
                folium.GeoJson(
                    gdf, name="Reference Shapefile",
                    style_function=lambda x: {'color': 'black', 'weight': 2, 'fill': False}
                ).add_to(m)
            except Exception as e:
                shapefile_warning = f"⚠️ Error loading shapefile '{shp_name}': {str(e)}"

    if cfg.get('include_reference_radius'):
        fg_rad = folium.FeatureGroup(name='Reference Radius')
        folium.Circle(
            location=[LATS_vent, LONGS_vent], radius=cfg.get('ref_radius_m', 5000),
            color='black', weight=1, fill=False, dash_array='5,5'
        ).add_to(fg_rad)
        fg_rad.add_to(m)

    # --- MULTI-WAYPOINT PLOTTING ---
    # Read all waypoints from config (semicolon-separated, with single-waypoint fallback)
    waypoints = parse_waypoints_from_config(cfg) if cfg.get('include_reference_waypoint') else []
    if waypoints:
        fg_wpts = folium.FeatureGroup(name="Reference Waypoints")
        for wpt in waypoints:
            add_waypoint_marker(
                fg_wpts,
                lat=wpt['lat'], lon=wpt['lon'],
                name=wpt['name'], symbol=wpt['symbol']
            )
        fg_wpts.add_to(m)

    folium.Marker(
        [LATS_vent, LONGS_vent],
        icon=folium.DivIcon(
            html='<div style="width:0;height:0;border-left:10px solid transparent;'
                 'border-right:10px solid transparent;border-bottom:20px solid black;'
                 'transform:translate(-50%,-50%);"></div>'
        ),
        tooltip="Vent"
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # --- AUTO-FIT MAP BOUNDS TO DATA EXTENT ---
    # Compute bounding box from anomalies and vent; include reference radius if enabled
    lats = list(filtered['latitude'].values) + [LATS_vent]
    lons = list(filtered['longitude'].values) + [LONGS_vent]

    # If the reference radius is enabled, expand bounds so the full circle is visible
    if cfg.get('include_reference_radius'):
        radius_m = cfg.get('ref_radius_m', 5000)
        # Rough degree conversion: 1 deg lat ≈ 111 km; lon adjusted by latitude
        dlat = radius_m / 111000.0
        dlon = radius_m / (111000.0 * max(np.cos(np.radians(LATS_vent)), 1e-6))
        lats += [LATS_vent - dlat, LATS_vent + dlat]
        lons += [LONGS_vent - dlon, LONGS_vent + dlon]

    # Include ALL reference waypoints if enabled
    for wpt in waypoints:
        lats.append(wpt['lat'])
        lons.append(wpt['lon'])

    south, north = min(lats), max(lats)
    west, east = min(lons), max(lons)

    # Guard against degenerate (single-point) bounds — add a small buffer
    if south == north:
        south -= 0.005
        north += 0.005
    if west == east:
        west -= 0.005
        east += 0.005

    m.fit_bounds([[south, west], [north, east]], padding=(30, 30))

    # Inject lock-zoom button (must come AFTER LayerControl so leaflet map is fully built)
    m.get_root().html.add_child(folium.Element(build_lock_zoom_script()))

    map_html = m._repr_html_()

    # --- PLOTLY TIME SERIES ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    sat_colors = {'SNPP': 'orange', 'NOAA20': 'purple', 'NOAA21': 'red'}

    for sat, color in sat_colors.items():
        d = filtered[filtered['satellite'] == sat]
        if not d.empty:
            fig.add_trace(go.Scatter(
                x=d['date'], y=d['frp'], mode='markers', name=sat,
                marker=dict(color=color, size=8, line=dict(width=1, color='black')),
                hovertemplate="Date: %{x|%d/%m/%Y}<br>FRP: %{y} MW<extra></extra>"
            ), row=1, col=1)
            for _, row in d.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row['date'], row['date']], y=[0, row['distance_km']],
                    mode='lines', line=dict(color=color, width=1.2),
                    showlegend=False, hoverinfo='skip'
                ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=d['date'], y=d['distance_km'], mode='markers',
                marker=dict(color=color, size=6), showlegend=False,
                hovertemplate="Date: %{x|%d/%m/%Y}<br>Max. Distance: %{y:.2f} km<extra></extra>"
            ), row=2, col=1)

    fig.update_layout(
        title=dict(
            text=f"FIRMS - Thermal anomalies<br>{volcano} volcano: {s_label} - {e_label}",
            x=0.5, xanchor='center', font=dict(size=18, color='black')
        ),
        height=750, template="plotly_white", margin=dict(t=100, b=50),
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0)
    )

    # Force x-axis to span the full configured period, regardless of data extent
    fig.update_xaxes(range=[start_dt, end_dt], row=1, col=1)
    fig.update_xaxes(range=[start_dt, end_dt], row=2, col=1)

    fig.update_yaxes(title_text="FRP (MW)", row=1, col=1)
    fig.update_yaxes(title_text="Max. Lava Flow Distance (km)", row=2, col=1)

    # --- SUMMARY STATS PANEL ---
    # Read from filter_VIIRS_combined.csv to get global stats across all satellites
    summary_panel = None
    csv_path = os.path.join(folder, "filter_VIIRS_combined.csv") if folder else "filter_VIIRS_combined.csv"
    if os.path.exists(csv_path):
        df_comb = pd.read_csv(csv_path)
        if not df_comb.empty:
            frp_mean = df_comb['frp'].mean()
            frp_max = df_comb['frp'].max()
            dist_mean = df_comb['distance_km'].mean()
            dist_max = df_comb['distance_km'].max()

            box_style = {
                'flex': '1', 'minWidth': '160px', 'padding': '14px 18px',
                'borderRadius': '8px', 'backgroundColor': '#f0f4f8',
                'border': '2px solid #2980b9', 'textAlign': 'center'
            }
            label_style = {'fontSize': '11px', 'color': '#7f8c8d', 'marginBottom': '4px'}
            value_style = {'fontSize': '22px', 'fontWeight': 'bold', 'color': '#2980b9'}

            summary_panel = html.Div([
                html.Div("📊 Period Summary (all satellites)", style={
                    'fontWeight': 'bold', 'fontSize': '14px', 'color': '#2c3e50',
                    'marginBottom': '10px'
                }),
                html.Div([
                    html.Div([
                        html.Div("Mean FRP", style=label_style),
                        html.Div(f"{frp_mean:.1f} MW", style=value_style),
                    ], style=box_style),
                    html.Div([
                        html.Div("Max FRP", style=label_style),
                        html.Div(f"{frp_max:.1f} MW", style=value_style),
                    ], style=box_style),
                    html.Div([
                        html.Div("Mean Distance", style=label_style),
                        html.Div(f"{dist_mean:.2f} km", style=value_style),
                    ], style=box_style),
                    html.Div([
                        html.Div("Max Distance", style=label_style),
                        html.Div(f"{dist_max:.2f} km", style=value_style),
                    ], style=box_style),
                ], style={
                    'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap'
                })
            ], style={
                'padding': '16px 20px', 'marginBottom': '20px',
                'backgroundColor': 'white', 'borderRadius': '10px',
                'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'
            })

    # Build layout children, inserting shapefile warning if needed
    layout_children = []

    if shapefile_warning:
        layout_children.append(
            html.Div(shapefile_warning, style={
                'backgroundColor': '#fff3cd', 'border': '1px solid #ffc107',
                'borderRadius': '6px', 'padding': '10px 16px',
                'marginBottom': '10px', 'color': '#856404', 'fontWeight': 'bold'
            })
        )

    if summary_panel:
        layout_children.append(summary_panel)

    # Map container: limited width and centered horizontally
    layout_children += [
        html.Div(
            [html.Iframe(srcDoc=map_html, width='100%', height='600px',
                         style={'border': 'none', 'borderRadius': '8px'})],
            style={
                'marginBottom': '20px', 'padding': '5px',
                'maxWidth': '1100px', 'margin': '0 auto 20px auto'
            }
        ),
        html.Div([dcc.Graph(figure=fig, config={
            'toImageButtonOptions': {
                'format': 'png', 'filename': f'{volcano}_analysis',
                'height': 900, 'width': 1200, 'scale': 3
            },
            'displaylogo': False
        })])
    ]

    return html.Div(layout_children)


if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    app.run(debug=True, port=8070)
