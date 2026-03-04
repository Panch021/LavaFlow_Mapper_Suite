import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import requests
import os
import numpy as np
from datetime import datetime, date, timedelta
from io import StringIO


# ==========================================
# 1. LOGIC: DIRECTORY & CONFIG MANAGEMENT
# ==========================================

def get_active_folder():
    """
    Reads the current volcano name from the session pointer file
    and returns the sanitized folder name.
    """
    if os.path.exists("active_volcano.txt"):
        with open("active_volcano.txt", "r") as f:
            vol_name = f.read().strip()
            return vol_name.replace(" ", "_")
    return None


def load_global_config():
    """
    Load configuration from the active volcano subfolder.
    Falls back to root config.txt if subfolder config is missing.
    """
    folder = get_active_folder()
    config_path = "config.txt"

    if folder:
        specific_path = os.path.join(folder, f"config_{folder}.txt")
        if os.path.exists(specific_path):
            config_path = specific_path

    if not os.path.exists(config_path):
        return {}

    config = {}
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


def calculate_bbox(lat, lon, radius_m):
    """Calculates BBox based on vent coordinates and user-defined radius."""
    lat_offset = radius_m / 111320
    lon_offset = radius_m / (111320 * np.cos(np.radians(lat)))
    bbox = [
        round(lon - lon_offset, 5), round(lat - lat_offset, 5),
        round(lon + lon_offset, 5), round(lat + lat_offset, 5)
    ]
    return ",".join(map(str, bbox))


# ==========================================
# 2. LOGIC: DOWNLOAD & ROBUST MERGE
# ==========================================

FIRMS_API_MAX_DAYS = 5  # NASA FIRMS API hard limit per request

def process_download(start_date, end_date, radius_m):
    """
    Downloads FIRMS data for all sensors and merges it into the specific volcano subfolder.
    Maintains historical consistency and prevents duplicates.
    For ranges > 10 days, the request is automatically split into chunks.
    """
    folder = get_active_folder()
    if not folder:
        return "❌ Error: Active volcano not set. Please save configuration in Global Config first."

    cfg = load_global_config()
    map_key = cfg.get('map_key')
    lat_v = float(cfg.get('lats_vent', 0))
    lon_v = float(cfg.get('longs_vent', 0))

    if not map_key or map_key == 'INSERT_YOUR_MAP_KEY_HERE':
        return "❌ Error: Valid NASA FIRMS API Key is required."

    bbox = calculate_bbox(lat_v, lon_v, radius_m)

    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")
    total_days = (dt_end - dt_start).days + 1
    if total_days < 1:
        return "❌ Error: End date must be after start date."

    # Build list of chunk intervals if range exceeds API limit
    date_chunks = []
    chunk_start = dt_start
    while chunk_start <= dt_end:
        chunk_end = min(chunk_start + timedelta(days=FIRMS_API_MAX_DAYS - 1), dt_end)
        date_chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)

    sources = {
        'VIIRS_SNPP_NRT': f'historical_VIIRS_SNPP_NRT_{folder}.csv',
        'VIIRS_NOAA21_NRT': f'historical_VIIRS_NOAA21_NRT_{folder}.csv',
        'VIIRS_NOAA20_NRT': f'historical_VIIRS_NOAA20_NRT_{folder}.csv',
        'MODIS_NRT': f'historical_MODIS_NRT_{folder}.csv'
    }

    log = []

    if len(date_chunks) > 1:
        log.append(f"ℹ️ Range of {total_days} days split into {len(date_chunks)} chunks (max {FIRMS_API_MAX_DAYS} days/request).\n")

    for src_id, filename in sources.items():
        try:
            file_path = os.path.join(folder, filename)
            all_new_frames = []

            for chunk_start, chunk_end in date_chunks:
                chunk_days = (chunk_end - chunk_start).days + 1
                chunk_start_str = chunk_start.strftime("%Y-%m-%d")

                url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{src_id}/{bbox}/{chunk_days}/{chunk_start_str}"
                response = requests.get(url)

                if response.status_code != 200:
                    log.append(f"❌ {src_id} [{chunk_start_str}]: API error (HTTP {response.status_code})")
                    continue

                df_chunk = pd.read_csv(StringIO(response.text))
                if not df_chunk.empty:
                    all_new_frames.append(df_chunk)

            if not all_new_frames:
                log.append(f"⚠️ {src_id}: No data found.")
                continue

            df_new = pd.concat(all_new_frames, ignore_index=True)

            # Standardize format for new data
            df_new['acq_time'] = df_new['acq_time'].astype(str).str.zfill(4)
            df_new['acq_date'] = pd.to_datetime(df_new['acq_date'])

            if os.path.exists(file_path):
                df_hist = pd.read_csv(file_path)
                df_hist['acq_date'] = pd.to_datetime(df_hist['acq_date'], format='%d/%m/%Y', errors='coerce')
                df_hist['acq_time'] = df_hist['acq_time'].astype(str).str.zfill(4)

                # Drop existing records for the downloaded date range to avoid stale data
                dates_to_refresh = df_new['acq_date'].unique()
                df_hist = df_hist[~df_hist['acq_date'].isin(dates_to_refresh)]

                df_combined = pd.concat([df_hist, df_new], ignore_index=True)
                df_combined = df_combined.dropna(subset=['latitude', 'longitude', 'acq_date'])

                df_combined['lat_r'] = pd.to_numeric(df_combined['latitude']).round(4)
                df_combined['lon_r'] = pd.to_numeric(df_combined['longitude']).round(4)

                df_final = df_combined.drop_duplicates(
                    subset=['lat_r', 'lon_r', 'acq_date', 'acq_time']
                ).drop(columns=['lat_r', 'lon_r'])
            else:
                df_final = df_new

            df_final = df_final.sort_values(['acq_date', 'acq_time'], ascending=[False, False])
            df_final['acq_date'] = df_final['acq_date'].dt.strftime('%d/%m/%Y')
            df_final.to_csv(file_path, index=False)

            log.append(f"✅ {src_id}: Merged ({len(df_new)} new) | Total: {len(df_final)}")

        except Exception as e:
            log.append(f"❌ {src_id}: System Error -> {str(e)}")

    return "\n".join(log)


# ==========================================
# 3. STANDALONE TEST UI
# ==========================================

if __name__ == '__main__':
    app = dash.Dash(__name__)
    init_cfg = load_global_config()
    default_radius = float(init_cfg.get('ref_radius_m', 10000))

    app.layout = html.Div([
        html.H2("🛰️ FIRMS Data Downloader & Merger"),
        html.Div([
            html.Label("Download Radius (meters):"),
            dcc.Input(id='dl-radius', type='number', value=default_radius),
            dcc.DatePickerRange(
                id='dl-date-picker',
                start_date=date.today() - timedelta(days=4),
                end_date=date.today()
            ),
            html.Button("START DOWNLOAD", id="btn-run", n_clicks=0),
        ]),
        dcc.Loading(html.Div(id="dl-output-log",
                             style={'whiteSpace': 'pre-line', 'marginTop': '20px', 'fontFamily': 'monospace'}))
    ])


    @app.callback(
        Output("dl-output-log", "children"),
        Input("btn-run", "n_clicks"),
        [State('dl-date-picker', 'start_date'),
         State('dl-date-picker', 'end_date'),
         State('dl-radius', 'value')],
        prevent_initial_call=True
    )
    def update_log(n, start, end, rad):
        return process_download(start, end, rad)


    app.run(debug=True, port=8055)
