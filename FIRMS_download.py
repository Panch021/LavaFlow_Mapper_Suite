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
    """
    Load configuration from the active volcano subfolder.
    """
    folder = get_active_folder()
    if not folder:
        return {}
    folder_name = os.path.basename(folder)          # e.g. 'Wolf_2022'
    config_path = os.path.join(folder, f"config_{folder_name}.txt")

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
# 2. ROBUST DATE PARSER & MIGRATION
# ==========================================

def parse_acq_date(series):
    """
    Robust date parser that normalizes acq_date to datetime regardless of
    the original format stored on disk. Handles:
      - ISO:          YYYY-MM-DD            (current standard)
      - Full legacy:  DD/MM/YYYY            (old app format)
      - Short legacy: D/M/YY, DD/M/YY, etc (NASA API raw output)
    Tries each format explicitly before falling back to pandas inference
    with dayfirst=True to avoid ambiguous month/day swaps.
    Always returns a datetime Series — never depends on the OS locale.
    """
    # 1. Try ISO format first (current standard)
    parsed = pd.to_datetime(series, format='%Y-%m-%d', errors='coerce')
    if parsed.notna().sum() == len(series.dropna()):
        return parsed

    # 2. Try full DD/MM/YYYY legacy format
    parsed = pd.to_datetime(series, format='%d/%m/%Y', errors='coerce')
    if parsed.notna().sum() == len(series.dropna()):
        return parsed

    # 3. Fallback: pandas inference with dayfirst=True
    # Handles short formats like D/M/YY, D/M/YYYY, DD/M/YY, etc.
    return pd.to_datetime(series, dayfirst=True, errors='coerce')


def migrate_historical_dates(folder, sources):
    """
    Checks all existing historical CSV files and migrates acq_date to ISO
    format (YYYY-MM-DD) if stored in any other format.
    Runs before every download attempt regardless of whether new data is found.
    Files already in ISO format are left untouched.
    Files that do not exist yet are silently skipped.
    """
    for filename in sources.values():
        file_path = os.path.join(folder, filename)
        if not os.path.exists(file_path):
            continue
        try:
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='latin-1')

            # Check if already in ISO format — skip to avoid unnecessary writes
            sample = df['acq_date'].dropna().iloc[0] if not df['acq_date'].dropna().empty else None
            if sample is None:
                continue

            try:
                datetime.strptime(str(sample), '%Y-%m-%d')
                continue  # Already ISO, nothing to do
            except ValueError:
                pass  # Not ISO, proceed with migration

            df['acq_date'] = parse_acq_date(df['acq_date'])
            df['acq_date'] = df['acq_date'].dt.strftime('%Y-%m-%d')
            df.to_csv(file_path, index=False)

        except Exception:
            continue  # Never block a download due to a migration error


# ==========================================
# 3. API TRANSACTION COUNTER
# ==========================================

FIRMS_TRANSACTION_LIMIT = 5000  # NASA FIRMS limit per 10-minute interval

def get_transaction_status(map_key):
    """
    Queries the NASA FIRMS API to get the current transaction count for the
    given MAP_KEY. Returns a dict with 'current', 'limit', and 'remaining',
    or None if the query fails (invalid key, no connection, etc.).
    """
    url = f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={map_key}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        current = int(data.get('current_transactions', 0))
        return {
            'current': current,
            'limit': FIRMS_TRANSACTION_LIMIT,
            'remaining': FIRMS_TRANSACTION_LIMIT - current
        }
    except Exception:
        return None


def build_transaction_panel(map_key):
    """
    Builds a Dash HTML panel showing current API transaction usage.
    Called before and after the download to show consumption.
    Returns an html.Div ready to embed in the log output.
    """
    status = get_transaction_status(map_key)

    if status is None:
        return html.Div(
            "⚠️ Could not retrieve transaction status (check API key or connection).",
            style={'color': '#e67e22', 'fontSize': '13px', 'marginTop': '8px'}
        )

    current = status['current']
    remaining = status['remaining']
    limit = status['limit']
    pct_used = (current / limit) * 100

    # Color scale: green → orange → red based on usage
    if pct_used < 50:
        bar_color = '#27ae60'
        text_color = '#27ae60'
    elif pct_used < 80:
        bar_color = '#e67e22'
        text_color = '#e67e22'
    else:
        bar_color = '#e74c3c'
        text_color = '#e74c3c'

    return html.Div([
        html.Div("🔑 NASA FIRMS API — Transaction Status (10-min window)",
                 style={'fontWeight': 'bold', 'fontSize': '13px', 'color': '#2c3e50', 'marginBottom': '8px'}),
        html.Div([
            # Used
            html.Div([
                html.Div("Used", style={'fontSize': '11px', 'color': '#7f8c8d'}),
                html.Div(f"{current}", style={'fontSize': '20px', 'fontWeight': 'bold', 'color': text_color}),
            ], style={'flex': '1', 'textAlign': 'center', 'padding': '8px 12px',
                      'backgroundColor': '#f8f9fa', 'borderRadius': '6px', 'border': '1px solid #dde'}),
            # Remaining
            html.Div([
                html.Div("Remaining", style={'fontSize': '11px', 'color': '#7f8c8d'}),
                html.Div(f"{remaining}", style={'fontSize': '20px', 'fontWeight': 'bold', 'color': '#2980b9'}),
            ], style={'flex': '1', 'textAlign': 'center', 'padding': '8px 12px',
                      'backgroundColor': '#f8f9fa', 'borderRadius': '6px', 'border': '1px solid #dde'}),
            # Limit
            html.Div([
                html.Div("Limit / 10 min", style={'fontSize': '11px', 'color': '#7f8c8d'}),
                html.Div(f"{limit}", style={'fontSize': '20px', 'fontWeight': 'bold', 'color': '#2c3e50'}),
            ], style={'flex': '1', 'textAlign': 'center', 'padding': '8px 12px',
                      'backgroundColor': '#f8f9fa', 'borderRadius': '6px', 'border': '1px solid #dde'}),
        ], style={'display': 'flex', 'gap': '8px', 'marginBottom': '8px'}),

        # Progress bar
        html.Div([
            html.Div(style={
                'height': '8px', 'width': f'{min(pct_used, 100):.1f}%',
                'backgroundColor': bar_color, 'borderRadius': '4px',
                'transition': 'width 0.3s ease'
            })
        ], style={
            'height': '8px', 'backgroundColor': '#ecf0f1',
            'borderRadius': '4px', 'overflow': 'hidden'
        }),
        html.Div(f"{pct_used:.1f}% used",
                 style={'fontSize': '11px', 'color': '#95a5a6', 'marginTop': '4px', 'textAlign': 'right'})

    ], style={
        'padding': '12px 16px', 'backgroundColor': 'white',
        'border': '1px solid #dde', 'borderRadius': '8px',
        'marginBottom': '12px'
    })


# ==========================================
# 4. LOGIC: DOWNLOAD & ROBUST MERGE
# ==========================================

FIRMS_API_MAX_DAYS = 5  # NASA FIRMS API hard limit per request


def process_download(start_date, end_date, radius_m):
    """
    Downloads FIRMS data for all sensors and merges it into the specific volcano subfolder.
    Maintains historical consistency and prevents duplicates.
    For ranges > 5 days, the request is automatically split into chunks.

    Date format policy:
      - All CSV files are always saved with acq_date in ISO format YYYY-MM-DD.
      - On every download attempt, migrate_historical_dates() checks all existing
        files and converts any legacy format to ISO before the merge.
      - If no historical file exists yet, migration is skipped and the new data
        is saved directly in ISO format.

    Returns a list of Dash components (text + transaction panel) for the log output.
    """
    radius_m = radius_m or 10000
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

    folder_name = os.path.basename(folder)   # e.g. 'Sangay' not 'projects/Sangay'
    sources = {
        'VIIRS_SNPP_NRT': f'historical_VIIRS_SNPP_NRT_{folder_name}.csv',
        'VIIRS_NOAA21_NRT': f'historical_VIIRS_NOAA21_NRT_{folder_name}.csv',
        'VIIRS_NOAA20_NRT': f'historical_VIIRS_NOAA20_NRT_{folder_name}.csv',
        'MODIS_NRT': f'historical_MODIS_NRT_{folder_name}.csv'
    }

    log_lines = []

    if len(date_chunks) > 1:
        log_lines.append(f"ℹ️ Range of {total_days} days split into {len(date_chunks)} chunks (max {FIRMS_API_MAX_DAYS} days/request).\n")

    # --- Transaction status BEFORE download ---
    tx_before = get_transaction_status(map_key)
    tx_before_count = tx_before['current'] if tx_before else None

    # Migrate any legacy date formats to ISO before processing new data.
    # Runs regardless of whether new data is found. Non-existent files are skipped.
    migrate_historical_dates(folder, sources)

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
                    log_lines.append(f"❌ {src_id} [{chunk_start_str}]: API error (HTTP {response.status_code})")
                    continue

                df_chunk = pd.read_csv(StringIO(response.text))
                if not df_chunk.empty:
                    all_new_frames.append(df_chunk)

            if not all_new_frames:
                log_lines.append(f"⚠️ {src_id}: No data found.")
                continue

            df_new = pd.concat(all_new_frames, ignore_index=True)

            # Normalize new data: acq_time zero-padded, acq_date to datetime
            df_new['acq_time'] = df_new['acq_time'].astype(str).str.zfill(4)
            df_new['acq_date'] = parse_acq_date(df_new['acq_date'])

            if os.path.exists(file_path):
                # Historical file already migrated to ISO by migrate_historical_dates()
                try:
                    df_hist = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    df_hist = pd.read_csv(file_path, encoding='latin-1')

                df_hist['acq_date'] = parse_acq_date(df_hist['acq_date'])
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

            # Always save in ISO format YYYY-MM-DD — locale-independent canonical format
            df_final['acq_date'] = df_final['acq_date'].dt.strftime('%Y-%m-%d')
            df_final.to_csv(file_path, index=False)

            log_lines.append(f"✅ {src_id}: Merged ({len(df_new)} new) | Total: {len(df_final)}")

        except Exception as e:
            log_lines.append(f"❌ {src_id}: System Error -> {str(e)}")

    # --- Transaction status AFTER download ---
    tx_after = get_transaction_status(map_key)
    tx_after_count = tx_after['current'] if tx_after else None

    # Calculate transactions used in this session
    if tx_before_count is not None and tx_after_count is not None:
        used_now = tx_after_count - tx_before_count
        log_lines.append(f"\n🔁 Transactions used in this download: {used_now}")

    # Assemble final Dash output: text log + transaction panel
    output = html.Div([
        html.Pre("\n".join(log_lines),
                 style={'fontFamily': 'monospace', 'fontSize': '13px',
                        'whiteSpace': 'pre-wrap', 'marginBottom': '16px'}),
        build_transaction_panel(map_key)
    ])

    return output


# ==========================================
# 5. STANDALONE TEST UI
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
