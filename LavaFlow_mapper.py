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
def load_global_config():
    """Reads global variables from config.txt."""
    config = {}
    config_path = "config.txt"
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
# 1. DATA ENGINE
# ==========================================
def load_and_tag_data():
    """Reads satellite CSV files and tags them with source info."""
    all_data = []
    configs = [{"pattern": "*SNPP*.csv", "name": "SNPP", "id": 1},
               {"pattern": "*NOAA20*.csv", "name": "NOAA20", "id": 2},
               {"pattern": "*NOAA21*.csv", "name": "NOAA21", "id": 3}]

    for c in configs:
        for f in glob.glob(c["pattern"]):
            df = pd.read_csv(f)
            for col in ['latitude', 'longitude', 'frp', 'track']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['date'] = pd.to_datetime(df['acq_date'] + " " +
                                        df['acq_time'].astype(str).str.zfill(4),
                                        format="%d/%m/%Y %H%M")
            df['satellite'], df['source'] = c["name"], c["id"]
            all_data.append(df)
    return pd.concat(all_data) if all_data else pd.DataFrame()


# ==========================================
# 2. DASHBOARD GENERATOR
# ==========================================
def get_layout():
    """Returns the finalized layout and saves necessary CSV files to root."""
    cfg = load_global_config()
    volcano = cfg.get('volcano', 'Volcano')
    LATS_vent = cfg.get('lats_vent', 0.0)
    LONGS_vent = cfg.get('longs_vent', 0.0)

    comb = load_and_tag_data()
    if comb.empty: return html.Div("Error: No data files found.")

    start_dt = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True)
    end_dt = pd.to_datetime(cfg.get('end_day_str'), dayfirst=True)

    filtered = comb[(comb['track'] <= cfg.get('filter_track', 1.0)) &
                    (comb['frp'] >= cfg.get('filter_frp', 0.0)) &
                    (comb['date'] >= start_dt) & (comb['date'] <= end_dt)].sort_values('date').copy()

    if filtered.empty: return html.Div("No anomalies found in this range.")

    # Distance calculation (Haversine)
    R_earth = 6371.0
    p = np.pi / 180
    lat1, lon1 = LATS_vent * p, LONGS_vent * p
    lat2, lon2 = filtered['latitude'].values * p, filtered['longitude'].values * p
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    filtered['distance_km'] = R_earth * 2 * np.arcsin(np.sqrt(a))

    # --- SAVE RESULTS TO ROOT ---
    filtered.to_csv("filter_VIIRS_combined.csv", index=False)

    daily_max = filtered.copy()
    daily_max['date_only'] = daily_max['date'].dt.date
    summary = daily_max.groupby(['date_only', 'satellite']).agg({
        'distance_km': 'max', 'frp': 'max', 'latitude': 'first',
        'longitude': 'first', 'source': 'first'
    }).reset_index()
    summary.to_csv("max_distance_per_day_VIIRS.csv", index=False)

    # --- FOLIUM MAP ---
    m = folium.Map(location=[LATS_vent, LONGS_vent], zoom_start=13, control_scale=True, tiles=None)

    # UPDATED CSS: Bottom value increased to 80px to prevent scale clipping
    custom_css = """
    <style>
        .leaflet-control-scale { 
            position: absolute !important;
            bottom: 120px !important; 
            left: 20px !important; 
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
    colormap = bcm.LinearColormap(colors=['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c'], vmin=min_ts,
                                  vmax=max_ts)

    s_label, e_label = start_dt.strftime("%d/%m/%Y"), end_dt.strftime("%d/%m/%Y")
    colormap.caption = f'      Timeline: {s_label} - {e_label}'
    colormap.tick_labels = []
    colormap.add_to(m)

    fg_anomalies = folium.FeatureGroup(name="Thermal Anomalies")
    for _, row in filtered.iterrows():
        folium.Circle(location=[row['latitude'], row['longitude']], radius=192.5,
                      color=colormap(row['date'].timestamp()), fill=True, fill_opacity=0.7,
                      popup=f"Date: {row['date'].strftime('%Y-%m-%d %H:%M')}<br>FRP: {row['frp']} MW").add_to(
            fg_anomalies)
    fg_anomalies.add_to(m)

    if cfg.get('include_shapefile') and cfg.get('shapefile_path'):
        path = cfg.get('shapefile_path')
        actual_path = path if path.endswith(".shp") else path + ".shp"
        if os.path.exists(actual_path):
            try:
                import geopandas as gpd
                gdf = gpd.read_file(actual_path).to_crs(epsg=4326)
                folium.GeoJson(gdf, name="Shapefile Overlay",
                               style_function=lambda x: {'color': 'black', 'weight': 2, 'fill': False}).add_to(m)
            except:
                pass

    if cfg.get('include_reference_radius'):
        fg_rad = folium.FeatureGroup(name='Reference Radius')
        folium.Circle(location=[LATS_vent, LONGS_vent], radius=cfg.get('ref_radius_m', 5000),
                      color='black', weight=1, fill=False, dash_array='5,5').add_to(fg_rad)
        fg_rad.add_to(m)

    if cfg.get('include_reference_waypoint'):
        w_names = str(cfg.get('wpt_names', "")).split(",")
        w_lats = str(cfg.get('wpt_lats', "")).split(",")
        w_lons = str(cfg.get('wpt_lons', "")).split(",")
        w_syms = str(cfg.get('wpt_symbols', "")).split(",")
        fg_wpts = folium.FeatureGroup(name="Reference Waypoints")
        for i in range(len(w_names)):
            try:
                lat, lon, sym = float(w_lats[i]), float(w_lons[i]), w_syms[i].strip()
                if sym == "circle":
                    folium.CircleMarker([lat, lon], radius=7, color='darkred', fill=True, tooltip=w_names[i]).add_to(
                        fg_wpts)
                else:
                    RegularPolygonMarker([lat, lon], number_of_sides=4, radius=7, color='darkred', fill=True,
                                         tooltip=w_names[i]).add_to(fg_wpts)
            except:
                continue
        fg_wpts.add_to(m)

    folium.Marker([LATS_vent, LONGS_vent], icon=folium.DivIcon(
        html='<div style="width:0;height:0;border-left:10px solid transparent;border-right:10px solid transparent;border-bottom:20px solid black;transform:translate(-50%,-50%);"></div>'),
                  tooltip="Vent").add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    map_html = m._repr_html_()

    # --- PLOTLY TIME SERIES ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    sat_colors = {'SNPP': 'orange', 'NOAA20': 'purple', 'NOAA21': 'red'}

    for sat, color in sat_colors.items():
        d = filtered[filtered['satellite'] == sat]
        if not d.empty:
            fig.add_trace(go.Scatter(x=d['date'], y=d['frp'], mode='markers', name=sat,
                                     marker=dict(color=color, size=8, line=dict(width=1, color='black')),
                                     hovertemplate="Date: %{x}<br>FRP: %{y} MW<extra></extra>"), row=1, col=1)
            for _, row in d.iterrows():
                fig.add_trace(go.Scatter(x=[row['date'], row['date']], y=[0, row['distance_km']],
                                         mode='lines', line=dict(color=color, width=1.2),
                                         showlegend=False, hoverinfo='skip'), row=2, col=1)
            fig.add_trace(go.Scatter(x=d['date'], y=d['distance_km'], mode='markers',
                                     marker=dict(color=color, size=6), showlegend=False,
                                     hovertemplate="Date: %{x}<br>Max. Distance: %{y:.2f} km<extra></extra>"), row=2,
                          col=1)

    fig.update_layout(
        title=dict(text=f"FIRMS - Thermal anomalies<br>{volcano} volcano: {s_label} - {e_label}", x=0.5,
                   xanchor='center', font=dict(size=18, color='black')),
        height=750, template="plotly_white", margin=dict(t=100, b=50),
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0)
    )

    fig.update_yaxes(title_text="FRP (MW)", row=1, col=1)
    fig.update_yaxes(title_text="Max. Lava Flow Distance (km)", row=2, col=1)

    return html.Div([
        html.Div([html.Iframe(srcDoc=map_html, width='100%', height='600px',
                              style={'border': 'none', 'borderRadius': '8px'})],
                 style={'marginBottom': '20px', 'padding': '5px'}),
        html.Div([dcc.Graph(figure=fig, config={
            'toImageButtonOptions': {'format': 'png', 'filename': f'{volcano}_analysis', 'height': 900, 'width': 1200,
                                     'scale': 3}, 'displaylogo': False})])
    ])


if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    app.run(debug=True, port=8090)