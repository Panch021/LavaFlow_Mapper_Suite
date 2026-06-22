import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from dash import html, dcc, Input, Output, State
import dash


# ==========================================
# 0. CONFIGURATION HELPERS
# ==========================================

def get_active_folder():
    """
    Returns the full relative folder path of the active project
    (e.g. 'projects/Wolf_2022' or 'examples/Sangay_2023').
    """
    if os.path.exists("active_volcano.txt"):
        with open("active_volcano.txt", "r") as f:
            path = f.read().strip()
        if os.path.isdir(path):
            return path
        legacy = path.replace(" ", "_")
        if os.path.isdir(legacy):
            return legacy
    return None


def load_global_config():
    folder = get_active_folder()
    if not folder:
        return {}
    folder_name = os.path.basename(folder)
    config_path = os.path.join(folder, f"config_{folder_name}.txt")

    config = {}
    if not os.path.exists(config_path):
        return config
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                val = v.strip()
                if val.lower() == 'true':
                    config[k.strip()] = True
                elif val.lower() == 'false':
                    config[k.strip()] = False
                else:
                    try:
                        config[k.strip()] = float(val) if "." in val else int(val)
                    except ValueError:
                        config[k.strip()] = val
    return config


# ==========================================
# 0a. UNIFIED DATE PARSER
# ==========================================
def parse_firms_date(series):
    """
    Robust FIRMS date parser. Handles mixed formats row-by-row.

    Detects format by inspecting the string itself:
      - If it matches YYYY-MM-DD or YYYY-MM-DD HH:MM:SS -> ISO (year first)
      - Otherwise it's assumed to be DD/MM/YYYY (LatAm/European)

    IMPORTANT: never uses dayfirst=True as a fallback on ISO strings,
    because '2026-01-03 06:39:00' with dayfirst=True is wrongly read as
    1 March 2026 (the leading '03' is taken as the month).
    """
    s = series.astype(str).str.strip()

    # Empty result
    parsed = pd.Series([pd.NaT] * len(s), index=s.index, dtype='datetime64[ns]')

    # Rows that LOOK like ISO (start with 4 digits + dash)
    iso_mask = s.str.match(r'^\d{4}-\d{2}-\d{2}', na=False)
    if iso_mask.any():
        # No format=: lets pandas handle both 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS'
        parsed.loc[iso_mask] = pd.to_datetime(s[iso_mask], errors='coerce')

    # Remaining rows: assume DD/MM/YYYY (Ecuadorian / European convention)
    rest = parsed.isna() & s.ne('') & s.ne('nan')
    if rest.any():
        parsed.loc[rest] = pd.to_datetime(s[rest], dayfirst=True, errors='coerce')

    return parsed


# ==========================================
# 0b. MULTI-WAYPOINT PARSER
# ==========================================
def parse_waypoints_from_config(c):
    """
    Parses waypoints from the config dict. Supports both:
      - Legacy single-waypoint format: wpt_names=Foo, wpt_lats=1.0, ...
      - New multi-waypoint format:    wpt_names=Foo;Bar, wpt_lats=1.0;2.0, ...
    Returns a list of dicts {name, lat, lon, symbol}.
    """
    def _as_list(v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(';')]
        return [str(v)]

    names = _as_list(c.get('wpt_names', ''))
    lats  = _as_list(c.get('wpt_lats', 0.0))
    lons  = _as_list(c.get('wpt_lons', 0.0))
    syms  = _as_list(c.get('wpt_symbols', 'circle'))

    n = max(len(names), len(lats), len(lons), len(syms))
    waypoints = []
    for i in range(n):
        try:
            name = names[i] if i < len(names) else ''
            lat_raw = lats[i] if i < len(lats) else ''
            lon_raw = lons[i] if i < len(lons) else ''
            sym = syms[i] if i < len(syms) else 'circle'
            if not str(lat_raw).strip() or not str(lon_raw).strip():
                continue
            lat = float(lat_raw)
            lon = float(lon_raw)
            waypoints.append({
                'name': str(name).strip(),
                'lat': lat,
                'lon': lon,
                'symbol': (str(sym).strip() or 'circle'),
            })
        except (ValueError, IndexError):
            continue
    return waypoints


# ==========================================
# 1. FIGURE BUILDERS
# ==========================================

def compute_anomaly_stats(df, start_dt, end_dt, week_day=3):
    """Computes period summary stats matching the Anomalies_count sidebar panel."""
    df_range = df[(df['acq_date'] >= start_dt) & (df['acq_date'] <= end_dt)].copy()
    if df_range.empty:
        return {}

    last_day = df_range['acq_date'].max()
    total_last_day = int((df_range['acq_date'] == last_day).sum())

    days_since_start = (end_dt.dayofweek - week_day) % 7
    last_week_start = end_dt - pd.Timedelta(days=int(days_since_start))
    last_week_end = last_week_start + pd.Timedelta(days=6)
    total_last_week = int(((df_range['acq_date'] >= last_week_start) & (df_range['acq_date'] <= last_week_end)).sum())

    last_month_start = end_dt.replace(day=1)
    last_month_end = last_month_start + pd.offsets.MonthEnd(1)
    total_last_month = int(((df_range['acq_date'] >= last_month_start) & (df_range['acq_date'] <= last_month_end)).sum())

    df_range['week_label'] = df_range['acq_date'] - pd.to_timedelta(
        (df_range['acq_date'].dt.dayofweek - week_day) % 7, unit='d')
    full_week_start = start_dt + pd.Timedelta(days=(week_day - start_dt.dayofweek) % 7)
    weekly_totals = df_range[df_range['week_label'] >= full_week_start].groupby('week_label').size()
    peak_week = int(weekly_totals.max()) if not weekly_totals.empty else 0

    df_range['month_label'] = df_range['acq_date'].dt.to_period('M').dt.to_timestamp()
    peak_month = int(df_range.groupby('month_label').size().max())

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


def build_anomaly_stats_html(stats):
    """Renders period summary stats as a class-based responsive HTML block."""
    if not stats:
        return ""
    return f"""
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-label">Last day with data</div>
            <div class="stat-value">{stats['total_last_day']}</div>
            <div class="stat-meta">{stats['last_day']}</div>
        </div>
        <div class="stat-box">
            <div class="stat-label">Last week (all sensors)</div>
            <div class="stat-value">{stats['total_last_week']}</div>
            <div class="stat-meta">{stats['last_week_start']} – {stats['last_week_end']}</div>
        </div>
        <div class="stat-box">
            <div class="stat-label">Last month (all sensors)</div>
            <div class="stat-value">{stats['total_last_month']}</div>
            <div class="stat-meta">{stats['last_month']}</div>
        </div>
        <div class="stat-box">
            <div class="stat-label">Peak week in period</div>
            <div class="stat-value stat-value--alert">{stats['peak_week']}</div>
            <div class="stat-meta">anomalies</div>
        </div>
        <div class="stat-box">
            <div class="stat-label">Peak month in period</div>
            <div class="stat-value stat-value--alert">{stats['peak_month']}</div>
            <div class="stat-meta">anomalies</div>
        </div>
    </div>"""


def build_anomalies_figure(folder, cfg):
    """Weekly and monthly stacked bar charts from historical sensor CSVs.

    X-axis spans the full Analysis Period (start_day_str -> end_day_str) even
    when there are no detections at the start or end of the range. Missing
    weeks/months are reindexed to zero so the date ticks remain visible.
    """
    folder_name = os.path.basename(folder)
    files = {
        'MODIS': f'historical_MODIS_NRT_{folder_name}.csv',
        'VIIRS SNPP': f'historical_VIIRS_SNPP_NRT_{folder_name}.csv',
        'VIIRS NOAA-20': f'historical_VIIRS_NOAA20_NRT_{folder_name}.csv',
        'VIIRS NOAA-21': f'historical_VIIRS_NOAA21_NRT_{folder_name}.csv',
    }
    colors = {'MODIS': 'blue', 'VIIRS SNPP': 'orange', 'VIIRS NOAA-20': 'purple', 'VIIRS NOAA-21': 'red'}

    all_dfs = []
    for label, fname in files.items():
        fp = os.path.join(folder, fname)
        if os.path.exists(fp):
            try:
                try:
                    df = pd.read_csv(fp, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(fp, encoding='latin-1')

                # Unified, row-wise robust parser
                df['acq_date'] = parse_firms_date(df['acq_date'])

                # Drop rows that still couldn't be parsed and log how many
                n_before = len(df)
                df = df.dropna(subset=['acq_date'])
                n_dropped = n_before - len(df)
                if n_dropped > 0:
                    print(f"[Anomalies] {label}: {n_dropped}/{n_before} rows dropped (unparseable date)")

                df['source'] = label
                all_dfs.append(df[['acq_date', 'source']])
            except Exception as e:
                print(f"[Anomalies] Error reading {fname}: {e}")
                continue

    if not all_dfs:
        return None, None

    df_all = pd.concat(all_dfs, ignore_index=True)
    start_dt = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True, errors='coerce')
    end_dt   = pd.to_datetime(cfg.get('end_day_str'),   dayfirst=True, errors='coerce')
    if pd.isna(start_dt) or pd.isna(end_dt):
        return None, None

    # df = full period (used for stats AND for charts so numbers match)
    df = df_all[(df_all['acq_date'] >= start_dt) & (df_all['acq_date'] <= end_dt)].copy()

    week_day = 3
    sensors_order = list(colors.keys())

    # ---- Build full week and month grids spanning the ENTIRE analysis period ----
    # First complete week boundary within the analysis range (aligned to week_day)
    first_full_week_start = start_dt + pd.Timedelta(days=(week_day - start_dt.dayofweek) % 7)
    # Last week boundary on or before end_dt (aligned to week_day)
    last_week_start = end_dt - pd.Timedelta(days=(end_dt.dayofweek - week_day) % 7)

    if last_week_start >= first_full_week_start:
        all_weeks = pd.date_range(first_full_week_start, last_week_start, freq='7D')
    else:
        all_weeks = pd.DatetimeIndex([])

    # Full monthly grid: month-of-start_dt -> month-of-end_dt
    first_month = start_dt.to_period('M').to_timestamp()
    last_month = end_dt.to_period('M').to_timestamp()
    all_months = pd.date_range(first_month, last_month, freq='MS')

    # Aggregate weekly/monthly counts and reindex onto the full grids so
    # missing periods appear as zeros and ticks span the whole Analysis Period.
    if not df.empty:
        df['week_label'] = df['acq_date'] - pd.to_timedelta(
            (df['acq_date'].dt.dayofweek - week_day) % 7, unit='d'
        )
        df['month_label'] = df['acq_date'].dt.to_period('M').dt.to_timestamp()

        weekly_pivot = (df.groupby(['week_label', 'source']).size()
                          .unstack(fill_value=0)
                          .reindex(all_weeks, fill_value=0))
        monthly_pivot = (df.groupby(['month_label', 'source']).size()
                           .unstack(fill_value=0)
                           .reindex(all_months, fill_value=0))
    else:
        weekly_pivot = pd.DataFrame(0, index=all_weeks, columns=sensors_order)
        monthly_pivot = pd.DataFrame(0, index=all_months, columns=sensors_order)

    # Ensure every sensor column exists even if it had no detections
    for s in sensors_order:
        if s not in weekly_pivot.columns:
            weekly_pivot[s] = 0
        if s not in monthly_pivot.columns:
            monthly_pivot[s] = 0

    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.15,
                        subplot_titles=("Weekly Anomalies", "Monthly Anomalies"))

    MS_IN_WEEK = 7 * 24 * 60 * 60 * 1000

    for src, color in colors.items():
        # Shift x by half a week so bars center visually over their tick label
        w_x = weekly_pivot.index + pd.Timedelta(days=3.5)
        fig.add_trace(go.Bar(
            x=w_x, y=weekly_pivot[src].values, name=src, marker_color=color, legendgroup=src,
            customdata=weekly_pivot.index.strftime('%d %b %Y'),
            hovertemplate="<b>%{customdata}</b><br>Anomalies: %{y}<extra></extra>"
        ), row=1, col=1)
        fig.add_trace(go.Bar(
            x=monthly_pivot.index, y=monthly_pivot[src].values, name=src, marker_color=color,
            legendgroup=src, showlegend=False, xperiod="M1", xperiodalignment="middle",
            hovertemplate="<b>%{x|%b %Y}</b><br>Anomalies: %{y}<extra></extra>"
        ), row=2, col=1)

    diff_days = (end_dt - start_dt).days
    if diff_days <= 120:
        weekly_tick_step = 1
    elif diff_days <= 365:
        weekly_tick_step = 2
    elif diff_days <= 730:
        weekly_tick_step = 4
    else:
        weekly_tick_step = 8

    # ---- Force x-axis ranges to span the FULL analysis period ----
    weekly_pad = pd.Timedelta(days=3.5)
    weekly_x_min = first_full_week_start - weekly_pad
    weekly_x_max = (last_week_start + pd.Timedelta(days=7)) + weekly_pad

    monthly_x_min = first_month - pd.Timedelta(days=2)
    monthly_x_max = (last_month + pd.offsets.MonthEnd(1)) + pd.Timedelta(days=2)

    fig.update_xaxes(row=1, col=1, tickangle=45, type='date',
                     tick0=first_full_week_start + pd.Timedelta(days=3.5),
                     dtick=weekly_tick_step * MS_IN_WEEK, tickformat="%d %b %y",
                     range=[weekly_x_min, weekly_x_max])
    fig.update_xaxes(row=2, col=1, tickangle=45, type='date',
                     dtick="M1" if diff_days <= 730 else "M3", tickformat="%b %Y",
                     ticklabelmode="period",
                     range=[monthly_x_min, monthly_x_max])
    fig.update_yaxes(title_text="Weekly anomalies", row=1, col=1)
    fig.update_yaxes(title_text="Monthly anomalies", row=2, col=1)
    fig.update_layout(barmode='stack', template="plotly_white", height=700, autosize=True,
                      title=dict(text=f"Thermal Anomalies — {cfg.get('volcano', folder)}", x=0.5),
                      legend=dict(orientation="h", y=-0.12, xanchor="center", x=0.5))

    # Stats use the SAME filtered df as the charts so panel totals and bar totals agree.
    stats_html = build_anomaly_stats_html(compute_anomaly_stats(df, start_dt, end_dt, week_day))
    return fig, stats_html


def build_mapper_figure(folder, cfg):
    """FRP and distance time series + global stats panel from filter_VIIRS_combined.csv."""
    fp = os.path.join(folder, "filter_VIIRS_combined.csv")
    if not os.path.exists(fp):
        return None, None

    df = pd.read_csv(fp)

    # Robust parser instead of bare pd.to_datetime(df['date'])
    df['date'] = parse_firms_date(df['date'])
    n_before = len(df)
    df = df.dropna(subset=['date'])
    if len(df) < n_before:
        print(f"[Mapper] {n_before - len(df)}/{n_before} rows dropped (unparseable date)")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
    sat_colors = {'SNPP': 'orange', 'NOAA20': 'purple', 'NOAA21': 'red'}
    volcano = cfg.get('volcano', folder)
    start_dt = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True, errors='coerce')
    end_dt   = pd.to_datetime(cfg.get('end_day_str'),   dayfirst=True, errors='coerce')
    s_label = start_dt.strftime('%d/%m/%Y') if not pd.isna(start_dt) else 'N/A'
    e_label = end_dt.strftime('%d/%m/%Y')   if not pd.isna(end_dt)   else 'N/A'

    for sat, color in sat_colors.items():
        d = df[df['satellite'] == sat]
        if not d.empty:
            fig.add_trace(go.Scatter(x=d['date'], y=d['frp'], mode='markers', name=sat,
                                     marker=dict(color=color, size=7, line=dict(width=1, color='black')),
                                     hovertemplate="Date: %{x|%d/%m/%Y}<br>FRP: %{y} MW<extra></extra>"), row=1, col=1)
            for _, row in d.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row['date'], row['date']], y=[0, row['distance_km']],
                    mode='lines', line=dict(color=color, width=1.2),
                    showlegend=False, hoverinfo='skip'
                ), row=2, col=1)
            fig.add_trace(go.Scatter(x=d['date'], y=d['distance_km'], mode='markers',
                                     marker=dict(color=color, size=6), showlegend=False,
                                     hovertemplate="Date: %{x|%d/%m/%Y}<br>Distance: %{y:.2f} km<extra></extra>"), row=2, col=1)

    # ---- Reference radius line on the distance subplot ----
    # Independent Plotly toggle: a button in the top-right of the figure
    # shows/hides the radius line. Also appears as a regular legend entry
    # so it can be toggled from the legend as well.
    has_ref_radius = bool(cfg.get('include_reference_radius'))
    ref_radius_km = cfg.get('ref_radius_m', 5000) / 1000.0
    radius_buttons = None

    if has_ref_radius and not pd.isna(start_dt) and not pd.isna(end_dt):
        fig.add_trace(go.Scatter(
            x=[start_dt, end_dt],
            y=[ref_radius_km, ref_radius_km],
            mode='lines',
            line=dict(color='black', width=1.5, dash='dash'),
            name=f"Ref. radius ({ref_radius_km:.2f} km)",
            showlegend=True,
            hovertemplate=f"Ref. radius: {ref_radius_km:.2f} km<extra></extra>",
            visible=True,
        ), row=2, col=1)

        radius_trace_idx = len(fig.data) - 1
        n_traces = len(fig.data)

        radius_buttons = dict(
            type='buttons',
            direction='right',
            x=1.0, xanchor='right',
            y=1.12, yanchor='bottom',
            showactive=True,
            buttons=[
                dict(
                    label='⚫ Show Ref. Radius',
                    method='restyle',
                    args=[{'visible': [True if i == radius_trace_idx else None
                                       for i in range(n_traces)]}],
                ),
                dict(
                    label='⚪ Hide Ref. Radius',
                    method='restyle',
                    args=[{'visible': ['legendonly' if i == radius_trace_idx else None
                                       for i in range(n_traces)]}],
                ),
            ],
            pad=dict(r=4, t=4, b=4, l=4),
            bgcolor='#ecf0f1',
            bordercolor='#bdc3c7',
            font=dict(size=11),
        )

    fig.update_layout(template="plotly_white", height=600, autosize=True,
                      margin=dict(t=130),
                      title=dict(text=f"FIRMS Thermal Anomalies — {volcano}<br>{s_label} – {e_label}", x=0.5),
                      legend=dict(orientation="h", y=-0.15, xanchor="left", x=0),
                      updatemenus=[radius_buttons] if radius_buttons else [])
    fig.update_yaxes(title_text="FRP (MW)", row=1, col=1)
    fig.update_yaxes(title_text="Max. Lava Flow Distance (km)", row=2, col=1, rangemode='tozero')

    if not pd.isna(start_dt) and not pd.isna(end_dt):
        fig.update_xaxes(range=[start_dt, end_dt], row=1, col=1)
        fig.update_xaxes(range=[start_dt, end_dt], row=2, col=1)

    frp_mean  = df['frp'].mean()
    frp_max   = df['frp'].max()
    dist_mean = df['distance_km'].mean()
    dist_max  = df['distance_km'].max()

    stats_html = f"""
    <div class="stats-section">
        <div class="stats-title">📊 Period Summary (all satellites)</div>
        <div class="stats-grid">
            <div class="stat-box stat-box--outlined">
                <div class="stat-label">Mean FRP</div>
                <div class="stat-value stat-value--accent">{frp_mean:.1f} MW</div>
            </div>
            <div class="stat-box stat-box--outlined">
                <div class="stat-label">Max FRP</div>
                <div class="stat-value stat-value--accent">{frp_max:.1f} MW</div>
            </div>
            <div class="stat-box stat-box--outlined">
                <div class="stat-label">Mean Distance</div>
                <div class="stat-value stat-value--accent">{dist_mean:.2f} km</div>
            </div>
            <div class="stat-box stat-box--outlined">
                <div class="stat-label">Max Distance</div>
                <div class="stat-value stat-value--accent">{dist_max:.2f} km</div>
            </div>
        </div>
    </div>"""
    return fig, stats_html


def build_speed_figure(folder, cfg):
    """Propagation speed chart + stats panel from LavaFlow_propagation.csv."""
    fp = os.path.join(folder, "LavaFlow_propagation.csv")
    if not os.path.exists(fp):
        return None, None

    df = pd.read_csv(fp)

    # Robust parser
    df['date'] = parse_firms_date(df['date'])
    df = df.dropna(subset=['date'])

    volcano = cfg.get('volcano', folder)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df['date'], y=df['max_distance'], name="Max Distance",
                              mode='lines+markers', line=dict(color='black', width=2, dash='dash'),
                              marker=dict(size=7)), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['date'], y=df['speed'], name="Prop. Speed",
                              mode='lines+markers', line=dict(color='red', width=2, dash='dot'),
                              marker=dict(size=7, symbol='diamond')), secondary_y=True)

    # ---- Reference radius line on the Max Distance (primary) axis ----
    # Plotted as a regular trace so it appears in the legend and can be
    # toggled from there. Blue to keep it visually distinct from the black
    # Max Distance line.
    has_ref_radius = bool(cfg.get('include_reference_radius'))
    if has_ref_radius and not df.empty:
        ref_radius_km = cfg.get('ref_radius_m', 5000) / 1000.0
        fig.add_trace(go.Scatter(
            x=[df['date'].min(), df['date'].max()],
            y=[ref_radius_km, ref_radius_km],
            mode='lines',
            line=dict(color='#1f77b4', width=2, dash='dash'),
            name=f"Ref. radius ({ref_radius_km:.2f} km)",
            hovertemplate=f"Ref. radius: {ref_radius_km:.2f} km<extra></extra>",
        ), secondary_y=False)

    fig.update_layout(template="plotly_white", height=500, autosize=True,
                      title=dict(text=f"Lava Flow Propagation Speed — {volcano}", x=0.5),
                      legend=dict(orientation="h", y=-0.2, xanchor="center", x=0.5))
    fig.update_yaxes(title_text="Maximum Distance (km)", secondary_y=False, rangemode='tozero')
    fig.update_yaxes(title_text="Propagation Speed (m/h)", secondary_y=True, color="red")

    speed_valid = df['speed'].dropna()
    max_dist   = df['max_distance'].max() if not df.empty else 0
    max_speed  = speed_valid.max()  if not speed_valid.empty else 0
    mean_speed = speed_valid.mean() if not speed_valid.empty else 0

    stats_html = f"""
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-label">Max. Lava Flow Distance</div>
            <div class="stat-value">{max_dist:.2f} km</div>
        </div>
        <div class="stat-box stat-box--alert">
            <div class="stat-label">Max. Propagation Speed</div>
            <div class="stat-value stat-value--alert">{max_speed:.1f} m/h</div>
        </div>
        <div class="stat-box stat-box--alert">
            <div class="stat-label">Mean Propagation Speed</div>
            <div class="stat-value stat-value--alert">{mean_speed:.1f} m/h</div>
        </div>
    </div>"""
    return fig, stats_html


def build_vertical_colorbar(start_dt, end_dt, n_ticks=6):
    """Vertical CSS gradient colorbar with date labels, matching LavaFlow_mapper."""
    colors = ['#d7191c', '#fdae61', '#ffffbf', '#abdda4', '#2b83ba']
    gradient = ", ".join(colors)
    total_seconds = (end_dt - start_dt).total_seconds()
    tick_dates = [
        start_dt + pd.Timedelta(seconds=total_seconds * i / (n_ticks - 1))
        for i in range(n_ticks)
    ]
    tick_labels = [d.strftime('%d/%m/%Y') for d in reversed(tick_dates)]
    label_items = "".join([
        f'<div style="flex:1;display:flex;align-items:center;'
        f'font-size:12px;color:#333;white-space:nowrap;">{lbl}</div>'
        for lbl in tick_labels
    ])
    return f"""
    <div style="position:absolute;bottom:100px;left:10px;z-index:9999;
                display:flex;flex-direction:row;align-items:stretch;
                height:160px;pointer-events:none;
                background:white;padding:6px 8px;border-radius:5px;">
        <div style="width:22px;height:100%;
                    background:linear-gradient(to bottom, {gradient});
                    border:1px solid #aaa;border-radius:3px;
                    margin-right:5px;flex-shrink:0;"></div>
        <div style="display:flex;flex-direction:column;
                    justify-content:space-between;height:100%;">
            {label_items}
        </div>
    </div>"""


def build_lock_zoom_script():
    """Lock-zoom Leaflet control button (bottom-right corner)."""
    return """
    <script>
    (function() {
        function attachLockButton() {
            var mapKey = Object.keys(window).find(function(k) {
                return k.startsWith('map_') && window[k] && window[k]._container;
            });
            if (!mapKey) { setTimeout(attachLockButton, 150); return; }
            var leafletMap = window[mapKey];

            var LockControl = L.Control.extend({
                options: { position: 'bottomright' },
                onAdd: function(map) {
                    var btn = L.DomUtil.create('button', 'leaflet-bar lock-zoom-btn');
                    btn.innerHTML = '🔓 Unlock zoom';
                    btn.style.cssText = 'padding:6px 10px;background:#c0392b;color:white;' +
                        'border:none;border-radius:4px;cursor:pointer;' +
                        'font-weight:bold;font-size:12px;' +
                        'box-shadow:0 1px 5px rgba(0,0,0,0.3);' +
                        'margin-bottom:380px;';
                    var locked = true;
                    map.scrollWheelZoom.disable();
                    map.doubleClickZoom.disable();
                    map.touchZoom.disable();
                    map.boxZoom.disable();

                    L.DomEvent.disableClickPropagation(btn);
                    L.DomEvent.on(btn, 'click', function() {
                        locked = !locked;
                     if (locked) {
                        map.scrollWheelZoom.disable();
                        map.doubleClickZoom.disable();
                        map.touchZoom.disable();
                        map.boxZoom.disable();
                        btn.innerHTML = '🔓 Unlock zoom';
                        btn.style.background = '#c0392b';
                     } else {
                        map.scrollWheelZoom.enable();
                        map.doubleClickZoom.enable();
                        map.touchZoom.enable();
                        map.boxZoom.enable();
                        btn.innerHTML = '🔒 Lock zoom';
                        btn.style.background = '#7f8c8d';
                     }
                    });
                    return btn;
                }
            });
            leafletMap.addControl(new LockControl());
        }
        if (document.readyState === 'complete') {
            attachLockButton();
        } else {
            window.addEventListener('load', attachLockButton);
        }
    })();
    </script>
    """


def add_waypoint_marker_with_label(feature_group, lat, lon, name, symbol):
    """Adds a waypoint marker plus a permanent label showing its name."""
    import folium
    try:
        from folium.plugins import RegularPolygonMarker
    except ImportError:
        from folium.features import RegularPolygonMarker

    label = folium.Tooltip(
        name or "Waypoint",
        permanent=True,
        direction='right',
        offset=(8, 0),
        sticky=False,
        opacity=0.95
    ) if name else folium.Tooltip(name or "Waypoint")

    if symbol == "circle":
        folium.CircleMarker(
            [lat, lon], radius=7, color='black',
            fill=True, fill_opacity=1.0,
            tooltip=label
        ).add_to(feature_group)
    elif symbol == "triangle":
        RegularPolygonMarker(
            [lat, lon], number_of_sides=3, radius=9, rotation=30,
            color='black', fill=True, fill_opacity=1.0,
            tooltip=label
        ).add_to(feature_group)
    else:
        RegularPolygonMarker(
            [lat, lon], number_of_sides=4, radius=7, rotation=45,
            color='black', fill=True, fill_opacity=1.0,
            tooltip=label
        ).add_to(feature_group)


def build_folium_map(folder, cfg):
    """Recreates the Folium map from filter_VIIRS_combined.csv, matching LavaFlow_mapper output."""
    try:
        import folium
        import branca.colormap as bcm
    except ImportError:
        return None

    fp = os.path.join(folder, "filter_VIIRS_combined.csv")
    if not os.path.exists(fp):
        return None

    df = pd.read_csv(fp)

    # Robust parser
    df['date'] = parse_firms_date(df['date'])
    df = df.dropna(subset=['date'])

    LATS = cfg.get('lats_vent', 0.0)
    LONS = cfg.get('longs_vent', 0.0)
    start_dt = pd.to_datetime(cfg.get('start_day_str'), dayfirst=True, errors='coerce')
    end_dt   = pd.to_datetime(cfg.get('end_day_str'),   dayfirst=True, errors='coerce')

    if pd.isna(start_dt): start_dt = df['date'].min()
    if pd.isna(end_dt):   end_dt   = df['date'].max()
    if pd.isna(start_dt) or pd.isna(end_dt):
        return None

    ref_radius_km = cfg.get('ref_radius_m', 5000) / 1000
    max_dist_km = df['distance_km'].max() if not df.empty else ref_radius_km
    view_km = max(ref_radius_km, max_dist_km)
    zoom = 15 if view_km < 2 else 14 if view_km < 5 else 13 if view_km < 10 else 12 if view_km < 20 else 11 if view_km < 50 else 10

    m = folium.Map(location=[LATS, LONS], zoom_start=zoom, control_scale=True, tiles=None)

    custom_css = """
    <style>
        .leaflet-control-scale {
            position: absolute !important;
            bottom: 40px !important;
            left: 10px !important;
            z-index: 9999 !important;
            visibility: visible !important;
        }
        .leaflet-tooltip.leaflet-tooltip-right {
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid #555;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: bold;
            color: #2c3e50;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }
        .leaflet-tooltip.leaflet-tooltip-right::before {
            border-right-color: #555;
        }
    </style>
    """
    m.get_root().header.add_child(folium.Element(custom_css))

    folium.TileLayer('Esri World Imagery', name='Esri World Imagery').add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    folium.TileLayer('OpenTopoMap', name='OpenTopoMap').add_to(m)

    min_ts, max_ts = start_dt.timestamp(), end_dt.timestamp()
    colormap = bcm.LinearColormap(
        colors=['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c'],
        vmin=min_ts, vmax=max_ts
    )

    colorbar_html = build_vertical_colorbar(start_dt, end_dt, n_ticks=6)
    m.get_root().html.add_child(folium.Element(colorbar_html))

    fg_anomalies = folium.FeatureGroup(name="Thermal Anomalies")
    for _, row in df.iterrows():
        folium.Circle(
            location=[row['latitude'], row['longitude']], radius=192.5,
            color=colormap(row['date'].timestamp()), fill=True, fill_opacity=0.7,
            popup=f"Date: {row['date'].strftime('%Y-%m-%d %H:%M')}<br>FRP: {row['frp']} MW"
        ).add_to(fg_anomalies)
    fg_anomalies.add_to(m)

    if cfg.get('include_shapefile') and cfg.get('shapefile_path'):
        shp_name = str(cfg.get('shapefile_path'))
        if not shp_name.lower().endswith(".shp"):
            shp_name += ".shp"
        actual_path = os.path.join(folder, shp_name) if folder else shp_name
        if os.path.exists(actual_path):
            try:
                import geopandas as gpd
                gdf = gpd.read_file(actual_path).to_crs(epsg=4326)
                folium.GeoJson(
                    gdf, name="Reference Shapefile",
                    style_function=lambda x: {'color': 'black', 'weight': 2, 'fill': False}
                ).add_to(m)
            except Exception:
                pass

    if cfg.get('include_reference_radius'):
        fg_rad = folium.FeatureGroup(name='Reference Radius')
        folium.Circle(
            location=[LATS, LONS], radius=cfg.get('ref_radius_m', 5000),
            color='black', weight=1, fill=False, dash_array='5,5'
        ).add_to(fg_rad)
        fg_rad.add_to(m)

    waypoints = parse_waypoints_from_config(cfg) if cfg.get('include_reference_waypoint') else []
    if waypoints:
        fg_wpts = folium.FeatureGroup(name="Reference Waypoints")
        for wpt in waypoints:
            add_waypoint_marker_with_label(
                fg_wpts,
                lat=wpt['lat'], lon=wpt['lon'],
                name=wpt['name'], symbol=wpt['symbol']
            )
        fg_wpts.add_to(m)

    folium.Marker(
        [LATS, LONS],
        icon=folium.DivIcon(
            html='<div style="width:0;height:0;border-left:10px solid transparent;'
                 'border-right:10px solid transparent;border-bottom:20px solid black;'
                 'transform:translate(-50%,-50%);"></div>'
        ),
        tooltip="Vent"
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    lats = list(df['latitude'].values) + [LATS]
    lons = list(df['longitude'].values) + [LONS]

    if cfg.get('include_reference_radius'):
        radius_m = cfg.get('ref_radius_m', 5000)
        dlat = radius_m / 111000.0
        dlon = radius_m / (111000.0 * max(np.cos(np.radians(LATS)), 1e-6))
        lats += [LATS - dlat, LATS + dlat]
        lons += [LONS - dlon, LONS + dlon]

    for wpt in waypoints:
        lats.append(wpt['lat'])
        lons.append(wpt['lon'])

    south, north = min(lats), max(lats)
    west, east = min(lons), max(lons)

    if south == north:
        south -= 0.005
        north += 0.005
    if west == east:
        west -= 0.005
        east += 0.005

    m.fit_bounds([[south, west], [north, east]], padding=(30, 30))

    m.get_root().html.add_child(folium.Element(build_lock_zoom_script()))

    return m._repr_html_()


# ==========================================
# 2. HTML REPORT ASSEMBLER
# ==========================================

def generate_report(output_path, selected_sections=None):
    """Builds a self-contained, fully responsive HTML report."""
    folder = get_active_folder()
    if not folder:
        return False, "No active project found."

    if selected_sections is None:
        selected_sections = ['anomalies', 'mapper', 'speed']

    cfg = load_global_config()
    volcano = cfg.get('volcano', folder.replace("_", " "))
    start_str = cfg.get('start_day_str', 'N/A').split()[0]
    end_str = cfg.get('end_day_str', 'N/A').split()[0]
    generated_on = datetime.now().strftime('%d/%m/%Y %H:%M')

    sections = []
    # Use 'cdn' for the first Plotly chart so Plotly Python injects the CDN URL
    # for the EXACT matching plotly.js version. Subsequent charts reuse it.
    # This fixes the 'bdata' base64 binary-encoding bug where plotly-latest from
    # the CDN doesn't decode arrays serialized by Plotly Python >=6.x.
    _plotly_js_loaded = False

    def _plotly_js_param():
        nonlocal _plotly_js_loaded
        if not _plotly_js_loaded:
            _plotly_js_loaded = True
            return 'cdn'
        return False

    if 'anomalies' in selected_sections:
        fig_anom, anom_stats_html = build_anomalies_figure(folder, cfg)
        if fig_anom:
            chart_html = fig_anom.to_html(full_html=False, include_plotlyjs=_plotly_js_param(), config={'displaylogo': False})
            sections.append(("<h2>📈 Thermal Anomaly Counts</h2>",
                             (anom_stats_html or "") + chart_html))

    if 'mapper' in selected_sections:
        map_html = build_folium_map(folder, cfg)
        if map_html:
            fig_mapper, mapper_stats_html = build_mapper_figure(folder, cfg)
            frp_chart_html = ""
            if fig_mapper:
                frp_chart_html = (
                    "<h3 class='ts-header'>📊 FRP & Distance Time Series</h3>"
                    + (mapper_stats_html or "")
                    + fig_mapper.to_html(full_html=False, include_plotlyjs=_plotly_js_param(),
                                         config={'displaylogo': False})
                )
            sections.append(("<h2>🌋 Thermal Anomaly Map</h2>",
                             f'<div class="map-container">{map_html}</div>' + frp_chart_html))

    if 'speed' in selected_sections:
        fig_speed, speed_stats_html = build_speed_figure(folder, cfg)
        if fig_speed:
            chart_html = fig_speed.to_html(full_html=False, include_plotlyjs=_plotly_js_param(), config={'displaylogo': False})
            sections.append(("<h2>🚀 Propagation Speed</h2>",
                             (speed_stats_html or "") + chart_html))

    if not sections:
        return False, "No results available for the selected sections. Run the required modules first."

    html_report = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LavaFlow Report — {volcano}</title>
    <!-- NOTE: do NOT load plotly.js here. Each chart embeds its own matching
         version via include_plotlyjs='cdn' below, which avoids the 'bdata'
         binary-encoding incompatibility seen with plotly-latest. -->
    <script>
        // Make all Plotly charts truly responsive — listen for resize and orientation change
        function resizePlotly() {{
            var graphs = document.querySelectorAll('.plotly-graph-div');
            graphs.forEach(function(g) {{ try {{ Plotly.Plots.resize(g); }} catch(e) {{}} }});
        }}
        window.addEventListener('load', resizePlotly);
        window.addEventListener('resize', resizePlotly);
        window.addEventListener('orientationchange', resizePlotly);
    </script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        /* ========== BASE LAYOUT ========== */
        * {{ box-sizing: border-box; }}
        html, body {{ width: 100%; overflow-x: hidden; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f6fa;
            color: #2c3e50;
            line-height: 1.4;
        }}

        /* ========== HEADER ========== */
        .header {{
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: clamp(14px, 3vw, 24px) clamp(10px, 3vw, 20px);
            text-align: center;
        }}
        .header h1 {{ margin: 0 0 6px 0; font-size: clamp(16px, 4.5vw, 28px); line-height: 1.2; }}
        .header p {{ margin: 4px 0; opacity: 0.85; font-size: clamp(11px, 2.5vw, 14px); }}

        /* ========== CONTAINER & SECTIONS ========== */
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: clamp(8px, 2vw, 16px);
        }}
        .section {{
            background: white;
            border-radius: clamp(6px, 1.5vw, 10px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: clamp(10px, 2.5vw, 18px);
            margin-bottom: clamp(10px, 2vw, 18px);
            overflow: hidden;
        }}
        .section h2 {{
            margin: 0 0 12px 0;
            font-size: clamp(15px, 3.5vw, 20px);
            color: #2980b9;
            border-bottom: 2px solid #eee;
            padding-bottom: 8px;
        }}

        /* ========== TIME-SERIES SUBSECTION HEADER ========== */
        .ts-header {{
            color: #2980b9;
            margin: clamp(24px, 6vw, 60px) 0 8px 0;
            font-size: clamp(13px, 3vw, 16px);
        }}

        /* ========== PROJECT PARAMETERS META GRID ========== */
        .meta-grid {{
            display: flex;
            gap: clamp(6px, 1.5vw, 10px);
            flex-wrap: wrap;
            margin-bottom: 5px;
        }}
        .meta-box {{
            background: #f0f4f8;
            border: 1px solid #dde;
            border-radius: 6px;
            padding: clamp(6px, 1.5vw, 10px) clamp(8px, 2vw, 14px);
            flex: 1 1 130px;
            min-width: 0;
        }}
        .meta-box .label {{ font-size: clamp(9px, 2vw, 11px); color: #7f8c8d; }}
        .meta-box .value {{
            font-size: clamp(12px, 2.5vw, 16px);
            font-weight: bold;
            color: #2c3e50;
            word-break: break-word;
        }}

        /* ========== STATS PANELS ========== */
        .stats-section {{ margin-bottom: clamp(12px, 2.5vw, 20px); }}
        .stats-title {{
            font-weight: bold;
            font-size: clamp(12px, 2.6vw, 14px);
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .stats-grid {{
            display: flex;
            gap: clamp(6px, 1.5vw, 12px);
            flex-wrap: wrap;
            margin: 12px 0 16px 0;
        }}
        .stat-box {{
            flex: 1 1 140px;
            min-width: 0;
            padding: clamp(8px, 2vw, 14px) clamp(10px, 2vw, 18px);
            background: #f0f4f8;
            border: 1px solid #dde;
            border-radius: 8px;
        }}
        .stat-box--outlined {{ border: 2px solid #2980b9; text-align: center; }}
        .stat-box--alert    {{ background: #eaf4fb; border: 2px solid #e74c3c; }}
        .stat-label {{
            font-size: clamp(10px, 2vw, 11px);
            color: #7f8c8d;
            margin-bottom: 4px;
        }}
        .stat-value {{
            font-size: clamp(16px, 4vw, 22px);
            font-weight: bold;
            color: #2c3e50;
            line-height: 1.1;
        }}
        .stat-value--accent {{ color: #2980b9; }}
        .stat-value--alert  {{ color: #e74c3c; }}
        .stat-meta {{ font-size: clamp(9px, 2vw, 11px); color: #95a5a6; margin-top: 2px; }}

        /* ========== MAP CONTAINER ========== */
        .map-container {{
            width: 100%;
            max-width: 1100px;
            margin: 0 0 20px 0;
        }}
        .map-container iframe {{
            width: 100% !important;
            max-width: 100%;
            border: none;
            border-radius: 8px;
            display: block;
        }}

        /* ========== PLOTLY CHARTS ========== */
        .chart {{ width: 100%; min-width: 0; overflow-x: auto; }}
        .chart .plotly-graph-div {{ width: 100% !important; }}
        .chart .js-plotly-plot {{ width: 100% !important; }}

        /* ========== FOOTER ========== */
        .footer {{
            text-align: center;
            padding: clamp(10px, 2.5vw, 18px);
            font-size: clamp(10px, 2vw, 12px);
            color: #999;
        }}

        /* ========== RESPONSIVE BREAKPOINTS ========== */
        @media (max-width: 768px) {{
            .meta-box {{ flex: 1 1 calc(50% - 6px); }}
            .stat-box {{ flex: 1 1 calc(50% - 6px); }}
        }}

        @media (max-width: 480px) {{
            .stats-grid {{ gap: 6px; }}
            .meta-grid  {{ gap: 6px; }}
            .stat-box   {{ padding: 8px 10px; }}
            .meta-box   {{ flex: 1 1 calc(50% - 3px); }}
        }}

        @media (max-width: 360px) {{
            .stat-box {{ flex: 1 1 100%; }}
            .meta-box {{ flex: 1 1 100%; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🌋 LavaFlow Suite — {volcano}</h1>
        <p>Analysis period: {start_str} — {end_str}</p>
        <p>Generated: {generated_on}</p>
    </div>
    <div class="container">
        <div class="section">
            <h2>⚙️ Project Parameters</h2>
            <div class="meta-grid">
                <div class="meta-box"><div class="label">Volcano</div><div class="value">{volcano}</div></div>
                <div class="meta-box"><div class="label">Vent Lat / Lon</div><div class="value">{cfg.get('lats_vent')} / {cfg.get('longs_vent')}</div></div>
                <div class="meta-box"><div class="label">FRP Filter</div><div class="value">{'≥' if cfg.get('frp_filter_mode','gt')=='gt' else '≤'} {cfg.get('filter_frp')} MW</div></div>
                <div class="meta-box"><div class="label">Track Filter</div><div class="value">≤ {cfg.get('filter_track')}</div></div>
                <div class="meta-box"><div class="label">Ref. Radius</div><div class="value">{cfg.get('ref_radius_m')} m</div></div>
            </div>
        </div>
        {''.join(f'<div class="section">{h}<div class="chart">{c}</div></div>' for h, c in sections)}
    </div>
    <div class="footer">
        LavaFlow Suite · Report generated on {generated_on} · Data source: NASA FIRMS
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_report)

    return True, f"Report saved: {output_path}"


# ==========================================
# 3. DASH LAYOUT
# ==========================================

def get_layout():
    folder = get_active_folder()
    cfg = load_global_config()
    volcano = cfg.get('volcano', 'Volcano')

    default_values = []
    checklist_options = []
    if folder:
        folder_name = os.path.basename(folder)
        checks = [
            ('anomalies', '📈 Anomaly Counts',    f'historical_VIIRS_SNPP_NRT_{folder_name}.csv'),
            ('mapper',    '🌋 Thermal Anomaly Map', 'filter_VIIRS_combined.csv'),
            ('speed',     '🚀 Propagation Speed',  'LavaFlow_propagation.csv'),
        ]
        for key, label, fname in checks:
            exists = os.path.exists(os.path.join(folder, fname))
            note = '' if exists else ' (not yet generated)'
            checklist_options.append({
                'label': f' {label}{note}',
                'value': key,
                'disabled': not exists
            })
            if exists:
                default_values.append(key)

    def _fmt(d): return datetime.strptime(d.split()[0], '%d/%m/%Y').strftime('%Y%m%d')
    start_str_fn = _fmt(cfg.get('start_day_str', '01/01/2000 00:00'))
    end_str_fn   = _fmt(cfg.get('end_day_str',   '01/01/2000 00:00'))
    output_path  = os.path.join(folder, f"{volcano.replace(' ', '_')}_{start_str_fn}_{end_str_fn}_report.html") if folder else "report.html"

    return html.Div([
        html.Div([
            html.H2("📤 Export HTML Report", style={'margin': '0', 'color': '#2c3e50'}),
            html.P("Select the sections to include and generate a self-contained HTML file.",
                   style={'color': '#7f8c8d'})
        ], style={'padding': '20px', 'backgroundColor': 'white', 'borderBottom': '2px solid #eee'}),

        html.Div([
            html.Div([
                html.H4("Select Sections to Export", style={'color': '#2980b9', 'marginBottom': '12px'}),

                dcc.Checklist(
                    id='export-section-toggle',
                    options=checklist_options,
                    value=default_values,
                    labelStyle={
                        'display': 'block',
                        'padding': '11px 16px',
                        'marginBottom': '8px',
                        'borderRadius': '7px',
                        'border': '2px solid #27ae60',
                        'backgroundColor': '#f0faf4',
                        'fontWeight': 'bold',
                        'fontSize': '14px',
                        'cursor': 'pointer',
                        'color': '#2c3e50',
                    },
                    inputStyle={'marginRight': '10px', 'transform': 'scale(1.3)', 'cursor': 'pointer'},
                    style={'marginBottom': '20px'}
                ),

                html.Hr(),
                html.H4("Output File", style={'color': '#2980b9'}),
                html.P(f"📁 {output_path}",
                       style={'fontFamily': 'monospace', 'fontSize': '13px',
                              'backgroundColor': '#f0f4f8', 'padding': '8px',
                              'borderRadius': '4px', 'wordBreak': 'break-all'}),
                html.Br(),
                html.Button("📤 GENERATE HTML REPORT", id="btn-export-report", n_clicks=0,
                            style={'padding': '14px 28px', 'backgroundColor': '#2980b9', 'color': 'white',
                                   'border': 'none', 'borderRadius': '6px', 'fontWeight': 'bold',
                                   'fontSize': '15px', 'cursor': 'pointer'}),
                html.Div(id='export-report-status', style={'marginTop': '20px'})

            ], style={'maxWidth': '650px', 'padding': '30px', 'backgroundColor': 'white',
                      'borderRadius': '10px', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'})
        ], style={'padding': '30px'})
    ])


# ==========================================
# 4. CALLBACK REGISTRATION
# ==========================================

def register_callbacks(app):
    @app.callback(
        Output('export-report-status', 'children'),
        Input('btn-export-report', 'n_clicks'),
        State('export-section-toggle', 'value'),
        prevent_initial_call=True
    )
    def export_cb(n, selected_sections):
        if not n or n == 0:
            return ""
        selected_sections = selected_sections or []
        if not selected_sections:
            return html.Div("⚠️ Please select at least one section to export.",
                            style={'color': '#e67e22', 'fontWeight': 'bold'})
        folder = get_active_folder()
        cfg = load_global_config()
        volcano = cfg.get('volcano', 'Volcano')
        def _fmt(d): return datetime.strptime(d.split()[0], '%d/%m/%Y').strftime('%Y%m%d')
        start_str_fn = _fmt(cfg.get('start_day_str', '01/01/2000 00:00'))
        end_str_fn   = _fmt(cfg.get('end_day_str',   '01/01/2000 00:00'))
        output_path  = os.path.join(folder, f"{volcano.replace(' ', '_')}_{start_str_fn}_{end_str_fn}_report.html")

        success, message = generate_report(output_path, selected_sections)
        if success:
            return html.Div([
                html.P(f"✅ {message}", style={'color': '#27ae60', 'fontWeight': 'bold'}),
                html.P("Share the HTML file with colleagues — it opens in any browser without Python.",
                       style={'color': '#7f8c8d', 'fontSize': '13px'})
            ])
        else:
            return html.Div(f"❌ {message}", style={'color': '#e74c3c', 'fontWeight': 'bold'})
