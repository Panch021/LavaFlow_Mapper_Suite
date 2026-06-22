import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime
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
# 1. DATA ENGINE
# ==========================================

def process_speed_data():
    """Calculate propagation speed and prevent 'inf' values."""
    folder = get_active_folder()
    if not folder: return None

    input_file = os.path.join(folder, "max_distance_per_day_VIIRS.csv")
    if not os.path.exists(input_file): return None

    df = pd.read_csv(input_file)
    df['date'] = pd.to_datetime(df['date_only'])
    df = df.sort_values('date').reset_index(drop=True)

    df['max_distance'] = df['distance_km'].cummax()
    df['prev_max'] = df['max_distance'].shift(1, fill_value=0)
    processed = df[df['distance_km'] > df['prev_max']].copy()

    if not processed.empty:
        processed['time_diff'] = processed['date'].diff().dt.total_seconds() / 3600  # hours
        processed['distance_diff'] = (processed['max_distance'] - processed['prev_max']) * 1000  # meters

        processed['speed'] = np.where(processed['time_diff'] > 0,
                                      processed['distance_diff'] / processed['time_diff'], 0)

        output_path = os.path.join(folder, "LavaFlow_propagation.csv")
        processed.to_csv(output_path, index=False)

    return processed


# ==========================================
# 2. DASHBOARD GENERATOR
# ==========================================

def get_layout():
    """Generate speed report with linear scale and external summary."""
    folder = get_active_folder()
    cfg = load_global_config()

    if not folder:
        return html.Div("⚠️ No active project found. Please configure a volcano first.",
                        style={'textAlign': 'center', 'padding': '20px', 'color': '#e74c3c'})

    speed_path = os.path.join(folder, "max_distance_per_day_VIIRS.csv")
    if not os.path.exists(speed_path):
        return html.Div([
            html.P("⚠️ No mapper results found.",
                   style={'color': '#e74c3c', 'fontWeight': 'bold', 'fontSize': '16px'}),
            html.P("Please run the 🌋 LavaFlow Mapper (Tab 4) first to generate the required data.",
                   style={'color': '#7f8c8d'})
        ], style={'textAlign': 'center', 'padding': '40px'})

    volcano_name = cfg.get('volcano', folder.replace("_", " ") if folder else 'Volcano')
    data = process_speed_data()

    if data is None or data.empty:
        return html.Div("No propagation data found (run Mapper first).",
                        style={'textAlign': 'center', 'padding': '20px', 'color': '#e74c3c'})

    start_str = data['date'].min().strftime('%Y-%m-%d')
    end_str = data['date'].max().strftime('%Y-%m-%d')

    # Drop NaN before computing speed statistics to avoid misleading results
    speed_valid = data['speed'].dropna()
    max_speed = speed_valid.max() if not speed_valid.empty else 0
    avg_speed = speed_valid.mean() if not speed_valid.empty else 0
    max_dist = data['max_distance'].max()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Max Distance Trace (Primary Y Axis)
    fig.add_trace(
        go.Scatter(x=data['date'], y=data['max_distance'], name="Max Distance",
                   mode='lines+markers', line=dict(color='black', width=2, dash='dash'),
                   marker=dict(size=8, symbol='circle')),
        secondary_y=False
    )

    # Speed Trace (Secondary Y Axis)
    fig.add_trace(
        go.Scatter(x=data['date'], y=data['speed'], name="Prop. Speed",
                   mode='lines+markers', line=dict(color='red', width=2, dash='dot'),
                   marker=dict(size=8, symbol='diamond')),
        secondary_y=True
    )

    # ---- Reference radius line on the Max Distance (primary) axis ----
    # Shown only when include_reference_radius=True in the config. Plotted as
    # a regular trace on the primary y-axis so it shares the same scale as
    # Max Distance. Appears in the legend, so the user can toggle it from
    # there without needing an extra button.
    has_ref_radius = bool(cfg.get('include_reference_radius'))
    if has_ref_radius:
        ref_radius_km = cfg.get('ref_radius_m', 5000) / 1000.0
        fig.add_trace(
            go.Scatter(
                x=[data['date'].min(), data['date'].max()],
                y=[ref_radius_km, ref_radius_km],
                mode='lines',
                line=dict(color='#1f77b4', width=2, dash='dash'),
                name=f"Ref. radius ({ref_radius_km:.2f} km)",
                hovertemplate=f"Ref. radius: {ref_radius_km:.2f} km<extra></extra>",
            ),
            secondary_y=False
        )

    fig.update_layout(
        title=dict(text=f"{volcano_name} - Lava Flow Propagation Speed<br>{start_str} to {end_str}",
                   x=0.5, font=dict(size=20)),
        template="plotly_white",
        height=600, width=1100,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        margin=dict(t=80, b=100, l=80, r=80)
    )

    fig.update_xaxes(title_text="Date", gridcolor='lightgrey')
    fig.update_yaxes(title_text="Maximum Distance (km)", secondary_y=False,
                     gridcolor='lightgrey', rangemode='tozero')
    fig.update_yaxes(title_text="Propagation Speed (m/h)", secondary_y=True,
                     type="linear", color="red", gridcolor='rgba(255,0,0,0.05)')

    master_config = {
        'toImageButtonOptions': {
            'format': 'png', 'filename': f"{volcano_name.replace(' ', '_')}_Speed",
            'height': 800, 'width': 1200, 'scale': 3
        },
        'displaylogo': False
    }

    summary_header = html.Div([
        html.Div([
            html.Strong("Max Distance: "), f"{max_dist:.2f} km"
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px',
                  'border': '1px solid #ddd', 'textAlign': 'center', 'flex': '1', 'margin': '5px'}),

        html.Div([
            html.Strong("Max Speed: "), f"{max_speed:.1f} m/h"
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px',
                  'border': '1px solid #ddd', 'textAlign': 'center', 'flex': '1', 'margin': '5px'}),

        html.Div([
            html.Strong("Mean Speed: "), f"{avg_speed:.1f} m/h"
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px',
                  'border': '1px solid #ddd', 'textAlign': 'center', 'flex': '1', 'margin': '5px'}),
    ], style={'display': 'flex', 'justifyContent': 'space-around', 'marginBottom': '20px',
              'maxWidth': '1100px', 'marginLeft': 'auto', 'marginRight': 'auto'})

    return html.Div([
        summary_header,
        dcc.Graph(figure=fig, config=master_config)
    ], style={'padding': '20px'})


if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    app.run(debug=True, port=8080)
