"""
Anomalies_count.py
==================
Weekly and monthly counts of FIRMS thermal anomalies per sensor.

The bar charts and the "Period summary" panel are built from ONE shared
aggregation (aggregate_counts), so the numbers shown in the panel are,
by construction, the same numbers plotted as bars. The export module
reuses the same functions.
"""
import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dcc, html, Input, Output, State

import lavaflow_common as lfc

get_active_folder = lfc.get_active_folder
load_global_config = lfc.load_global_config

SENSORS = list(lfc.SENSOR_COLORS.keys())
SENSOR_FILES = {
    'MODIS (AQUA/TERRA)': 'historical_MODIS_NRT_{name}.csv',
    'VIIRS (SNPP)': 'historical_VIIRS_SNPP_NRT_{name}.csv',
    'VIIRS (NOAA-20)': 'historical_VIIRS_NOAA20_NRT_{name}.csv',
    'VIIRS (NOAA-21)': 'historical_VIIRS_NOAA21_NRT_{name}.csv',
}
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


# ==========================================
# 1. DATA
# ==========================================
def load_historical_data(folder=None):
    """All raw sensor files of the project -> DataFrame(acq_date, source, frp)."""
    folder = folder or get_active_folder()
    if not folder:
        return pd.DataFrame()
    name = os.path.basename(folder)
    frames = []
    for label, pattern in SENSOR_FILES.items():
        fp = os.path.join(folder, pattern.format(name=name))
        if not os.path.exists(fp):
            continue
        try:
            df = lfc.read_csv_any(fp)
            df['acq_date'] = lfc.parse_firms_date(df['acq_date']).dt.normalize()
            df = df.dropna(subset=['acq_date'])
            df['source'] = label
            frames.append(df[['acq_date', 'source', 'frp']])
        except Exception as e:
            print(f"[Anomalies] could not read {fp}: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def week_start(dates, week_day):
    """Start (00:00) of the week containing each date, weeks starting on week_day (0=Mon)."""
    dates = pd.to_datetime(dates)
    if isinstance(dates, pd.Timestamp):
        return dates.normalize() - pd.Timedelta(days=int((dates.dayofweek - week_day) % 7))
    return dates.dt.normalize() - pd.to_timedelta((dates.dt.dayofweek - week_day) % 7, unit='D')


def aggregate_counts(df, start_dt, end_dt, week_day=3):
    """
    Shared aggregation for charts and summary.

    Returns dict with
      weekly  : DataFrame indexed by week start, one column per sensor + 'Total'
                (covers every week touching the period; the first and last
                 weeks may be partial and are flagged in `partial_weeks`)
      monthly : same for calendar months
      summary : dict with the values shown in the Period summary panel,
                computed from `weekly`/`monthly` so they always agree.
    """
    start_dt = pd.Timestamp(start_dt).normalize()
    end_dt = pd.Timestamp(end_dt).normalize()
    df = df[(df['acq_date'] >= start_dt) & (df['acq_date'] <= end_dt)].copy() if not df.empty else df

    first_week = week_start(start_dt, week_day)
    last_week = week_start(end_dt, week_day)
    all_weeks = pd.date_range(first_week, last_week, freq='7D')
    first_month = start_dt.to_period('M').to_timestamp()
    last_month = end_dt.to_period('M').to_timestamp()
    all_months = pd.date_range(first_month, last_month, freq='MS')

    all_days = pd.date_range(start_dt, end_dt, freq='D')
    if not df.empty:
        daily = (df.groupby(['acq_date', 'source']).size().unstack(fill_value=0)
                 .reindex(all_days, fill_value=0))
    else:
        daily = pd.DataFrame(0, index=all_days, columns=SENSORS)
    for s_ in SENSORS:
        if s_ not in daily.columns:
            daily[s_] = 0
    daily = daily[SENSORS].astype(int)
    daily['Total'] = daily.sum(axis=1)

    if not df.empty:
        df['week_label'] = week_start(df['acq_date'], week_day)
        df['month_label'] = df['acq_date'].dt.to_period('M').dt.to_timestamp()
        weekly = (df.groupby(['week_label', 'source']).size().unstack(fill_value=0)
                  .reindex(all_weeks, fill_value=0))
        monthly = (df.groupby(['month_label', 'source']).size().unstack(fill_value=0)
                   .reindex(all_months, fill_value=0))
    else:
        weekly = pd.DataFrame(0, index=all_weeks, columns=SENSORS)
        monthly = pd.DataFrame(0, index=all_months, columns=SENSORS)

    for s in SENSORS:
        if s not in weekly.columns:
            weekly[s] = 0
        if s not in monthly.columns:
            monthly[s] = 0
    weekly = weekly[SENSORS].astype(int)
    monthly = monthly[SENSORS].astype(int)
    weekly['Total'] = weekly.sum(axis=1)
    monthly['Total'] = monthly.sum(axis=1)

    partial_weeks = {}
    if first_week < start_dt:
        partial_weeks[first_week] = (start_dt, min(first_week + pd.Timedelta(days=6), end_dt))
    if last_week + pd.Timedelta(days=6) > end_dt:
        partial_weeks[last_week] = (max(last_week, start_dt), end_dt)

    # short periods (< 2 months, e.g. the onset of an eruption): daily + weekly panels and summary
    short = end_dt < start_dt + pd.DateOffset(months=2)

    summary = {}
    if not df.empty:
        last_day = df['acq_date'].max()
        lw0, lw1 = last_week, last_week + pd.Timedelta(days=6)
        summary = {
            'period_start': start_dt.strftime('%d/%m/%Y'),
            'period_end': end_dt.strftime('%d/%m/%Y'),
            'total_period': int(len(df)),
            'last_day': last_day.strftime('%d/%m/%Y'),
            'total_last_day': int((df['acq_date'] == last_day).sum()),
            'last_week_start': max(lw0, start_dt).strftime('%d/%m/%Y'),
            'last_week_end': min(lw1, end_dt).strftime('%d/%m/%Y'),
            'total_last_week': int(weekly.loc[last_week, 'Total']),
            'last_week_partial': last_week in partial_weeks,
            'last_month': end_dt.strftime('%B %Y'),
            'total_last_month': int(monthly.loc[last_month, 'Total']),
            'peak_week': int(weekly['Total'].max()),
            'peak_week_start': weekly['Total'].idxmax().strftime('%d/%m/%Y'),
            'peak_month': int(monthly['Total'].max()),
            'peak_month_label': monthly['Total'].idxmax().strftime('%B %Y'),
            'peak_day': int(daily['Total'].max()),
            'peak_day_label': daily['Total'].idxmax().strftime('%d/%m/%Y'),
            'n_days': int(len(daily)),
            'short': bool(short),
            'per_sensor': {s: int(df[df['source'] == s].shape[0]) for s in SENSORS if (df['source'] == s).any()},
        }
    return {'daily': daily, 'weekly': weekly, 'monthly': monthly, 'summary': summary,
            'partial_weeks': partial_weeks, 'start': start_dt, 'end': end_dt, 'week_day': week_day,
            'short': short}


# ==========================================
# 2. FIGURE
# ==========================================
def _label_font(n):
    return 11 if n <= 40 else 10 if n <= 80 else 8 if n <= 160 else 7


def _add_total_labels(fig, x, totals, row, n_bars):
    """Vertical total labels on top of each stacked bar (always readable, even with many bars)."""
    axis = '' if row == 1 else str(row)
    size = _label_font(n_bars)
    for xi, v in zip(x, totals):
        if v <= 0:
            continue
        fig.add_annotation(x=xi, y=v, xref=f'x{axis}', yref=f'y{axis}', text=str(int(v)),
                           textangle=-90, showarrow=False, yanchor='bottom', xanchor='center',
                           yshift=2, font=dict(size=size, color='#2c3e50'))


def _headroom(totals, n_bars):
    """Extra y-range so the vertical labels fit above the tallest bar."""
    digits = len(str(int(max(totals.max(), 1))))
    frac = 0.06 + 0.035 * digits * (_label_font(n_bars) / 10)
    return [0, max(totals.max(), 1) * (1 + frac)]


def build_counts_figure(agg, volcano, height=None):
    """
    Stacked bars per sensor with the total written (vertically) above each bar.
      * period < 2 months : daily (top)  + weekly (bottom)
      * otherwise         : weekly (top) + monthly (bottom)
    """
    daily, weekly, monthly = agg['daily'], agg['weekly'], agg['monthly']
    start_dt, end_dt = agg['start'], agg['end']
    diff_days = max((end_dt - start_dt).days, 1)
    short = agg.get('short', False)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.14)

    # ---------- weekly panel data ----------
    w_x = weekly.index + pd.Timedelta(days=3.5)
    w_lbl = [f"Week {i.strftime('%d %b %Y')} – {(i + pd.Timedelta(days=6)).strftime('%d %b %Y')}"
             + (" (partial)" if i in agg['partial_weeks'] else "") for i in weekly.index]
    if short:
        wstep = 1
    elif diff_days <= 365:
        wstep = 1 if len(weekly) <= 30 else 2
    elif diff_days <= 730:
        wstep = 4
    else:
        wstep = max(8, int(round(len(weekly) / 40)) * 4)

    # ---------- top / bottom definitions ----------
    if short:
        d_x = daily.index + pd.Timedelta(hours=12)
        d_lbl = [d.strftime('%d %b %Y') for d in daily.index]
        panels = [
            dict(row=1, df=daily, x=d_x, lbl=d_lbl, width=0.8 * 86400000, ytitle="Daily anomalies"),
            dict(row=2, df=weekly, x=w_x, lbl=w_lbl, width=0.8 * 7 * 86400000, ytitle="Weekly anomalies"),
        ]
    else:
        m_x = monthly.index + pd.to_timedelta(monthly.index.days_in_month / 2, unit='D')
        m_lbl = [m.strftime('%B %Y') for m in monthly.index]
        m_w = [0.8 * d * 86400000 for d in monthly.index.days_in_month]
        panels = [
            dict(row=1, df=weekly, x=w_x, lbl=w_lbl, width=0.8 * 7 * 86400000, ytitle="Weekly anomalies"),
            dict(row=2, df=monthly, x=m_x, lbl=m_lbl, width=m_w, ytitle="Monthly anomalies"),
        ]

    for pnl in panels:
        for src in SENSORS:
            fig.add_trace(go.Bar(
                x=pnl['x'], y=pnl['df'][src].values, width=pnl['width'], name=src,
                marker_color=lfc.SENSOR_COLORS[src], legendgroup=src, showlegend=(pnl['row'] == 1),
                customdata=pnl['lbl'],
                hovertemplate="<b>%{customdata}</b><br>" + src + ": %{y}<extra></extra>"),
                row=pnl['row'], col=1)
        # invisible trace so hovering anywhere over the bar also shows the total
        fig.add_trace(go.Scatter(
            x=pnl['x'], y=pnl['df']['Total'].values, mode='markers', marker=dict(size=1, opacity=0),
            showlegend=False, customdata=pnl['lbl'],
            hovertemplate="<b>%{customdata}</b><br>Total: %{y}<extra></extra>"), row=pnl['row'], col=1)
        _add_total_labels(fig, pnl['x'], pnl['df']['Total'].values, pnl['row'], len(pnl['df']))
        fig.update_yaxes(row=pnl['row'], col=1, title_text=pnl['ytitle'],
                         range=_headroom(pnl['df']['Total'], len(pnl['df'])))

    # ---------- x axes ----------
    if short:
        fig.update_xaxes(row=1, col=1, type='date', tickangle=45, tickformat="%d %b",
                         dtick=86400000 * (1 if diff_days <= 20 else 2 if diff_days <= 40 else 3),
                         tick0=daily.index[0] + pd.Timedelta(hours=12),
                         range=[daily.index[0] - pd.Timedelta(hours=6), daily.index[-1] + pd.Timedelta(hours=30)])
        wrow = 2
    else:
        fig.update_xaxes(row=2, col=1, type='date', tickangle=45,
                         dtick="M1" if diff_days <= 730 else ("M3" if diff_days <= 1500 else "M6"),
                         tickformat="%b %Y", ticklabelmode="period",
                         range=[monthly.index[0] - pd.Timedelta(days=2),
                                monthly.index[-1] + pd.offsets.MonthEnd(1) + pd.Timedelta(days=2)])
        wrow = 1
    tick_idx = weekly.index[::wstep]
    fig.update_xaxes(row=wrow, col=1, type='date', tickangle=45,
                     tickmode='array', tickvals=tick_idx + pd.Timedelta(days=3.5),
                     ticktext=[d.strftime('%d %b %y') for d in tick_idx],
                     range=[weekly.index[0] - pd.Timedelta(days=0.5),
                            weekly.index[-1] + pd.Timedelta(days=7.5)])

    fig.update_layout(
        title=dict(text=f"<b>FIRMS thermal anomalies — {volcano}</b><br>"
                        f"<span style='font-size:18px'>{start_dt.strftime('%d %b %Y')} – "
                        f"{end_dt.strftime('%d %b %Y')}</span>",
                   x=0.5, y=1.0, yref='paper', yanchor='bottom', pad=dict(b=40), font=dict(size=20)),
        barmode='stack', bargap=0, template="plotly_white", autosize=True,
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="center", x=0.5, title="Sensor:"),
        margin=dict(t=110, b=90, l=70, r=30), hovermode='closest',
    )
    if height:
        fig.update_layout(height=height)
    return fig


# ==========================================
# 3. SUMMARY PANEL
# ==========================================
def stat_tile(label, value, sub=None, cls=''):
    kids = [html.Div(label, className='k'), html.Div(value, className='v')]
    if sub:
        kids.append(html.Div(sub, className='s'))
    return html.Div(kids, className=f'lf-stat {cls}'.strip())


def summary_tiles(summary):
    """
    (label, value, sub-label, css-class) of the Period summary tiles.
    Periods shorter than two months use daily/weekly values (like the chart);
    longer periods use weekly/monthly values. Shared with the HTML export.
    """
    sm = summary
    week_lbl = "Last week" + (" (partial)" if sm['last_week_partial'] else "")
    week_sub = f"{sm['last_week_start']} – {sm['last_week_end']}"
    tiles = [("Whole period (all sensors)", sm['total_period'],
              f"{sm['period_start']} – {sm['period_end']} ({sm['n_days']} days)", 'accent'),
             ("Last day with data", sm['total_last_day'], sm['last_day'], '')]
    if sm.get('short'):
        tiles += [(week_lbl, sm['total_last_week'], week_sub, ''),
                  ("Max per day", sm['peak_day'], sm['peak_day_label'], 'alert'),
                  ("Max per week", sm['peak_week'], f"week of {sm['peak_week_start']}", 'alert')]
    else:
        tiles += [(week_lbl, sm['total_last_week'], week_sub, ''),
                  ("Last month", sm['total_last_month'], sm['last_month'], ''),
                  ("Max per week", sm['peak_week'], f"week of {sm['peak_week_start']}", 'alert'),
                  ("Max per month", sm['peak_month'], sm['peak_month_label'], 'alert')]
    return tiles


def build_stats_panel(summary):
    if not summary:
        return html.Div("No detections in this period.", className='lf-muted', style={'marginTop': '10px'})
    per_sensor = " · ".join(f"{k}: {v}" for k, v in summary['per_sensor'].items())
    mode = ("Period shorter than two months: daily and weekly values." if summary.get('short')
            else "Weekly and monthly values.")
    return html.Div([
        html.Hr(),
        html.H4("Period summary"),
        html.Div(mode, className='lf-muted'),
        html.Div([stat_tile(*t) for t in summary_tiles(summary)], className='lf-stats lf-stats-col'),
        html.Div(f"Per sensor: {per_sensor}", className='lf-muted'),
    ])


# ==========================================
# 4. LAYOUT
# ==========================================
def get_layout(start_date=None, end_date=None):
    cfg = load_global_config()
    volcano = cfg.get('volcano', 'Volcano Name')
    folder = get_active_folder()
    if not folder:
        return html.Div("No active project found. Please configure a volcano first.", className='lf-msg lf-msg-warn')

    name = os.path.basename(folder)
    if not any(os.path.exists(os.path.join(folder, p.format(name=name))) for p in SENSOR_FILES.values()):
        return html.Div([
            html.P("No satellite data found.", style={'fontWeight': '600'}),
            html.P("Run the FIRMS Download (tab 2) first to retrieve the satellite records.")
        ], className='lf-msg lf-msg-warn')

    start_date = start_date or datetime(2026, 1, 1)
    end_date = end_date or datetime(2026, 5, 1)

    return html.Div([
        html.Div([
            html.H2(f"Thermal anomaly counts — {volcano}"),
            html.P("Anomalies per sensor: daily + weekly for periods shorter than two months, weekly + monthly otherwise. "
                   "The number above each bar is its total; "
                   "the summary on the left uses exactly the same aggregation.", className='lf-note'),
        ]),
        html.Div([
            html.Div([
                html.H4("Controls"),
                html.Label("Analysis period", className='lf-label'),
                dcc.DatePickerRange(
                    id='stats-date-picker', display_format='DD/MM/YYYY',
                    start_date=pd.Timestamp(start_date).date(), end_date=pd.Timestamp(end_date).date()),
                html.Label("Week starting day", className='lf-label'),
                dcc.Dropdown(id='week-start-dropdown', clearable=False, value=3,
                             options=[{'label': d, 'value': i} for i, d in enumerate(WEEKDAYS)]),
                html.Br(),
                html.Button("UPDATE CHARTS", id="btn-gen-stats", n_clicks=0, className='lf-btn lf-btn-block'),
                html.Div(id='anomalies-summary-panel'),
            ], className='lf-card lf-sidebar'),
            html.Div([
                dcc.Graph(id='anomalies-count-plot', className='lf-graph',
                          style={'height': 'max(560px, 78vh)'},
                          config={'responsive': True, 'displaylogo': False,
                                  'toImageButtonOptions': {'format': 'png',
                                                           'filename': f'{lfc.safe_name(volcano)}_anomaly_counts',
                                                           'height': 1400, 'width': 1200, 'scale': 3}})
            ], className='lf-card lf-main'),
        ], className='lf-module'),
    ])


# ==========================================
# 5. CALLBACKS
# ==========================================
def register_callbacks(app):
    @app.callback(
        [Output('anomalies-count-plot', 'figure'), Output('anomalies-summary-panel', 'children')],
        Input('btn-gen-stats', 'n_clicks'),
        [State('stats-date-picker', 'start_date'), State('stats-date-picker', 'end_date'),
         State('week-start-dropdown', 'value')],
        prevent_initial_call=False
    )
    def update_charts(n, start, end, week_day):
        df_raw = load_historical_data()
        if df_raw.empty:
            return go.Figure(), build_stats_panel({})
        start_dt, end_dt = pd.to_datetime(start), pd.to_datetime(end)
        if pd.isna(start_dt) or pd.isna(end_dt) or end_dt < start_dt:
            return go.Figure(), html.Div("Invalid period.", className='lf-msg lf-msg-err')
        agg = aggregate_counts(df_raw, start_dt, end_dt, int(week_day or 3))
        volcano = load_global_config().get('volcano', 'Volcano Name')
        return build_counts_figure(agg, volcano), build_stats_panel(agg['summary'])


if __name__ == '__main__':
    from dash import Dash
    app = Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True, port=8060)
