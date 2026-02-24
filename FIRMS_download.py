import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import requests
import os
import numpy as np
from datetime import datetime, date, timedelta
from io import StringIO


# ==========================================
# 1. LOGIC: CONFIG & GEOMETRY
# ==========================================

def load_global_config():
    """Load configuration parameters. Creates config.txt with defaults if missing."""
    default_params = {
        'volcano': 'Volcano Name',
        'lats_vent': 0.0,
        'longs_vent': 0.0,
        'start_day_str': '01/01/2024 00:00',
        'end_day_str': '01/01/2026 00:00',
        'filter_frp': 0,
        'filter_track': 0.5,
        'map_key': 'INSERT_YOUR_MAP_KEY_HERE',
        'include_reference_radius': True,
        'ref_radius_m': 3000,
        'include_shapefile': False,
        'shapefile_path': '',
        'include_reference_waypoint': False,
        'wpt_names': 'Reference Point',
        'wpt_lats': '0.0',
        'wpt_lons': '0.0',
        'wpt_symbols': 'circle'
    }

    if not os.path.exists("config.txt"):
        with open("config.txt", "w") as f:
            for key, value in default_params.items():
                f.write(f"{key}={value}\n")
        return default_params

    config = {}
    with open("config.txt", "r") as f:
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

    final_config = default_params.copy()
    final_config.update(config)
    return final_config


def calculate_bbox(lat, lon, radius_m):
    """Calculates BBox based on vent coordinates and user-defined radius."""
    lat_offset = radius_m / 111320
    lon_offset = radius_m / (111320 * np.cos(np.radians(lat)))

    bbox = [
        round(lon - lon_offset, 5),  # min_lon
        round(lat - lat_offset, 5),  # min_lat
        round(lon + lon_offset, 5),  # max_lon
        round(lat + lat_offset, 5)  # max_lat
    ]
    return ",".join(map(str, bbox))


# ==========================================
# 2. LOGIC: DOWNLOAD & HIGH-PRECISION MERGE
# ==========================================

def process_download(start_date, end_date, radius_m):
    """Downloads FIRMS data using a custom search radius."""
    cfg = load_global_config()
    map_key = cfg.get('map_key')
    lat_v = float(cfg.get('lats_vent'))
    lon_v = float(cfg.get('longs_vent'))

    bbox = calculate_bbox(lat_v, lon_v, radius_m)

    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")

    days = (dt_end - dt_start).days + 1
    if days < 1: days = 1

    sources = {
        'VIIRS_SNPP_NRT': 'historical_VIIRS_SNPP_NRT.csv',
        'VIIRS_NOAA21_NRT': 'historical_VIIRS_NOAA21_NRT.csv',
        'VIIRS_NOAA20_NRT': 'historical_VIIRS_NOAA20_NRT.csv',
        'MODIS_NRT': 'historical_MODIS_NRT.csv'
    }

    log = []
    for src_id, filename in sources.items():
        try:
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{src_id}/{bbox}/{days}/{start_date}"
            response = requests.get(url)

            if response.status_code != 200:
                log.append(f"❌ {src_id}: API error (HTTP {response.status_code})")
                continue

            df_new = pd.read_csv(StringIO(response.text))
            if df_new.empty:
                log.append(f"⚠️ {src_id}: No data found.")
                continue

            current_batch_count = len(df_new)
            df_new['acq_time'] = df_new['acq_time'].astype(str).str.zfill(4)
            df_new['acq_date'] = pd.to_datetime(df_new['acq_date'])

            if os.path.exists(filename):
                df_hist = pd.read_csv(filename)
                df_hist['acq_time'] = df_hist['acq_time'].astype(str).str.zfill(4)
                df_hist['acq_date'] = pd.to_datetime(df_hist['acq_date'], dayfirst=True)

                dates_to_refresh = df_new['acq_date'].unique()
                df_hist = df_hist[~df_hist['acq_date'].isin(dates_to_refresh)]

                df_combined = pd.concat([df_hist, df_new], ignore_index=True)
                df_combined['latitude'] = pd.to_numeric(df_combined['latitude'], errors='coerce')
                df_combined['longitude'] = pd.to_numeric(df_combined['longitude'], errors='coerce')
                df_combined = df_combined.dropna(subset=['latitude', 'longitude'])

                df_combined['lat_round'] = df_combined['latitude'].round(4)
                df_combined['lon_round'] = df_combined['longitude'].round(4)

                df_final = df_combined.drop_duplicates(
                    subset=['lat_round', 'lon_round', 'acq_date', 'acq_time']
                ).drop(columns=['lat_round', 'lon_round'])
            else:
                df_final = df_new

            df_final['acq_date'] = df_final['acq_date'].dt.strftime('%d/%m/%Y')
            df_final.to_csv(filename, index=False)
            log.append(f"✅ {src_id}: {current_batch_count} records merged | Total: {len(df_final)}")

        except Exception as e:
            log.append(f"❌ {src_id}: Error {str(e)}")

    return "\n".join(log)


# ==========================================
# 3. DASHBOARD UI
# ==========================================

if __name__ == '__main__':
    app = dash.Dash(__name__)
    init_cfg = load_global_config()
    default_radius = float(init_cfg.get('ref_radius_m', 3000))

    app.layout = html.Div([
        html.H2("🛰️ FIRMS Data Downloader & Merger"),
        html.Div([
            html.Label("Download Radius (meters):"),
            dcc.Input(id='dl-radius', type='number', value=default_radius),
            dcc.DatePickerRange(id='dl-date-picker', start_date=date.today() - timedelta(days=2),
                                end_date=date.today()),
            html.Button("START DOWNLOAD", id="btn-run", n_clicks=0),
        ]),
        dcc.Loading(html.Div(id="dl-output-log"))
    ])
    app.run(debug=True, port=8060)