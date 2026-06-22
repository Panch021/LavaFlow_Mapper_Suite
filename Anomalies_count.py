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
    """Load configuration parameters from the active volcano subfolder."""
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
                config[key.strip()] = value.strip()
    return config


def load_historical_data():
    """Consolidated loader for sensor files in the specific volcano folder."""
    folder = get_active_folder()
    if not folder: return pd.DataFrame()
    folder_name = os.path.basename(folder)   # e.g. 'Sangay' not 'projects/Sangay'
    files = {
        'MODIS (AQUA/TERRA)': f'historical_MODIS_NRT_{folder_name}.csv',
        'VIIRS (SNPP)': f'historical_VIIRS_SNPP_NRT_{folder_name}.csv',
        'VIIRS (NOAA-20)': f'historical_VIIRS_NOAA20_NRT_{folder_name}.csv',
        'VIIRS (NOAA-21)': f'historical_VIIRS_NOAA21_NRT_{folder_name}.csv'
    }
    all_dfs = []
    for label, filename in files.items():
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            try:
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding='latin-1')

                # Robust multi-format date parser — handles:
                # YYYY-MM-DD (ISO, current standard)
                # DD/MM/YYYY (legacy full)
                # D/M/YY, DD/M/YY, D/M/YYYY (NASA API short formats)
                parsed = pd.to_datetime(df['acq_date'], format='%Y-%m-%d', errors='coerce')
                if parsed.isna().all():
                    parsed = pd.to_datetime(df['acq_date'], format='%d/%m/%Y', errors='coerce')
                if parsed.isna().all():
                    parsed = pd.to_datetime(df['acq_date'], dayfirst=True, errors='coerce')
                df['acq_date'] = parsed

                df['source'] = label
                all_dfs.append(df[['acq_date', 'source', 'frp']])
            except Exception:
                continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def compute_summary_stats(df, start_dt, end_dt, week_day):
    """
    Computes summary statistics for the sidebar panel:
    - Total anomalies on the last day WITH data (unchanged)
    - Total anomalies for the week containing end_dt (0 if no data that week)
    - Total anomalies for the month containing end_dt (0 if no data that month)
    - Peak week and peak month totals across the full analysis period
    """
    if df.empty:
        return {}

    df_range = df[(df['acq_date'] >= start_dt) & (df['acq_date'] <= end_dt)].copy()
    if df_range.empty:
        return {}

    last_day = df_range['acq_date'].max()

    # --- Last day with data (unchanged) ---
    total_last_day = int((df_range['acq_date'] == last_day).sum())

    # --- Last week: week that CONTAINS end_dt, anchored to week_day ---
    # Returns 0 if there are no detections during that week
    days_since_start = (end_dt.dayofweek - week_day) % 7
    last_week_start = end_dt - pd.Timedelta(days=int(days_since_start))
    last_week_end = last_week_start + pd.Timedelta(days=6)
    mask_last_week = (df_range['acq_date'] >= last_week_start) & (df_range['acq_date'] <= last_week_end)
    total_last_week = int(mask_last_week.sum())

    # --- Last month: calendar month that CONTAINS end_dt ---
    # Returns 0 if there are no detections during that month
    last_month_start = end_dt.replace(day=1)
    last_month_end = last_month_start + pd.offsets.MonthEnd(1)
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
        'last_month': end_dt.strftime('%B %Y'),
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

    folder = get_active_folder()
    if not folder:
        return html.Div("⚠️ No active project found. Please configure a volcano first.",
                        style={'textAlign': 'center', 'padding': '20px', 'color': '#e74c3c'})

    folder_name = os.path.basename(folder)   # e.g. 'Sangay' not 'projects/Sangay'
    sat_files = [
        f'historical_VIIRS_SNPP_NRT_{folder_name}.csv',
        f'historical_VIIRS_NOAA20_NRT_{folder_name}.csv',
        f'historical_VIIRS_NOAA21_NRT_{folder_name}.csv',
        f'historical_MODIS_NRT_{folder_name}.csv',
    ]
    if not any(os.path.exists(os.path.join(folder, f)) for f in sat_files):
        return html.Div([
            html.P("⚠️ No satellite data found.",
                   style={'color': '#e74c3c', 'fontWeight': 'bold', 'fontSize': '16px'}),
            html.P("Please run 🛰️ FIRMS Download (Tab 1) first to download satellite data.",
                   style={'color': '#7f8c8d'})
        ], style={'textAlign': 'center', 'padding': '40px'})

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

        # Compute sidebar summary stats (works even if df is empty for the range)
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

        # ---- Build the full week and month grids spanning the ENTIRE analysis period ----
        # This guarantees that x-axis ticks cover the full Analysis Period even when
        # there are no detections in the trailing (or leading) portion of the range.

        # First complete week boundary within the analysis range (aligned to week_day)
        first_full_week_start = start_dt + pd.Timedelta(days=(week_day - start_dt.dayofweek) % 7)
        # Last week boundary on or before end_dt (aligned to week_day)
        last_week_start = end_dt - pd.Timedelta(days=(end_dt.dayofweek - week_day) % 7)

        # Full weekly grid (may be empty if range < 1 week)
        if last_week_start >= first_full_week_start:
            all_weeks = pd.date_range(first_full_week_start, last_week_start, freq='7D')
        else:
            all_weeks = pd.DatetimeIndex([])

        # Full monthly grid spanning from month of start_dt to month of end_dt
        first_month = start_dt.to_period('M').to_timestamp()
        last_month = end_dt.to_period('M').to_timestamp()
        all_months = pd.date_range(first_month, last_month, freq='MS')

        sensors = ['MODIS (AQUA/TERRA)', 'VIIRS (SNPP)', 'VIIRS (NOAA-20)', 'VIIRS (NOAA-21)']
        colors = ['blue', 'orange', 'purple', 'red']

        # Aggregate weekly and monthly counts; reindex onto the full grids so missing
        # weeks/months appear as zeros and the x-axis spans the whole Analysis Period.
        if not df.empty:
            df['week_label'] = df['acq_date'] - pd.to_timedelta(
                (df['acq_date'].dt.dayofweek - week_day) % 7, unit='d'
            )
            df = df[df['week_label'] >= first_full_week_start]
            df['month_label'] = df['acq_date'].dt.to_period('M').dt.to_timestamp()

            weekly_pivot = (df.groupby(['week_label', 'source']).size()
                              .unstack(fill_value=0)
                              .reindex(all_weeks, fill_value=0))
            monthly_pivot = (df.groupby(['month_label', 'source']).size()
                               .unstack(fill_value=0)
                               .reindex(all_months, fill_value=0))
        else:
            weekly_pivot = pd.DataFrame(0, index=all_weeks, columns=sensors)
            monthly_pivot = pd.DataFrame(0, index=all_months, columns=sensors)

        # Ensure every sensor column exists even if it had no detections
        for s in sensors:
            if s not in weekly_pivot.columns:
                weekly_pivot[s] = 0
            if s not in monthly_pivot.columns:
                monthly_pivot[s] = 0

        fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.15)

        for src, color in zip(sensors, colors):
            # Shift x by half a week so bars center visually over their tick label
            w_x = weekly_pivot.index + pd.Timedelta(days=3.5)
            w_y = weekly_pivot[src].values
            fig.add_trace(go.Bar(
                x=w_x, y=w_y, name=src, marker_color=color,
                legendgroup=src,
                hovertemplate="<b>%{customdata}</b><br>Anomalies: %{y}<extra></extra>",
                customdata=weekly_pivot.index.strftime('%d %b %Y')
            ), row=1, col=1)

            fig.add_trace(go.Bar(
                x=monthly_pivot.index, y=monthly_pivot[src].values, name=src, marker_color=color,
                xperiod="M1", xperiodalignment="middle",
                legendgroup=src, showlegend=False,
                hovertemplate="<b>%{x|%b %Y}</b><br>Anomalies: %{y}<extra></extra>"
            ), row=2, col=1)

        # ---- Force x-axis ranges to span the FULL analysis period ----
        # Add a small padding so the first/last bars are not clipped by the axis edge.
        weekly_pad = pd.Timedelta(days=3.5)
        weekly_x_min = first_full_week_start - weekly_pad
        weekly_x_max = (last_week_start + pd.Timedelta(days=7)) + weekly_pad

        monthly_x_min = first_month - pd.Timedelta(days=2)
        monthly_x_max = (last_month + pd.offsets.MonthEnd(1)) + pd.Timedelta(days=2)

        # Subplot 1: weekly ticks anchored at the first full week (bars shifted +3.5d visually)
        fig.update_xaxes(
            row=1, col=1,
            tickangle=45,
            type='date',
            tick0=first_full_week_start + pd.Timedelta(days=3.5),
            dtick=tick_val_w,
            tickformat="%d %b %y",
            range=[weekly_x_min, weekly_x_max]
        )

        # Subplot 2: Monthly ticks centered under period
        fig.update_xaxes(
            row=2, col=1,
            tickangle=45,
            type='date',
            dtick="M1" if diff_days <= 730 else "M3",
            tickformat="%b %Y",
            ticklabelmode="period",
            range=[monthly_x_min, monthly_x_max]
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
