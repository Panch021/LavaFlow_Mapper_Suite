import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime
from dash import html, dcc


# ==========================================
# 0. CONFIGURATION LOADER
# ==========================================
def load_global_config():
    """Load configuration parameters from config.txt."""
    config = {}
    config_path = "config.txt"
    if not os.path.exists(config_path): return config
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
    """Calculate propagation speed and cumulative distances."""
    input_file = "max_distance_per_day_VIIRS.csv"
    if not os.path.exists(input_file): return None

    # Load and preprocess data
    df = pd.read_csv(input_file)
    df['date'] = pd.to_datetime(df['date_only'])
    df = df.sort_values('date').reset_index(drop=True)

    # Calculate cumulative maximum distance
    df['max_distance'] = df['distance_km'].cummax()

    # Identify breakthrough events (new maximums only)
    df['prev_max'] = df['max_distance'].shift(1, fill_value=0)
    processed = df[df['distance_km'] > df['prev_max']].copy()

    # Calculate Speed (m/h)
    if not processed.empty:
        processed['time_diff'] = processed['date'].diff().dt.total_seconds() / 3600  # hours
        processed['distance_diff'] = (processed['max_distance'] - processed['prev_max']) * 1000  # meters
        processed['speed'] = processed['distance_diff'] / processed['time_diff']
        # Save logic-processed file
        processed.to_csv("LavaFlow_propagation.csv", index=False)

    return processed


# ==========================================
# 2. DASHBOARD GENERATOR
# ==========================================
def get_layout():
    """Generate the interactive dual-axis speed report (Landscape)."""
    cfg = load_global_config()
    volcano_name = cfg.get('volcano', 'Volcano')
    data = process_speed_data()

    if data is None or data.empty:
        return html.Div("No propagation data found (no new max. distances recorded).",
                        style={'textAlign': 'center', 'padding': '20px', 'color': '#e74c3c'})

    start_str = data['date'].min().strftime('%Y-%m-%d')
    end_str = data['date'].max().strftime('%Y-%m-%d')

    # Create figure with secondary Y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. Distance Trace (Primary Y)
    fig.add_trace(
        go.Scatter(x=data['date'], y=data['max_distance'], name="Max Distance",
                   mode='lines+markers', line=dict(color='black', width=2, dash='dash'),
                   marker=dict(size=8, symbol='circle')),
        secondary_y=False
    )

    # 2. Speed Trace (Secondary Y - Log Scale)
    fig.add_trace(
        go.Scatter(x=data['date'], y=data['speed'], name="Prop. Speed",
                   mode='lines+markers', line=dict(color='red', width=2, dash='dot'),
                   marker=dict(size=8, symbol='diamond')),
        secondary_y=True
    )

    # Statistics Summary
    max_dist = data['max_distance'].max()
    max_speed = data['speed'].max() if not data['speed'].isna().all() else 0
    avg_speed = data['speed'].mean() if not data['speed'].isna().all() else 0

    stats_text = (f"<b>Propagation Summary</b><br>"
                  f"Max Distance: {max_dist:.2f} km<br>"
                  f"Max Speed: {max_speed:.1f} m/h<br>"
                  f"Mean Speed: {avg_speed:.1f} m/h")

    fig.add_annotation(
        xref="paper", yref="paper", x=0.02, y=0.98,
        text=stats_text, showarrow=False, align="left",
        font=dict(size=12, color="black")
    )

    # UPDATED: Landscape Layout Settings
    fig.update_layout(
        title=dict(text=f"{volcano_name} - Lava Flow Propagation<br>{start_str} to {end_str}",
                   x=0.5, font=dict(size=20)),
        template="plotly_white",
        height=700,  # Reverted to landscape
        width=1100,  # Reverted to landscape
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(t=100, b=100, l=80, r=80)
    )

    fig.update_xaxes(title_text="Date", gridcolor='lightgrey')
    fig.update_yaxes(title_text="Maximum Distance (km)", secondary_y=False, gridcolor='lightgrey')
    fig.update_yaxes(title_text="Propagation Speed (m/h)", secondary_y=True,
                     type="log", color="red", gridcolor='rgba(255,0,0,0.05)')

    # UPDATED: High-Resolution Landscape Export
    master_config = {
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f"{volcano_name}_LavaFlow_Speed",
            'height': 800,
            'width': 1200,
            'scale': 3
        },
        'displaylogo': False
    }

    return html.Div([
        dcc.Graph(figure=fig, config=master_config)
    ], style={'padding': '10px'})


if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    app.run(debug=True, port=8095)