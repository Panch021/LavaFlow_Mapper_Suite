import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime, timedelta
from dash import html, dcc


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
    """Load variables from the active volcano subfolder config."""
    folder = get_active_folder()
    if not folder:
        return {}
    folder_name = os.path.basename(folder)          # e.g. 'Wolf_2022'
    config_path = os.path.join(folder, f"config_{folder_name}.txt")

    config = {}
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
# 1. DATA PROCESSING ENGINE
# ==========================================

def process_satellite_data(folder, filename, start_dt, end_dt):
    """Filter satellite data by date range using subfolder architecture."""
    file_path = os.path.join(folder, filename)
    if not os.path.exists(file_path): return None

    try:
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='latin-1')
    except Exception:
        return None

    # Robust multi-format date parser — handles ISO, DD/MM/YYYY, D/M/YY (NASA API short)
    parsed = pd.to_datetime(df['acq_date'], format='%Y-%m-%d', errors='coerce')
    if parsed.isna().all():
        parsed = pd.to_datetime(df['acq_date'], format='%d/%m/%Y', errors='coerce')
    if parsed.isna().all():
        parsed = pd.to_datetime(df['acq_date'], dayfirst=True, errors='coerce')
    df['acq_date_dt'] = parsed

    mask = (df['acq_date_dt'] >= start_dt) & (df['acq_date_dt'] <= end_dt)
    df = df[mask].copy()
    if df.empty: return None

    df['datetime'] = pd.to_datetime(
        df['acq_date_dt'].dt.strftime('%Y-%m-%d') + ' ' +
        df['acq_time'].astype(str).str.zfill(4),
        format='%Y-%m-%d %H%M'
    )
    return df


def get_cumulative_stats(df):
    """Calculate 12h interval cumulative statistics for power evolution."""
    if df is None or df.empty: return pd.DataFrame()

    time_seq = pd.date_range(
        start=df['datetime'].min().normalize(),
        end=df['datetime'].max().normalize() + timedelta(days=1),
        freq='12h'
    )

    results = []
    for t in time_seq:
        subset = df[df['datetime'] <= t]
        if subset.empty: continue
        frp = subset['frp']
        results.append({
            'timestamp': t,
            'mean': frp.mean(),
            'q25': frp.quantile(0.25),
            'median': frp.quantile(0.50),
            'q75': frp.quantile(0.75)
        })
    return pd.DataFrame(results)


def build_summary_header(sat_stats):
    """
    Builds the top summary panel showing the cross-satellite average of
    mean FRP and Q3 FRP. sat_stats is a list of dicts with keys 'name', 'mean', 'q3'.
    Only satellites with data are included in the averages.
    """
    valid = [s for s in sat_stats if s['mean'] is not None]
    if not valid:
        return html.Div()

    avg_of_means = np.mean([s['mean'] for s in valid])
    avg_of_q3 = np.mean([s['q3'] for s in valid])

    sat_colors = {'SNPP': '#e67e22', 'NOAA20': '#8e44ad', 'NOAA21': '#e74c3c'}

    box_style = {
        'padding': '12px 18px', 'borderRadius': '8px', 'border': '1px solid #dde',
        'backgroundColor': '#f8f9fa', 'textAlign': 'center', 'flex': '1', 'margin': '0 6px'
    }
    summary_box_style = {
        'padding': '12px 18px', 'borderRadius': '8px', 'border': '2px solid #2980b9',
        'backgroundColor': '#eaf4fb', 'textAlign': 'center', 'flex': '1', 'margin': '0 6px'
    }
    label_style = {'fontSize': '11px', 'color': '#7f8c8d', 'marginBottom': '2px'}
    value_style = {'fontSize': '20px', 'fontWeight': 'bold', 'color': '#2c3e50'}

    sat_boxes = []
    for s in valid:
        color = sat_colors.get(s['name'], '#555')
        sat_boxes.append(html.Div([
            html.Div(s['name'], style={**label_style, 'fontWeight': 'bold', 'color': color}),
            html.Div(f"Mean: {s['mean']:.1f} MW", style={'fontSize': '13px', 'color': '#2c3e50'}),
            html.Div(f"Q3: {s['q3']:.1f} MW", style={'fontSize': '13px', 'color': '#2980b9'}),
        ], style=box_style))

    summary_boxes = [
        html.Div([
            html.Div("Avg. of Means (all satellites)", style=label_style),
            html.Div(f"{avg_of_means:.1f} MW", style=value_style),
        ], style=summary_box_style),
        html.Div([
            html.Div("Avg. of Q3 (all satellites)", style=label_style),
            html.Div(f"{avg_of_q3:.1f} MW", style={**value_style, 'color': '#2980b9'}),
        ], style=summary_box_style),
    ]

    return html.Div([
        html.Div(sat_boxes + summary_boxes,
                 style={'display': 'flex', 'justifyContent': 'center',
                        'flexWrap': 'wrap', 'gap': '6px', 'padding': '10px 0'})
    ], style={
        'margin': '10px 0 15px 0', 'padding': '12px',
        'border': '1px solid #dde', 'borderRadius': '10px',
        'backgroundColor': 'white'
    })


# ==========================================
# 2. MASTER REPORT GENERATOR (A4 RATIO)
# ==========================================

def get_layout():
    """Generate the unified A4 report with histograms and temporal trends."""
    folder = get_active_folder()
    if not folder:
        return html.Div("No active project found. Save configuration first.")

    folder_name = os.path.basename(folder)   # e.g. 'Wolf' not 'projects/Wolf'
    sat_files = [
        f"historical_VIIRS_SNPP_NRT_{folder_name}.csv",
        f"historical_VIIRS_NOAA20_NRT_{folder_name}.csv",
        f"historical_VIIRS_NOAA21_NRT_{folder_name}.csv"
    ]
    if not any(os.path.exists(os.path.join(folder, f)) for f in sat_files):
        return html.Div([
            html.P("⚠️ No satellite data found.",
                   style={'color': '#e74c3c', 'fontWeight': 'bold', 'fontSize': '16px'}),
            html.P("Please run 🛰️ FIRMS Download (Tab 1) first to download satellite data.",
                   style={'color': '#7f8c8d'})
        ], style={'textAlign': 'center', 'padding': '40px'})

    cfg = load_global_config()
    volcano_name = cfg.get('volcano', folder_name.replace("_", " "))

    start_str = cfg.get('start_day_str', 'N/A').split()[0]
    end_str = cfg.get('end_day_str', 'N/A').split()[0]

    # Robust date parsing: tolerates formats with or without time component
    start_dt = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True, errors='coerce')
    end_dt = pd.to_datetime(cfg.get('end_day_str'), dayfirst=True, errors='coerce')

    if pd.isna(start_dt) or pd.isna(end_dt):
        return html.Div("Error: Invalid date format in config. Expected DD/MM/YYYY or DD/MM/YYYY HH:MM.")

    sat_configs = [
        {"file": f"historical_VIIRS_SNPP_NRT_{folder_name}.csv",  "name": "SNPP",   "color": "orange"},
        {"file": f"historical_VIIRS_NOAA20_NRT_{folder_name}.csv", "name": "NOAA20", "color": "purple"},
        {"file": f"historical_VIIRS_NOAA21_NRT_{folder_name}.csv", "name": "NOAA21", "color": "red"}
    ]

    fig = make_subplots(
        rows=3, cols=2,
        horizontal_spacing=0.10,
        vertical_spacing=0.07,
        subplot_titles=(
            "SNPP Histogram", "SNPP Cumulative Evolution",
            "NOAA20 Histogram", "NOAA20 Cumulative Evolution",
            "NOAA21 Histogram", "NOAA21 Cumulative Evolution"
        )
    )

    # Collect per-satellite stats for the summary header
    sat_stats = []

    for i, sat_cfg in enumerate(sat_configs):
        row = i + 1
        data = process_satellite_data(folder, sat_cfg["file"], start_dt, end_dt)

        if data is None:
            fig.add_annotation(text="No data found in range", row=row, col=1, showarrow=False)
            sat_stats.append({'name': sat_cfg['name'], 'mean': None, 'q3': None})
            continue

        frp_vals = data['frp']
        m = {
            'min': frp_vals.min(), 'q1': frp_vals.quantile(0.25), 'median': frp_vals.median(),
            'mean': frp_vals.mean(), 'q3': frp_vals.quantile(0.75), 'p95': frp_vals.quantile(0.95),
            'max': frp_vals.max()
        }

        # Accumulate stats for summary panel
        sat_stats.append({'name': sat_cfg['name'], 'mean': m['mean'], 'q3': m['q3']})

        # --- COL 1: FREQUENCY HISTOGRAMS ---
        fig.add_trace(go.Histogram(
            x=frp_vals, xbins=dict(size=10), marker_color=sat_cfg['color'], opacity=0.5,
            showlegend=False,
            hovertemplate="FRP Range: %{x} MW<br>Count: %{y}<extra></extra>"
        ), row=row, col=1)

        fig.add_vline(x=m['mean'], line_dash="solid", line_color="black", line_width=1.5, row=row, col=1)
        fig.add_vline(x=m['q3'], line_dash="dot", line_color="blue", line_width=2, row=row, col=1)

        stats_text = (f"<b>{sat_cfg['name']} Stats (MW)</b><br>min: {m['min']:.1f}<br>q1: {m['q1']:.1f}<br>"
                      f"median: {m['median']:.1f}<br>mean: {m['mean']:.1f}<br>"
                      f"q3: {m['q3']:.1f}<br>p95: {m['p95']:.1f}<br>max: {m['max']:.1f}")

        axis_idx = 2 * i + 1
        xref_val = "x domain" if axis_idx == 1 else f"x{axis_idx} domain"
        yref_val = "y domain" if axis_idx == 1 else f"y{axis_idx} domain"

        fig.add_annotation(
            xref=xref_val, yref=yref_val, x=0.98, y=0.95,
            text=stats_text, showarrow=False, align="right", font=dict(size=10, color="black")
        )

        # --- COL 2: CUMULATIVE STATISTICAL EVOLUTION ---
        stats_df = get_cumulative_stats(data)
        if not stats_df.empty:
            fig.add_trace(go.Scatter(
                x=stats_df['timestamp'], y=stats_df['mean'], name='Mean',
                line=dict(color='black', dash='solid', width=2),
                hovertemplate="Mean: %{y:.1f} MW<extra></extra>",
                legendgroup="mean", showlegend=(i == 0)), row=row, col=2)

            fig.add_trace(go.Scatter(
                x=stats_df['timestamp'], y=stats_df['q75'], name='Q3 (75%)',
                line=dict(color='blue', dash='dot', width=2),
                hovertemplate="Q3: %{y:.1f} MW<extra></extra>",
                legendgroup="q3", showlegend=(i == 0)), row=row, col=2)

            fig.add_trace(go.Scatter(
                x=stats_df['timestamp'], y=stats_df['median'], name='Median',
                line=dict(color='green', width=1.5),
                hovertemplate="Median: %{y:.1f} MW<extra></extra>",
                legendgroup="median", showlegend=(i == 0)), row=row, col=2)

        fig.update_xaxes(title_text="FRP (MW)", range=[0, m['p95'] * 1.9], row=row, col=1)
        fig.update_yaxes(title_text="Frequency", row=row, col=1)
        fig.update_yaxes(title_text="FRP (MW)", row=row, col=2)

    fig.update_layout(
        height=1400,
        width=990,
        title=dict(
            text=f"FRP Statistical Analysis: {volcano_name}<br>Period: {start_str} - {end_str}",
            x=0.5, font=dict(size=22)
        ),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.08, xanchor="center", x=0.5, font=dict(size=12)),
        margin=dict(t=130, b=100, l=80, r=40)
    )

    master_config = {
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f"{volcano_name.replace(' ', '_')}_FRP_Report",
            'height': 1400,
            'width': 990,
            'scale': 3
        },
        'displaylogo': False
    }

    summary_header = build_summary_header(sat_stats)

    return html.Div([
        summary_header,
        dcc.Graph(figure=fig, config=master_config)
    ], style={'padding': '10px'})


# ==========================================
# 3. STANDALONE EXECUTION
# ==========================================

if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    app.run(debug=True, port=8065)
