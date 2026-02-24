import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import glob
import os
from datetime import datetime, timedelta
from dash import html, dcc


# ==========================================
# 0. CONFIGURATION LOADER
# ==========================================
def load_global_config():
    """Load variables from config.txt."""
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
# 1. DATA PROCESSING
# ==========================================
def process_satellite_data(config_sat, start_dt, end_dt):
    """Filter satellite data by date range."""
    files = glob.glob(config_sat["pattern"])
    if not files: return None
    df = pd.read_csv(files[0])
    df['acq_date_dt'] = pd.to_datetime(df['acq_date'], dayfirst=True)
    mask = (df['acq_date_dt'] >= start_dt) & (df['acq_date_dt'] <= end_dt)
    df = df[mask].copy()
    if df.empty: return None
    df['datetime'] = pd.to_datetime(df['acq_date_dt'].dt.strftime('%Y-%m-%d') + ' ' +
                                    df['acq_time'].astype(str).str.zfill(4), format='%Y-%m-%d %H%M')
    return df


def get_cumulative_stats(df):
    """Calculate 12h cumulative statistics."""
    if df is None or df.empty: return pd.DataFrame()
    time_seq = pd.date_range(start=df['datetime'].min().normalize(),
                             end=df['datetime'].max().normalize() + timedelta(days=1), freq='12h')
    results = []
    for t in time_seq:
        subset = df[df['datetime'] <= t]
        if subset.empty: continue
        frp = subset['frp']
        results.append({'timestamp': t, 'mean': frp.mean(), 'q25': frp.quantile(0.25),
                        'median': frp.quantile(0.50), 'q75': frp.quantile(0.75)})
    return pd.DataFrame(results)


# ==========================================
# 2. MASTER DASHBOARD GENERATOR (A4 RATIO)
# ==========================================
def get_layout():
    """Generate unified A4 report figure."""
    cfg = load_global_config()
    volcano_name = cfg.get('volcano', 'Volcano')
    start_str = cfg.get('start_day_str', 'N/A').split()[0]
    end_str = cfg.get('end_day_str', 'N/A').split()[0]
    start_dt = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True)
    end_dt = pd.to_datetime(cfg.get('end_day_str'), dayfirst=True)

    sat_configs = [
        {"pattern": "*SNPP*.csv", "name": "SNPP", "color": "orange"},
        {"pattern": "*NOAA20*.csv", "name": "NOAA20", "color": "purple"},
        {"pattern": "*NOAA21*.csv", "name": "NOAA21", "color": "red"}
    ]

    # Subplot titles with satellite name for both charts
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

    for i, config in enumerate(sat_configs):
        row = i + 1
        data = process_satellite_data(config, start_dt, end_dt)

        if data is None:
            fig.add_annotation(text="No data found", row=row, col=1, showarrow=False)
            continue

        frp_vals = data['frp']
        m = {'min': frp_vals.min(), 'q1': frp_vals.quantile(0.25), 'median': frp_vals.median(),
             'mean': frp_vals.mean(), 'q3': frp_vals.quantile(0.75), 'p95': frp_vals.quantile(0.95),
             'max': frp_vals.max()}

        # --- COL 1: HISTOGRAMS ---
        fig.add_trace(go.Histogram(
            x=frp_vals, xbins=dict(size=10), marker_color=config['color'], opacity=0.5,
            showlegend=False
        ), row=row, col=1)

        # Vertical lines: Mean (solid), Q3 (dot)
        fig.add_vline(x=m['mean'], line_dash="solid", line_color="black", line_width=1.5, row=row, col=1)
        fig.add_vline(x=m['q3'], line_dash="dot", line_color="blue", line_width=2, row=row, col=1)

        # Statistical labels (clean text)
        stats_text = (f"<b>{config['name']} Stats (MW)</b><br>min: {m['min']:.1f}<br>q1: {m['q1']:.1f}<br>"
                      f"median: {m['median']:.1f}<br>mean: {m['mean']:.1f}<br>"
                      f"q3: {m['q3']:.1f}<br>p95: {m['p95']:.1f}<br>max: {m['max']:.1f}")

        axis_idx = 2 * i + 1
        xref_val = "x domain" if axis_idx == 1 else f"x{axis_idx} domain"
        yref_val = "y domain" if axis_idx == 1 else f"y{axis_idx} domain"

        fig.add_annotation(
            xref=xref_val, yref=yref_val, x=0.98, y=0.95,
            text=stats_text, showarrow=False, align="right", font=dict(size=10, color="black")
        )

        # --- COL 2: CUMULATIVE EVOLUTION ---
        stats_df = get_cumulative_stats(data)
        if not stats_df.empty:
            # Styled lines: Mean (solid), Q3 (dot)
            fig.add_trace(go.Scatter(
                x=stats_df['timestamp'], y=stats_df['mean'], name='Mean',
                line=dict(color='black', dash='solid', width=2),
                legendgroup="mean", showlegend=(i == 0)), row=row, col=2)

            fig.add_trace(go.Scatter(
                x=stats_df['timestamp'], y=stats_df['q75'], name='Q3 (75%)',
                line=dict(color='blue', dash='dot', width=2),
                legendgroup="q3", showlegend=(i == 0)), row=row, col=2)

            fig.add_trace(go.Scatter(
                x=stats_df['timestamp'], y=stats_df['median'], name='Median',
                line=dict(color='green', width=1.5),
                legendgroup="median", showlegend=(i == 0)), row=row, col=2)

        # Set axes labels
        fig.update_xaxes(title_text="FRP (MW)", range=[0, m['p95'] * 1.9], row=row, col=1)
        fig.update_yaxes(title_text="Frequency", row=row, col=1)
        fig.update_yaxes(title_text="FRP (MW)", row=row, col=2)

    # A4 Portrait Layout
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

    # HQ Export config
    master_config = {
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f"{volcano_name}_FRP_Statistics",
            'height': 1400,
            'width': 990,
            'scale': 3
        },
        'displaylogo': False
    }

    return html.Div([dcc.Graph(figure=fig, config=master_config)], style={'padding': '10px'})


if __name__ == "__main__":
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    app.run(debug=True, port=8070)