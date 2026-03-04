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

def get_active_folder():
    """Reads the current volcano name and sanitizes it for folder paths."""
    if os.path.exists("active_volcano.txt"):
        with open("active_volcano.txt", "r") as f:
            vol_name = f.read().strip()
            return vol_name.replace(" ", "_")
    return None


def load_global_config():
    """Load configuration parameters from the active volcano subfolder."""
    folder = get_active_folder()
    config_path = "config.txt"
    if folder:
        specific_path = os.path.join(folder, f"config_{folder}.txt")
        if os.path.exists(specific_path): config_path = specific_path

    config = {}
    if not os.path.exists(config_path): return config
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config


def load_historical_data():
    """Consolidated loader for sensor files in the specific volcano folder."""
    folder = get_active_folder()
    if not folder: return pd.DataFrame()
    files = {
        'MODIS (AQUA/TERRA)': f'historical_MODIS_NRT_{folder}.csv',
        'VIIRS (SNPP)': f'historical_VIIRS_SNPP_NRT_{folder}.csv',
        'VIIRS (NOAA-20)': f'historical_VIIRS_NOAA20_NRT_{folder}.csv',
        'VIIRS (NOAA-21)': f'historical_VIIRS_NOAA21_NRT_{folder}.csv'
    }
    all_dfs = []
    for label, filename in files.items():
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df['acq_date'] = pd.to_datetime(df['acq_date'], format='%d/%m/%Y', errors='coerce')
            df['source'] = label
            all_dfs.append(df[['acq_date', 'source', 'frp']])
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def compute_summary_stats(df, start_dt, end_dt, week_day):
    """
    Computes summary statistics for the sidebar panel:
    - Total anomalies on the last day with data
    - Total and peak anomalies for the last week and last month in the range
    - Peak week and peak month totals across the full analysis period
    """
    if df.empty:
        return {}

    df_range = df[(df['acq_date'] >= start_dt) & (df['acq_date'] <= end_dt)].copy()
    if df_range.empty:
        return {}

    last_day = df_range['acq_date'].max()

    # --- Last day ---
    total_last_day = int((df_range['acq_date'] == last_day).sum())

    # --- Last week: the complete week block containing last_day ---
    # Align last_day to the start of its week using the selected week_day
    days_since_start = (last_day.dayofweek - week_day) % 7
    last_week_start = last_day - pd.Timedelta(days=int(days_since_start))
    last_week_end = last_week_start + pd.Timedelta(days=6)
    mask_last_week = (df_range['acq_date'] >= last_week_start) & (df_range['acq_date'] <= last_week_end)
    total_last_week = int(mask_last_week.sum())

    # --- Last month: calendar month of last_day ---
    last_month_start = last_day.replace(day=1)
    last_month_end = (last_month_start + pd.offsets.MonthEnd(1))
    mask_last_month = (df_range['acq_date'] >= last_month_start) & (df_range['acq_date'] <= last_month_end)
    total_last_month = int(mask_last_month.sum())

    # --- Peak week across the full period ---
    df_range['week_label'] = df_range['acq_date'] - pd.to_timedelta(
        (df_range['acq_date'].dt.dayofweek - week_day) % 7, unit='d'
    )
    # Only count weeks that start on or after start_dt to exclude partial first week
    full_week_start = start_dt + pd.Timedelta(days=(week_day - start_dt.dayofweek) % 7)
    weekly_totals = df_range[df_range['week_label'] >= full_week_start].groupby('week_label').size()
    peak_week = int(weekly_totals.max()) if not weekly_totals.empty else 0

    # --- Peak month across the full period ---
    df_range['month_label'] = df_range['acq_date'].dt.to_period('M').dt.to_timestamp()
    monthly_totals = df_range.groupby('month_label').size()
    peak_month = int(monthly_totals.max()) if not monthly_totals.empty else 0

    return {
        'last_day': last_day.strftime('%d/%m/%Y'),
        'total_last_day': total_last_day,
        'last_week_start': last_week_start.strftime('%d/%m/%Y'),
        'last_week_end': last_week_end.strftime('%d/%m/%Y'),
        'total_last_week': total_last_week,
        'last_month': last_day.strftime('%B %Y'),
        'total_last_month': total_last_month,
        'peak_week': peak_week,
        'peak_month': peak_month,
    }


def build_stats_panel(stats):
    """Renders the summary statistics sidebar panel from a stats dict."""
    if not stats:
        return html.Div("No data available.", style={'color': '#999', 'fontSize': '12px', 'marginTop': '10px'})

    box_style = {
        'padding': '10px 12px', 'borderRadius': '6px', 'marginBottom': '8px',
        'border': '1px solid #dde', 'backgroundColor': '#f0f4f8'
    }
    label_style = {'fontSize': '11px', 'color': '#7f8c8d', 'marginBottom': '2px'}
    value_style = {'fontSize': '18px', 'fontWeight': 'bold', 'color': '#2c3e50'}
    sub_style = {'fontSize': '11px', 'color': '#95a5a6'}
    peak_style = {'fontSize': '13px', 'fontWeight': 'bold', 'color': '#e74c3c'}

    return html.Div([
        html.Hr(style={'margin': '15px 0 10px 0'}),
        html.H5("📊 Period Summary", style={'color': '#2c3e50', 'marginBottom': '10px'}),

        html.Div([
            html.Div("Last day with data (all sensors):", style=label_style),
            html.Div(stats['total_last_day'], style=value_style),
            html.Div(stats['last_day'], style=sub_style),
        ], style=box_style),

        html.Div([
            html.Div("Last week (all sensors):", style=label_style),
            html.Div(stats['total_last_week'], style=value_style),
            html.Div(f"{stats['last_week_start']} – {stats['last_week_end']}", style=sub_style),
        ], style=box_style),

        html.Div([
            html.Div("Last month (all sensors):", style=label_style),
            html.Div(stats['total_last_month'], style=value_style),
            html.Div(stats['last_month'], style=sub_style),
        ], style=box_style),

        html.Hr(style={'margin': '10px 0'}),
        html.Div("Peak values in period:", style={**label_style, 'fontWeight': 'bold'}),
        html.Div([
            html.Span("Week max: ", style=label_style),
            html.Span(f"{stats['peak_week']} anomalies", style=peak_style),
        ], style={'marginBottom': '5px'}),
        html.Div([
            html.Span("Month max: ", style=label_style),
            html.Span(f"{stats['peak_month']} anomalies", style=peak_style),
        ]),
    ], style={'marginTop': '5px'})


# ==========================================
# 2. DASHBOARD LAYOUT
# ==========================================

def get_layout(start_date=None, end_date=None):
    cfg = load_global_config()
    volcano = cfg.get('volcano', 'Volcano Name')
    if start_date is None: start_date = datetime(2026, 1, 1)
    if end_date is None: end_date = datetime(2026, 5, 1)

    return html.Div([
        html.Div([
            html.H2(f"Thermal Anomaly Statistics: {volcano}", style={'margin': '0', 'color': '#2c3e50'}),
            html.P("Weekly and monthly cumulative analysis.", style={'color': '#7f8c8d'})
        ], style={'padding': '20px', 'backgroundColor': 'white', 'borderBottom': '2px solid #eee'}),

        html.Div([
            html.Div([
                html.H4("Visualization Controls"),
                html.Label("1. Analysis Period:", style={'fontWeight': 'bold'}),
                dcc.DatePickerRange(
                    id='stats-date-picker',
                    display_format='DD/MM/YYYY',
                    start_date=start_date.date() if isinstance(start_date, datetime) else start_date,
                    end_date=end_date.date() if isinstance(end_date, datetime) else end_date,
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
                    value=3,  # Default Thursday
                    clearable=False,
                    style={'marginTop': '5px'}
                ),
                html.Br(),
                html.Button("📊 UPDATE CHARTS", id="btn-gen-stats", n_clicks=0,
                            style={'width': '100%', 'padding': '12px', 'backgroundColor': '#3498db', 'color': 'white',
                                   'border': 'none', 'borderRadius': '5px', 'fontWeight': 'bold'}),

                # Summary stats panel — updated by callback
                html.Div(id='anomalies-summary-panel')

            ], style={'width': '22%', 'padding': '25px', 'borderRight': '1px solid #eee',
                      'backgroundColor': '#fcfcfc'}),

            html.Div([
                dcc.Graph(
                    id='anomalies-count-plot',
                    style={'height': '85vh'},
                    config={
                        'toImageButtonOptions': {
                            'format': 'png',
                            'filename': f'{volcano.replace(" ", "_")}_thermal_stats',
                            'height': 1400, 'width': 1200, 'scale': 3
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
    @app.callback(
        [Output('anomalies-count-plot', 'figure'),
         Output('anomalies-summary-panel', 'children')],
        Input('btn-gen-stats', 'n_clicks'),
        [State('stats-date-picker', 'start_date'),
         State('stats-date-picker', 'end_date'),
         State('week-start-dropdown', 'value')],
        prevent_initial_call=False
    )
    def update_charts(n, start, end, week_day):
        df_raw = load_historical_data()
        if df_raw.empty:
            return go.Figure(), build_stats_panel({})

        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        df = df_raw[(df_raw['acq_date'] >= start_dt) & (df_raw['acq_date'] <= end_dt)].copy()

        if df.empty:
            return go.Figure(), build_stats_panel({})

        # Compute sidebar summary stats
        stats = compute_summary_stats(df_raw, start_dt, end_dt, week_day)
        summary_panel = build_stats_panel(stats)

        # Constant: 1 week in milliseconds for Plotly
        MS_IN_WEEK = 7 * 24 * 60 * 60 * 1000

        # Dynamic tick spacing to avoid overlapping labels
        diff_days = (end_dt - start_dt).days
        if diff_days <= 120:
            weekly_tick_step = 1
        elif diff_days <= 365:
            weekly_tick_step = 2
        elif diff_days <= 730:
            weekly_tick_step = 4
        else:
            weekly_tick_step = 8

        tick_val_w = weekly_tick_step * MS_IN_WEEK

        # Align week labels to the selected week_day
        df['week_label'] = df['acq_date'] - pd.to_timedelta(
            (df['acq_date'].dt.dayofweek - week_day) % 7, unit='d'
        )

        # Drop the partial first week: only keep rows whose week starts on or after
        # the first complete week boundary within the analysis range
        first_full_week_start = start_dt + pd.Timedelta(days=(week_day - start_dt.dayofweek) % 7)
        df = df[df['week_label'] >= first_full_week_start]

        weekly = df.groupby(['week_label', 'source']).size().reset_index(name='count')
        df['month_label'] = df['acq_date'].dt.to_period('M').dt.to_timestamp()
        monthly = df.groupby(['month_label', 'source']).size().reset_index(name='count')

        fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.15)
        sensors = ['MODIS (AQUA/TERRA)', 'VIIRS (SNPP)', 'VIIRS (NOAA-20)', 'VIIRS (NOAA-21)']
        colors = ['blue', 'orange', 'purple', 'red']

        for src, color in zip(sensors, colors):
            w_data = weekly[weekly['source'] == src]
            m_data = monthly[monthly['source'] == src]

            # Shift x by half a week so bars center visually over their tick label
            w_x = w_data['week_label'] + pd.Timedelta(days=3.5)
            fig.add_trace(go.Bar(
                x=w_x, y=w_data['count'], name=src, marker_color=color,
                legendgroup=src,
                hovertemplate="<b>%{customdata}</b><br>Anomalies: %{y}<extra></extra>",
                customdata=w_data['week_label'].dt.strftime('%d %b %Y')
            ), row=1, col=1)

            fig.add_trace(go.Bar(
                x=m_data['month_label'], y=m_data['count'], name=src, marker_color=color,
                xperiod="M1", xperiodalignment="middle",
                legendgroup=src, showlegend=False,
                hovertemplate="<b>%{x|%b %Y}</b><br>Anomalies: %{y}<extra></extra>"
            ), row=2, col=1)

        # tick0 anchored to the actual first bar position (week_label, not shifted)
        # so labels appear at the start of each week period, matching the hover date
        actual_first_week = weekly['week_label'].min() if not weekly.empty else first_full_week_start

        # Subplot 1: weekly ticks at week_label start (bars are shifted +3.5d visually)
        fig.update_xaxes(
            row=1, col=1,
            tickangle=45,
            type='date',
            tick0=actual_first_week + pd.Timedelta(days=3.5),
            dtick=tick_val_w,
            tickformat="%d %b %y"
        )

        # Subplot 2: Monthly ticks centered under period
        fig.update_xaxes(
            row=2, col=1,
            tickangle=45,
            type='date',
            dtick="M1" if diff_days <= 730 else "M3",
            tickformat="%b %Y",
            ticklabelmode="period"
        )

        fig.update_yaxes(title_text="Weekly anomalies", row=1, col=1)
        fig.update_yaxes(title_text="Monthly anomalies", row=2, col=1)

        vol_name = load_global_config().get('volcano', 'Volcano Name')
        fig.update_layout(
            title=dict(
                text=f"FIRMS: thermal anomalies in {vol_name}<br>{start_dt.strftime('%B %Y')} - {end_dt.strftime('%B %Y')}",
                x=0.5, font=dict(size=20, color='black')),
            barmode='stack', template="plotly_white",
            legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5, title="Sensor:"),
            margin=dict(t=100, b=120, l=80, r=40)
        )
        return fig, summary_panel


if __name__ == '__main__':
    from dash import Dash

    app = Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True, port=8060)
