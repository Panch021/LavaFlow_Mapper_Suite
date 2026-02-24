import dash
from dash import dcc, html, Input, Output, State
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime, date


# ==========================================
# 1. DATA AND CONFIG HELPERS
# ==========================================

def load_global_config():
    """Reads global variables from config.txt."""
    config = {}
    if not os.path.exists("config.txt"): return config
    with open("config.txt", "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config


def load_historical_data():
    """Consolidated loader for sensor files in the root directory."""
    # Order for stacking: Bottom to Top
    files = {
        'MODIS (AQUA/TERRA)': 'historical_MODIS_NRT.csv',
        'VIIRS (SNPP)': 'historical_VIIRS_SNPP_NRT.csv',
        'VIIRS (NOAA-20)': 'historical_VIIRS_NOAA20_NRT.csv',
        'VIIRS (NOAA-21)': 'historical_VIIRS_NOAA21_NRT.csv'
    }
    all_dfs = []
    for label, filename in files.items():
        if os.path.exists(filename):
            df = pd.read_csv(filename)
            df['acq_date'] = pd.to_datetime(df['acq_date'], dayfirst=True)
            df['source'] = label
            all_dfs.append(df[['acq_date', 'source', 'frp']])
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


# ==========================================
# 2. DASHBOARD LAYOUT
# ==========================================

def get_layout():
    """Returns the English dashboard interface with optimized export config."""
    cfg = load_global_config()
    volcano = cfg.get('volcano', 'Sangay')

    return html.Div([
        html.Div([
            html.H2(f"Thermal Anomaly Statistics: {volcano}", style={'margin': '0', 'color': '#2c3e50'}),
            html.P("Weekly and monthly cumulative analysis.", style={'color': '#7f8c8d'})
        ], style={'padding': '20px', 'backgroundColor': 'white', 'borderBottom': '1px solid #eee'}),

        html.Div([
            # Control Sidebar
            html.Div([
                html.H4("Visualization Controls"),
                html.Label("1. Analysis Period (Independent):", style={'fontWeight': 'bold'}),
                dcc.DatePickerRange(
                    id='stats-date-picker',
                    display_format='DD/MM/YYYY',
                    start_date=date(2021, 1, 1),
                    end_date=date.today(),
                    style={'width': '100%', 'marginTop': '5px'}
                ),
                html.Br(), html.Br(),
                html.Label("2. Week Starting Day:", style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='week-start-dropdown',
                    options=[
                        {'label': 'Monday', 'value': 0}, {'label': 'Tuesday', 'value': 1},
                        {'label': 'Wednesday', 'value': 2}, {'label': 'Thursday', 'value': 3},
                        {'label': 'Friday', 'value': 4}, {'label': 'Saturday', 'value': 5},
                        {'label': 'Sunday', 'value': 6}
                    ],
                    value=3,  # Default Thursday as in R
                    clearable=False,
                    style={'marginTop': '5px'}
                ),
                html.Br(),
                html.Button("📊 UPDATE CHARTS", id="btn-gen-stats", n_clicks=0,
                            style={'width': '100%', 'padding': '12px', 'backgroundColor': '#3498db', 'color': 'white',
                                   'border': 'none', 'borderRadius': '5px', 'fontWeight': 'bold'}),
                html.Br(),
                html.P("Note: Use the camera icon on the top right of the chart to save as high-res PNG.",
                       style={'fontSize': '12px', 'color': '#7f8c8d', 'marginTop': '15px'})
            ], style={'width': '22%', 'padding': '25px', 'borderRight': '1px solid #eee',
                      'backgroundColor': '#fcfcfc'}),

            # Main Graph Area
            html.Div([
                dcc.Graph(
                    id='anomalies-count-plot',
                    style={'height': '85vh'},
                    # HIGH-RESOLUTION EXPORT CONFIGURATION
                    config={
                        'toImageButtonOptions': {
                            'format': 'png',
                            'filename': f'{volcano}_thermal_stats',
                            'height': 1400,
                            'width': 1200,
                            'scale': 3  # Equivalent to 300 DPI
                        },
                        'displaylogo': False
                    }
                )
            ], style={'width': '76%', 'padding': '10px'})
        ], style={'display': 'flex'})
    ], style={'fontFamily': 'Arial, sans-serif'})


# ==========================================
# 3. CALLBACKS & PLOTTING LOGIC
# ==========================================

def register_callbacks(app):
    """Registers the stats generation logic."""

    @app.callback(
        Output('anomalies-count-plot', 'figure'),
        Input('btn-gen-stats', 'n_clicks'),
        [State('stats-date-picker', 'start_date'),
         State('stats-date-picker', 'end_date'),
         State('week-start-dropdown', 'value')],
        prevent_initial_call=False
    )
    def update_charts(n, start, end, week_day):
        # Load data
        df_raw = load_historical_data()
        if df_raw.empty: return go.Figure()

        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        df = df_raw[(df_raw['acq_date'] >= start_dt) & (df_raw['acq_date'] <= end_dt)].copy()

        # 1. DYNAMIC TICKS LOGIC
        diff_days = (end_dt - start_dt).days
        tick_val = "M6" if diff_days > 730 else "M3" if diff_days > 365 else "M1"

        # 2. AGGREGATIONS
        df['week_label'] = df['acq_date'] - pd.to_timedelta((df['acq_date'].dt.dayofweek - week_day) % 7, unit='d')
        weekly = df.groupby(['week_label', 'source']).size().reset_index(name='count')

        df['month_label'] = df['acq_date'].dt.to_period('M').dt.to_timestamp()
        monthly = df.groupby(['month_label', 'source']).size().reset_index(name='count')

        fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12)

        # STACK ORDER: MODIS (Bottom) to VIIRS NOAA-21 (Top)
        sensors = ['MODIS (AQUA/TERRA)', 'VIIRS (SNPP)', 'VIIRS (NOAA-20)', 'VIIRS (NOAA-21)']
        colors = ['blue', 'orange', 'purple', 'red']

        for src, color in zip(sensors, colors):
            w_data = weekly[weekly['source'] == src]
            m_data = monthly[monthly['source'] == src]

            # Weekly Trace
            fig.add_trace(go.Bar(
                x=w_data['week_label'], y=w_data['count'], name=src, marker_color=color,
                hovertemplate="Date: %{x|%d %b %Y}<br>Anomalies: %{y}<extra></extra>",
                legendgroup=src
            ), row=1, col=1)

            # Monthly Trace
            fig.add_trace(go.Bar(
                x=m_data['month_label'], y=m_data['count'], name=src, marker_color=color,
                hovertemplate="Month: %{x|%b %Y}<br>Anomalies: %{y}<extra></extra>",
                legendgroup=src, showlegend=False
            ), row=2, col=1)

        # Statistical Lines
        stats_vals = {'Mean': 70, 'SD': 140, '2xSD': 211}
        stats_colors = {'Mean': 'limegreen', 'SD': 'orange', '2xSD': 'black'}

        for label, val in stats_vals.items():
            fig.add_shape(type="line", x0=start_dt, x1=end_dt, y0=val, y1=val,
                          line=dict(color=stats_colors[label], width=1.5, dash="dash"), row=1, col=1)

        # Y-Axis Labels
        fig.update_yaxes(title_text="Total number of thermal anomalies (weekly)", row=1, col=1)
        fig.update_yaxes(title_text="Total number of thermal anomalies (monthly)", row=2, col=1)

        # Layout and Legend
        cfg = load_global_config()
        vol_name = cfg.get('volcano', 'Sangay')
        fig.update_layout(
            title=dict(
                text=f"FIRMS: thermal anomalies in {vol_name} volcano<br>{start_dt.strftime('%B %Y')} - {end_dt.strftime('%B %Y')}",
                x=0.5, font=dict(size=20, color='black')),
            barmode='stack', template="plotly_white",
            legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5, title="Sensor (satellite):"),
            margin=dict(t=100, b=100, l=80, r=40)
        )

        # Dynamic Ticks
        fig.update_xaxes(tickangle=90, dtick=tick_val, tickformat="%d %b %y", row=1, col=1)
        fig.update_xaxes(tickangle=90, dtick=tick_val, tickformat="%b %Y", row=2, col=1)

        return fig


# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == '__main__':
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True, port=8070)