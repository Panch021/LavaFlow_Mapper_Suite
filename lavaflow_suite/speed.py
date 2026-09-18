"""
lavaflow_suite/speed.py
=======================
Propagation speed of the flow front, estimated from the days on which the
maximum distance to the vent increases.

Max distance, max speed and mean speed are recomputed for the time
window visible in the chart (zoom / pan / reset). A button on the chart
shows or hides the reference radius.
"""
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc, Input, Output, no_update

from . import common as lfc

get_active_folder = lfc.get_active_folder
load_global_config = lfc.load_global_config


# ==========================================
# 1. DATA ENGINE
# ==========================================
def compute_speed(daily):
    """
    daily: DataFrame with 'date_only' and 'distance_km' (one or more rows per day).
    Rows from different satellites on the same day are merged first (daily
    maximum), otherwise same-day records produced artificial zero speeds.
    Returns the days on which the running maximum distance increased, with
    the speed (m/h) relative to the previous advance. The first advance has
    no reference and therefore no speed (NaN).
    """
    d = daily.copy()
    d['date'] = pd.to_datetime(d['date_only'])
    d = d.groupby('date', as_index=False)['distance_km'].max().sort_values('date')
    d['max_distance'] = d['distance_km'].cummax()
    d['prev_max'] = d['max_distance'].shift(1, fill_value=0)
    p = d[d['distance_km'] > d['prev_max']].copy()
    if p.empty:
        return p
    p['time_diff'] = p['date'].diff().dt.total_seconds() / 3600.0       # hours
    p['distance_diff'] = (p['max_distance'] - p['prev_max']) * 1000.0    # metres
    p['speed'] = np.where(p['time_diff'] > 0, p['distance_diff'] / p['time_diff'], np.nan)
    return p.reset_index(drop=True)


def process_speed_data(folder=None):
    folder = folder or get_active_folder()
    if not folder:
        return None
    fp = os.path.join(folder, "max_distance_per_day_VIIRS.csv")
    if not os.path.exists(fp):
        return None
    p = compute_speed(pd.read_csv(fp))
    if not p.empty:
        p.to_csv(os.path.join(folder, "LavaFlow_propagation.csv"), index=False)
    return p


def load_speed_data(folder=None):
    folder = folder or get_active_folder()
    fp = os.path.join(folder, "LavaFlow_propagation.csv") if folder else None
    if not fp or not os.path.exists(fp):
        return pd.DataFrame()
    df = pd.read_csv(fp)
    df['date'] = lfc.parse_firms_date(df['date'])
    return df.dropna(subset=['date'])


def compute_speed_stats(df, x0=None, x1=None):
    d = df
    if x0 is not None and not pd.isna(x0):
        d = d[d['date'] >= pd.Timestamp(x0)]
    if x1 is not None and not pd.isna(x1):
        d = d[d['date'] <= pd.Timestamp(x1)]
    sp = d['speed'].dropna() if 'speed' in d else pd.Series(dtype=float)
    return {'n': int(len(d)),
            'max_dist': float(d['max_distance'].max()) if len(d) else None,
            'max_speed': float(sp.max()) if len(sp) else None,
            'mean_speed': float(sp.mean()) if len(sp) else None,
            'x0': x0, 'x1': x1}


# ==========================================
# 2. FIGURE & PANEL (shared with the export)
# ==========================================
def build_speed_figure(df, cfg, title=True):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df['date'], y=df['max_distance'], name="Max distance",
                             mode='lines+markers', line=dict(color='black', width=2, dash='dash'),
                             marker=dict(size=7),
                             hovertemplate="%{x|%d/%m/%Y}<br>Max distance: %{y:.2f} km<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=df['date'], y=df['speed'], name="Propagation speed",
                             mode='lines+markers', connectgaps=True,
                             line=dict(color='#c0392b', width=2, dash='dot'),
                             marker=dict(size=8, symbol='diamond'),
                             hovertemplate="%{x|%d/%m/%Y}<br>Speed: %{y:.1f} m/h<extra></extra>"),
                  secondary_y=True)

    menus = []
    if cfg.get('include_reference_radius') and not df.empty:
        rk = float(cfg.get('ref_radius_m', 5000)) / 1000.0
        pad = pd.Timedelta(days=1)
        fig.add_trace(go.Scatter(x=[df['date'].min() - pad, df['date'].max() + pad], y=[rk, rk], mode='lines',
                                 name=f"Ref. radius ({rk:.2f} km)", line=dict(color='#2980b9', width=1.5, dash='dash'),
                                 hovertemplate=f"Ref. radius: {rk:.2f} km<extra></extra>"), secondary_y=False)
        idx = len(fig.data) - 1
        menus = [dict(type='buttons', direction='right', x=1.0, xanchor='right', y=1.02, yanchor='bottom',
                      showactive=True, active=0, pad=dict(r=2, t=2, b=2, l=2), font=dict(size=11),
                      bgcolor='white', bordercolor='#cfd4da',
                      buttons=[dict(label='Radius on', method='restyle', args=[{'visible': True}, [idx]]),
                               dict(label='Radius off', method='restyle', args=[{'visible': False}, [idx]])])]

    s = df['date'].min().strftime('%d/%m/%Y') if not df.empty else ''
    e = df['date'].max().strftime('%d/%m/%Y') if not df.empty else ''
    fig.update_layout(
        title=dict(text=f"Lava flow propagation — {cfg.get('volcano', '')}<br><sup>{s} – {e}</sup>",
                   x=0.5, font=dict(size=17)) if title else None,
        template="plotly_white", autosize=True, updatemenus=menus, uirevision='speed',
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5),
        margin=dict(t=80 if title else 40, b=60, l=70, r=70))
    fig.update_xaxes(gridcolor='#eee')
    fig.update_yaxes(title_text="Maximum distance (km)", secondary_y=False, rangemode='tozero', gridcolor='#eee')
    fig.update_yaxes(title_text="Propagation speed (m/h)", secondary_y=True, color='#c0392b',
                     rangemode='tozero', showgrid=False)
    return fig


def build_speed_panel(st):
    def f(v, unit, dec):
        return f"{v:.{dec}f} {unit}" if v is not None else "–"

    def fmt(x):
        return pd.Timestamp(x).strftime('%d/%m/%Y') if x is not None and not pd.isna(x) else '–'

    return html.Div([
        html.Div([html.Span("Statistics for the visible window: ", style={'fontWeight': '600'}),
                  html.Span(f"{fmt(st['x0'])} → {fmt(st['x1'])} · {st['n']} advances", className='lf-muted'),
                  html.Span("  (zoom or pan to update; double-click to reset)", className='lf-muted')]),
        html.Div([
            html.Div([html.Div("Max distance", className='k'), html.Div(f(st['max_dist'], 'km', 2), className='v')],
                     className='lf-stat'),
            html.Div([html.Div("Max speed", className='k'), html.Div(f(st['max_speed'], 'm/h', 1), className='v')],
                     className='lf-stat alert'),
            html.Div([html.Div("Mean speed", className='k'), html.Div(f(st['mean_speed'], 'm/h', 1), className='v')],
                     className='lf-stat accent'),
        ], className='lf-stats'),
    ])


# ==========================================
# 3. LAYOUT
# ==========================================
def get_layout():
    folder = get_active_folder()
    cfg = load_global_config()
    if not folder:
        return html.Div("No active project found. Please configure a volcano first.", className='lf-msg lf-msg-warn')
    if not os.path.exists(os.path.join(folder, "max_distance_per_day_VIIRS.csv")):
        return html.Div("No mapper results found. Run the LavaFlow Mapper (tab 5) first.",
                        className='lf-msg lf-msg-warn')

    process_speed_data(folder)
    data = load_speed_data(folder)
    if data.empty:
        return html.Div("No propagation data found (run the Mapper first).", className='lf-msg lf-msg-warn')

    volcano = cfg.get('volcano', 'Volcano')
    fig = build_speed_figure(data, cfg)
    return html.Div([
        html.Div([
            html.Div(id='speed-stats', children=build_speed_panel(compute_speed_stats(data))),
            dcc.Graph(id='speed-graph', figure=fig, className='lf-graph',
                      style={'height': 'clamp(420px, 65vh, 800px)'},
                      config={'responsive': True, 'displaylogo': False,
                              'toImageButtonOptions': {'format': 'png', 'filename': f"{lfc.safe_name(volcano)}_speed",
                                                       'height': 800, 'width': 1200, 'scale': 3}}),
            html.P("Speed = increase of the maximum distance between two consecutive advances divided by the "
                   "elapsed time. Detections of different satellites on the same day are merged (daily maximum).",
                   className='lf-muted'),
        ], className='lf-card'),
    ])


# ==========================================
# 4. CALLBACKS
# ==========================================
def register_callbacks(app):
    @app.callback(Output('speed-stats', 'children'), Input('speed-graph', 'relayoutData'),
                  prevent_initial_call=True)
    def update_speed_stats(relayout):
        df = load_speed_data()
        if df.empty:
            return no_update
        x0, x1 = lfc.xrange_from_relayout(relayout, fallback=(None, None))
        if x0 is None and relayout and not any(k.endswith('autorange') for k in relayout):
            return no_update
        return build_speed_panel(compute_speed_stats(df, x0, x1))


if __name__ == "__main__":
    from dash import Dash
    app = Dash(__name__)
    app.layout = get_layout()
    register_callbacks(app)
    app.run(debug=True, port=8080)
