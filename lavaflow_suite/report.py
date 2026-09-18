"""
lavaflow_suite/report.py
========================
Builds a self-contained, responsive HTML report of the active project.

Every figure is produced by the SAME builder used in the corresponding tab
(Anomalies_count, LavaFlow_mapper, LavaFlow_speed), so the report is
identical to what the user sees in the app:

  * anomaly counts with weekly/monthly totals and the same period summary,
  * folium map + FRP/distance series whose mean/P95/max follow the zoom,
  * propagation speed with the radius on/off button and zoom-following stats,
  * optionally, the propagation video (rendered here or in tab 6).
"""
import base64
import json
import os
from datetime import datetime

import pandas as pd
from dash import html, dcc, Input, Output, State, no_update

from . import common as lfc
from . import anomalies as anomalies_module
from . import mapper as mapper_module
from . import speed as speed_module
from . import video as video
from . import animation as anim_module

get_active_folder = lfc.get_active_folder
load_global_config = lfc.load_global_config
parse_firms_date = lfc.parse_firms_date
parse_waypoints_from_config = lfc.parse_waypoints_from_config

VIDEO_EMBED_LIMIT_MB = 40
PLOTLY_CFG = {'displaylogo': False, 'responsive': True}


# ==========================================
# 1. SECTION BUILDERS
# ==========================================
def _tile(label, value, sub='', cls=''):
    sub_html = f'<div class="stat-meta">{sub}</div>' if sub else ''
    return (f'<div class="stat-box {cls}"><div class="stat-label">{label}</div>'
            f'<div class="stat-value">{value}</div>{sub_html}</div>')


def build_anomalies_section(folder, cfg, week_day, plotly_js):
    df = anomalies_module.load_historical_data(folder)
    s, e = lfc.get_period(cfg)
    if df.empty or pd.isna(s) or pd.isna(e):
        return None
    agg = anomalies_module.aggregate_counts(df, s, e, week_day)
    fig = anomalies_module.build_counts_figure(agg, cfg.get('volcano', ''), height=760)
    sm = agg['summary']
    stats = ""
    if sm:
        per = " · ".join(f"{k}: {v}" for k, v in sm['per_sensor'].items())
        stats = ('<div class="stats-section"><div class="stats-title">📊 Period Summary (all sensors)</div>'
                 '<div class="stats-grid">'
                 + ''.join(_tile(*t) for t in anomalies_module.summary_tiles(sm))
                 + f'</div><p class="note">Per sensor — {per}. The number above each bar is its total '
                   f'(weeks start on {anomalies_module.WEEKDAYS[week_day]}).</p></div>')
    chart = fig.to_html(full_html=False, include_plotlyjs=plotly_js(), config=PLOTLY_CFG)
    return "📈 Thermal Anomaly Counts", stats + chart


def _series_payload(dates, **cols):
    out = {'t': [d.strftime('%Y-%m-%dT%H:%M:%S') for d in pd.to_datetime(dates)]}
    for k, v in cols.items():
        out[k] = [None if pd.isna(x) else round(float(x), 4) for x in v]
    return json.dumps(out)


def build_mapper_section(folder, cfg, plotly_js):
    df = lfc.load_filtered_data(folder)
    if df.empty:
        return None
    map_html, warning = mapper_module.build_folium_map(folder, cfg, df, labels=True, fit='anomalies',
                                                        default_basemap='topo')
    fig = mapper_module.build_timeseries_figure(df, cfg)
    fig.update_layout(height=720)
    s, e = lfc.get_period(cfg)
    st = mapper_module.compute_ts_stats(df, s, e)

    def grp(prefix, title, stat, unit, dec):
        vals = stat or {'mean': float('nan'), 'p95': float('nan'), 'max': float('nan')}
        return (f'<div class="stat-group"><div class="stats-title">{title}</div><div class="stats-grid">'
                + _tile("Mean", f'<span id="{prefix}-mean">{vals["mean"]:.{dec}f}</span> {unit}', cls='accent')
                + _tile("P95", f'<span id="{prefix}-p95">{vals["p95"]:.{dec}f}</span> {unit}', cls='accent')
                + _tile("Max", f'<span id="{prefix}-max">{vals["max"]:.{dec}f}</span> {unit}', cls='accent')
                + '</div></div>')

    stats = (f'<div class="window-note">Statistics for the visible window: <b id="ts-window">'
             f'{s.strftime("%d/%m/%Y")} → {e.strftime("%d/%m/%Y")}</b> · <span id="ts-n">{st["n"]}</span> anomalies '
             f'<span class="note">(zoom or pan the chart to update; double-click to reset)</span></div>'
             f'<div class="stats-title">📊 Period Summary (all satellites)</div>'
             f'<div class="two-col">{grp("frp", "FRP", st["frp"], "MW", 1)}'
             f'{grp("dist", "Distance to vent", st["dist"], "km", 2)}</div>')

    chart = fig.to_html(full_html=False, include_plotlyjs=plotly_js(), config=PLOTLY_CFG, div_id='ts-graph')
    payload = _series_payload(df['date'], frp=df['frp'], dist=df['distance_km'])
    script = f"""
<script>
(function() {{
  var D = {payload};
  var T = D.t.map(function(s) {{ return new Date(s).getTime(); }});
  var FULL = [new Date('{s.strftime('%Y-%m-%dT%H:%M:%S')}').getTime(), new Date('{e.strftime('%Y-%m-%dT%H:%M:%S')}').getTime()];
  function q(a, p) {{ if (!a.length) return NaN; a = a.slice().sort(function(x, y) {{ return x - y; }});
    var pos = (a.length - 1) * p, lo = Math.floor(pos), hi = Math.ceil(pos);
    return a[lo] + (a[hi] - a[lo]) * (pos - lo); }}
  function st(a) {{ if (!a.length) return [NaN, NaN, NaN];
    var s = 0; a.forEach(function(v) {{ s += v; }}); return [s / a.length, q(a, 0.95), Math.max.apply(null, a)]; }}
  function fmt(v, d) {{ return isNaN(v) ? '–' : v.toFixed(d); }}
  function pd(ms) {{ var d = new Date(ms); return ('0'+d.getDate()).slice(-2)+'/'+('0'+(d.getMonth()+1)).slice(-2)+'/'+d.getFullYear(); }}
  function upd(x0, x1) {{
    var f = [], g = [];
    for (var i = 0; i < T.length; i++) if (T[i] >= x0 && T[i] <= x1) {{
      if (D.frp[i] !== null) f.push(D.frp[i]); if (D.dist[i] !== null) g.push(D.dist[i]); }}
    var a = st(f), b = st(g);
    ['mean', 'p95', 'max'].forEach(function(k, j) {{
      document.getElementById('frp-' + k).textContent = fmt(a[j], 1);
      document.getElementById('dist-' + k).textContent = fmt(b[j], 2); }});
    document.getElementById('ts-n').textContent = f.length;
    document.getElementById('ts-window').textContent = pd(x0) + ' → ' + pd(x1);
  }}
  function toMs(v) {{ return new Date(String(v).replace(' ', 'T')).getTime(); }}
  function attach() {{
    var gd = document.getElementById('ts-graph');
    if (!gd || !gd.on) {{ setTimeout(attach, 200); return; }}
    gd.on('plotly_relayout', function(ev) {{
      var x0, x1, auto = false;
      Object.keys(ev).forEach(function(k) {{
        if (/^xaxis\\d*\\.range\\[0\\]$/.test(k)) x0 = ev[k];
        else if (/^xaxis\\d*\\.range\\[1\\]$/.test(k)) x1 = ev[k];
        else if (/^xaxis\\d*\\.range$/.test(k)) {{ x0 = ev[k][0]; x1 = ev[k][1]; }}
        else if (/^xaxis\\d*\\.autorange$/.test(k)) auto = true; }});
      if (x0 !== undefined && x1 !== undefined) upd(toMs(x0), toMs(x1));
      else if (auto) upd(FULL[0], FULL[1]);
    }});
  }}
  window.addEventListener('load', attach);
}})();
</script>"""
    warn = f'<p class="warn">{warning}</p>' if warning else ''
    body = (warn + f'<div class="map-container"><iframe srcdoc="{_escape_attr(map_html)}" '
                   f'referrerpolicy="strict-origin-when-cross-origin"></iframe></div>'
            + '<h3 class="ts-header">📊 FRP & Distance Time Series</h3>' + stats + chart + script)
    return "🌋 Thermal Anomaly Map", body


def _escape_attr(s):
    return s.replace('&', '&amp;').replace('"', '&quot;')


def build_speed_section(folder, cfg, plotly_js):
    if os.path.exists(os.path.join(folder, "max_distance_per_day_VIIRS.csv")):
        speed_module.process_speed_data(folder)
    df = speed_module.load_speed_data(folder)
    if df.empty:
        return None
    fig = speed_module.build_speed_figure(df, cfg)
    fig.update_layout(height=560)
    st = speed_module.compute_speed_stats(df)

    def f(v, d):
        return '–' if v is None else f"{v:.{d}f}"

    stats = (f'<div class="window-note">Statistics for the visible window: <b id="sp-window">'
             f'{df["date"].min().strftime("%d/%m/%Y")} → {df["date"].max().strftime("%d/%m/%Y")}</b> · '
             f'<span id="sp-n">{st["n"]}</span> advances '
             f'<span class="note">(zoom or pan the chart to update; double-click to reset)</span></div>'
             '<div class="stats-grid">'
             + _tile("Max distance", f'<span id="sp-maxd">{f(st["max_dist"], 2)}</span> km')
             + _tile("Max speed", f'<span id="sp-maxs">{f(st["max_speed"], 1)}</span> m/h', cls='alert alert-box')
             + _tile("Mean speed", f'<span id="sp-means">{f(st["mean_speed"], 1)}</span> m/h', cls='alert alert-box')
             + '</div>')
    chart = fig.to_html(full_html=False, include_plotlyjs=plotly_js(), config=PLOTLY_CFG, div_id='speed-graph')
    payload = _series_payload(df['date'], d=df['max_distance'], v=df['speed'])
    script = f"""
<script>
(function() {{
  var D = {payload};
  var T = D.t.map(function(s) {{ return new Date(s).getTime(); }});
  function toMs(v) {{ return new Date(String(v).replace(' ', 'T')).getTime(); }}
  function pd(ms) {{ var d = new Date(ms); return ('0'+d.getDate()).slice(-2)+'/'+('0'+(d.getMonth()+1)).slice(-2)+'/'+d.getFullYear(); }}
  function upd(x0, x1) {{
    var md = -Infinity, ms = -Infinity, s = 0, c = 0, n = 0;
    for (var i = 0; i < T.length; i++) if (T[i] >= x0 && T[i] <= x1) {{
      n++; if (D.d[i] !== null) md = Math.max(md, D.d[i]);
      if (D.v[i] !== null) {{ ms = Math.max(ms, D.v[i]); s += D.v[i]; c++; }} }}
    document.getElementById('sp-maxd').textContent = isFinite(md) ? md.toFixed(2) : '–';
    document.getElementById('sp-maxs').textContent = isFinite(ms) ? ms.toFixed(1) : '–';
    document.getElementById('sp-means').textContent = c ? (s / c).toFixed(1) : '–';
    document.getElementById('sp-n').textContent = n;
    document.getElementById('sp-window').textContent = pd(x0) + ' → ' + pd(x1);
  }}
  function attach() {{
    var gd = document.getElementById('speed-graph');
    if (!gd || !gd.on) {{ setTimeout(attach, 200); return; }}
    gd.on('plotly_relayout', function(ev) {{
      if (ev['xaxis.range[0]'] !== undefined) upd(toMs(ev['xaxis.range[0]']), toMs(ev['xaxis.range[1]']));
      else if (ev['xaxis.range']) upd(toMs(ev['xaxis.range'][0]), toMs(ev['xaxis.range'][1]));
      else if (ev['xaxis.autorange']) upd(-Infinity, Infinity);
    }});
  }}
  window.addEventListener('load', attach);
}})();
</script>"""
    return "🚀 Propagation Speed", stats + chart + script


def build_video_section(folder, cfg, embed=True):
    path = video.output_path(folder, cfg)
    if not os.path.exists(path):
        return None
    size_mb = os.path.getsize(path) / 1e6
    name = os.path.basename(path)
    if embed and size_mb <= VIDEO_EMBED_LIMIT_MB:
        with open(path, 'rb') as f:
            src = "data:video/mp4;base64," + base64.b64encode(f.read()).decode()
        note = f"{name} ({size_mb:.1f} MB, embedded)"
    else:
        src = name
        note = (f"{name} ({size_mb:.1f} MB) is linked, not embedded — keep the video in the same folder "
                f"as this report when sharing it.")
    body = (f'<div class="video-wrap"><video controls preload="metadata" src="{src}"></video></div>'
            f'<p class="note">{note}</p>')
    return "🎬 Propagation Video", body


# ==========================================
# 2. HTML REPORT ASSEMBLER
# ==========================================
REPORT_CSS = """
        /* ========== BASE LAYOUT ========== */
        * { box-sizing: border-box; }
        html, body { width: 100%; overflow-x: hidden; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f6fa;
            color: #2c3e50;
            line-height: 1.4;
        }

        /* ========== HEADER ========== */
        .header {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: clamp(14px, 3vw, 24px) clamp(10px, 3vw, 20px);
            text-align: center;
        }
        .header h1 { margin: 0 0 6px 0; font-size: clamp(16px, 4.5vw, 28px); line-height: 1.2; }
        .header p { margin: 4px 0; opacity: 0.85; font-size: clamp(11px, 2.5vw, 14px); }

        /* ========== CONTAINER & SECTIONS ========== */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: clamp(8px, 2vw, 16px);
        }
        .section {
            background: white;
            border-radius: clamp(6px, 1.5vw, 10px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: clamp(10px, 2.5vw, 18px);
            margin-bottom: clamp(10px, 2vw, 18px);
            overflow: hidden;
        }
        .section h2 {
            margin: 0 0 12px 0;
            font-size: clamp(15px, 3.5vw, 20px);
            color: #2980b9;
            border-bottom: 2px solid #eee;
            padding-bottom: 8px;
        }

        /* ========== TIME-SERIES SUBSECTION HEADER ========== */
        .ts-header {
            color: #2980b9;
            margin: clamp(24px, 6vw, 60px) 0 8px 0;
            font-size: clamp(13px, 3vw, 16px);
        }

        /* ========== PROJECT PARAMETERS META GRID ========== */
        .meta-grid {
            display: flex;
            gap: clamp(6px, 1.5vw, 10px);
            flex-wrap: wrap;
            margin-bottom: 5px;
        }
        .meta-box {
            background: #f0f4f8;
            border: 1px solid #dde;
            border-radius: 6px;
            padding: clamp(6px, 1.5vw, 10px) clamp(8px, 2vw, 14px);
            flex: 1 1 130px;
            min-width: 0;
        }
        .meta-box .label { font-size: clamp(9px, 2vw, 11px); color: #7f8c8d; }
        .meta-box .value {
            font-size: clamp(12px, 2.5vw, 16px);
            font-weight: bold;
            color: #2c3e50;
            word-break: break-word;
        }

        /* ========== STATS PANELS ========== */
        .stats-section { margin-bottom: clamp(12px, 2.5vw, 20px); }
        .stats-title {
            font-weight: bold;
            font-size: clamp(12px, 2.6vw, 14px);
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .stats-grid {
            display: flex;
            gap: clamp(6px, 1.5vw, 12px);
            flex-wrap: wrap;
            margin: 12px 0 16px 0;
        }
        .stat-box {
            flex: 1 1 140px;
            min-width: 0;
            padding: clamp(8px, 2vw, 14px) clamp(10px, 2vw, 18px);
            background: #f0f4f8;
            border: 1px solid #dde;
            border-radius: 8px;
        }
        .stat-box--outlined { border: 2px solid #2980b9; text-align: center; }
        .stat-box--alert    { background: #eaf4fb; border: 2px solid #e74c3c; }
        .stat-label {
            font-size: clamp(10px, 2vw, 11px);
            color: #7f8c8d;
            margin-bottom: 4px;
        }
        .stat-value {
            font-size: clamp(16px, 4vw, 22px);
            font-weight: bold;
            color: #2c3e50;
            line-height: 1.1;
        }
        .stat-value--accent { color: #2980b9; }
        .stat-value--alert  { color: #e74c3c; }
        .stat-meta { font-size: clamp(9px, 2vw, 11px); color: #95a5a6; margin-top: 2px; }

        /* ========== MAP CONTAINER ========== */
        .map-container {
            width: 100%;
            max-width: 1100px;
            margin: 0 0 20px 0;
        }
        .map-container iframe {
            width: 100% !important;
            max-width: 100%;
            border: none;
            border-radius: 8px;
            display: block;
        }

        /* ========== PLOTLY CHARTS ========== */
        .chart { width: 100%; min-width: 0; overflow-x: auto; }
        .chart .plotly-graph-div { width: 100% !important; }
        .chart .js-plotly-plot { width: 100% !important; }

        /* ========== FOOTER ========== */
        .footer {
            text-align: center;
            padding: clamp(10px, 2.5vw, 18px);
            font-size: clamp(10px, 2vw, 12px);
            color: #999;
        }

        /* ========== RESPONSIVE BREAKPOINTS ========== */
        @media (max-width: 768px) {
            .meta-box { flex: 1 1 calc(50% - 6px); }
            .stat-box { flex: 1 1 calc(50% - 6px); }
        }

        @media (max-width: 480px) {
            .stats-grid { gap: 6px; }
            .meta-grid  { gap: 6px; }
            .stat-box   { padding: 8px 10px; }
            .meta-box   { flex: 1 1 calc(50% - 3px); }
        }

        @media (max-width: 360px) {
            .stat-box { flex: 1 1 100%; }
            .meta-box { flex: 1 1 100%; }
        }
            /* ========== ADDITIONS (new sections) ========== */
        .stat-box.accent  { border: 2px solid #2980b9; text-align: center; }
        .stat-box.accent .stat-value { color: #2980b9; }
        .stat-box.alert .stat-value { color: #e74c3c; }
        .stat-box.alert-box { background: #eaf4fb; border: 2px solid #e74c3c; }
        .two-col { display: flex; flex-wrap: wrap; gap: 16px; }
        .two-col .stat-group { flex: 1 1 320px; min-width: 0; }
        .window-note { font-size: clamp(11px, 2.4vw, 13px); margin: 6px 0; }
        .note { color: #7f8c8d; font-size: clamp(10px, 2vw, 12px); }
        .warn { background: #fff3cd; border: 1px solid #ffc107; color: #856404; padding: 8px 12px;
                border-radius: 6px; font-weight: bold; }
        .map-container iframe { height: clamp(360px, 65vh, 720px); }
        .video-wrap { display: flex; justify-content: center; }
        .video-wrap video { width: 100%; max-width: 620px; max-height: 88vh; border-radius: 8px; background: black; }
        .credits { max-width: 1200px; margin: 0 auto; padding: 14px clamp(8px, 2vw, 18px) 0;
                   font-size: clamp(11px, 2.4vw, 13px); color: #555; line-height: 1.5; text-align: center; }
        .credits a { color: #2980b9; word-break: break-all; }
"""


def generate_report(output_path, selected_sections=None, week_day=3, embed_video=True):
    folder = get_active_folder()
    if not folder:
        return False, "No active project found."
    selected_sections = selected_sections or ['anomalies', 'mapper', 'speed', 'video']
    cfg = load_global_config()
    volcano = cfg.get('volcano', os.path.basename(folder))
    s, e = lfc.get_period(cfg)
    start_str = s.strftime('%d/%m/%Y') if not pd.isna(s) else 'N/A'
    end_str = e.strftime('%d/%m/%Y') if not pd.isna(e) else 'N/A'
    generated_on = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Plotly.js from the CDN matching the installed plotly version, loaded once.
    state = {'loaded': False}

    def plotly_js():
        if state['loaded']:
            return False
        state['loaded'] = True
        return 'cdn'

    sections = []
    builders = [
        ('anomalies', lambda: build_anomalies_section(folder, cfg, week_day, plotly_js)),
        ('mapper', lambda: build_mapper_section(folder, cfg, plotly_js)),
        ('speed', lambda: build_speed_section(folder, cfg, plotly_js)),
        ('video', lambda: build_video_section(folder, cfg, embed_video)),
    ]
    for key, fn in builders:
        if key in selected_sections:
            try:
                res = fn()
                if res:
                    sections.append(res)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                sections.append((key.capitalize(), f'<p class="warn">Section could not be generated: {ex}</p>'))
    if not sections:
        return False, "No results available for the selected sections. Run the required modules first."

    layers = []
    if cfg.get('include_reference_radius'):
        layers.append(f"radius {cfg.get('ref_radius_m')} m")
    if cfg.get('include_shapefile') and cfg.get('shapefile_path'):
        layers.append(f"shapefile {cfg.get('shapefile_path')}")
    if cfg.get('include_reference_waypoint'):
        n = len(parse_waypoints_from_config(cfg))
        if n:
            layers.append(f"{n} waypoint(s)")
    layers_txt = ", ".join(layers) if layers else "none"
    frp_sign = '≥' if cfg.get('frp_filter_mode', 'gt') == 'gt' else '≤'

    body = "".join(f'<div class="section"><h2>{h}</h2><div class="chart">{c}</div></div>' for h, c in sections)
    html_report = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LavaFlow report — {volcano}</title>
<script>
  function resizePlotly() {{
    document.querySelectorAll('.plotly-graph-div').forEach(function(g) {{
      try {{ Plotly.Plots.resize(g); }} catch (e) {{}} }});
  }}
  window.addEventListener('load', resizePlotly);
  window.addEventListener('resize', resizePlotly);
  window.addEventListener('orientationchange', resizePlotly);
</script>
<style>{REPORT_CSS}</style>
</head>
<body>
<div class="header">
  <h1>🌋 LavaFlow Mapper Suite — {volcano}</h1>
  <p>Analysis period: {start_str} — {end_str}</p>
  <p>Generated: {generated_on}</p>
</div>
<div class="container">
  <div class="section">
    <h2>⚙️ Project Parameters</h2>
    <div class="meta-grid">
      <div class="meta-box"><div class="label">Volcano</div><div class="value">{volcano}</div></div>
      <div class="meta-box"><div class="label">Vent Lat / Lon</div><div class="value">{cfg.get('lats_vent')} / {cfg.get('longs_vent')}</div></div>
      <div class="meta-box"><div class="label">FRP Filter</div><div class="value">{frp_sign} {cfg.get('filter_frp')} MW</div></div>
      <div class="meta-box"><div class="label">Track Filter</div><div class="value">≤ {cfg.get('filter_track')}</div></div>
      <div class="meta-box"><div class="label">Reference Layers</div><div class="value">{layers_txt}</div></div>
    </div>
  </div>
  {body}
</div>
<div class="credits">
  Results obtained with the methodology of Vasconez et al. (2022),
  <a href="https://doi.org/10.3390/rs14143483" target="_blank" rel="noopener">https://doi.org/10.3390/rs14143483</a>,
  implemented in LavaFlow Mapper Suite. The code is freely available at
  <a href="https://github.com/Panch021/LavaFlow_Mapper_Suite" target="_blank" rel="noopener">https://github.com/Panch021/LavaFlow_Mapper_Suite</a>.
</div>
<div class="footer">LavaFlow Suite · Report generated on {generated_on} · Data source: NASA FIRMS</div>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_report)
    return True, f"Report saved: {output_path}"


def report_path(folder, cfg):
    return os.path.join(folder, f"{lfc.safe_name(cfg.get('volcano', 'Volcano'))}_{lfc.period_tag(cfg)}_report.html")


# ==========================================
# 3. DASH LAYOUT
# ==========================================
def get_layout():
    folder = get_active_folder()
    cfg = load_global_config()
    if not folder:
        return html.Div("No active project found. Please configure a volcano first.", className='lf-msg lf-msg-warn')

    name = os.path.basename(folder)
    has_raw = any(os.path.exists(os.path.join(folder, p.format(name=name)))
                  for p in anomalies_module.SENSOR_FILES.values())
    has_map = os.path.exists(os.path.join(folder, "filter_VIIRS_combined.csv"))
    has_speed = os.path.exists(os.path.join(folder, "max_distance_per_day_VIIRS.csv"))
    vid = video.output_path(folder, cfg)
    has_video = os.path.exists(vid)

    checks = [('anomalies', 'Anomaly counts', has_raw, 'run FIRMS Download'),
              ('mapper', 'Thermal anomaly map + time series', has_map, 'run the Mapper'),
              ('speed', 'Propagation speed', has_speed, 'run the Mapper'),
              ('video', 'Propagation video', has_video, 'render it below or in tab 6')]
    options = [{'label': f" {lbl}" + ("" if ok else f"  —  not available ({hint})"), 'value': k, 'disabled': not ok}
               for k, lbl, ok, hint in checks]
    values = [k for k, _, ok, _ in checks if ok]

    settings = video.load_settings(folder)
    settings_txt = ("uses the view, basemap, layers and speed of your last render in tab 6"
                    if settings else "no previous render: full anomaly extent, Esri imagery, all enabled layers, speed 5")

    return html.Div([
        html.H2("Export HTML report"),
        html.P("The report reproduces the figures of tabs 3, 5, 6 and 7 with the same statistics and controls, "
               "and opens in any browser without Python.", className='lf-note'),
        html.Div([
            html.Div([
                html.H4("1 · Sections"),
                dcc.Checklist(id='export-section-toggle', options=options, value=values, className='lf-checks'),
                html.Label("Week starting day (anomaly counts)", className='lf-label'),
                dcc.Dropdown(id='export-week-day', value=3, clearable=False,
                             options=[{'label': d, 'value': i} for i, d in enumerate(anomalies_module.WEEKDAYS)],
                             style={'maxWidth': '220px'}),
                dcc.Checklist(id='export-embed-video', value=['embed'], className='lf-checks',
                              options=[{'label': f' Embed the video inside the HTML (≤ {VIDEO_EMBED_LIMIT_MB} MB)',
                                        'value': 'embed'}], style={'marginTop': '8px'}),

                html.H4("2 · Video (optional)", style={'marginTop': '16px'}),
                html.Div(f"{os.path.basename(vid)} — " + ("available" if has_video else "not rendered yet"),
                         className='lf-path'),
                html.P(f"Rendering from here {settings_txt}.", className='lf-muted'),
                html.Button("RENDER / UPDATE VIDEO", id='btn-export-render', n_clicks=0,
                            className='lf-btn lf-btn-warn'),
                dcc.Store(id='export-render-job'),
                html.Button("CANCEL", id='btn-export-render-cancel', n_clicks=0, disabled=True,
                            className='lf-btn lf-btn-ghost', style={'marginLeft': '8px'}),
                dcc.Interval(id='export-render-poll', interval=1000, disabled=True),
                html.Div(id='export-render-status'),

                html.H4("3 · Generate", style={'marginTop': '16px'}),
                html.Div(report_path(folder, cfg), className='lf-path'),
                html.Br(),
                html.Button("GENERATE HTML REPORT", id="btn-export-report", n_clicks=0, className='lf-btn'),
                dcc.Loading(html.Div(id='export-report-status', style={'marginTop': '12px'})),
            ], className='lf-card', style={'maxWidth': '760px'}),
        ]),
    ])


# ==========================================
# 4. CALLBACKS
# ==========================================
def register_callbacks(app):
    @app.callback(
        Output('export-report-status', 'children'),
        Input('btn-export-report', 'n_clicks'),
        [State('export-section-toggle', 'value'), State('export-week-day', 'value'),
         State('export-embed-video', 'value')],
        prevent_initial_call=True
    )
    def export_cb(n, selected_sections, week_day, embed):
        if not n:
            return ""
        if not selected_sections:
            return html.Div("Please select at least one section.", className='lf-msg lf-msg-warn')
        folder = get_active_folder()
        cfg = load_global_config()
        ok, msg = generate_report(report_path(folder, cfg), selected_sections, int(week_day or 3),
                                  embed_video='embed' in (embed or []))
        if ok:
            return html.Div([html.Div(msg, style={'wordBreak': 'break-all'}),
                             html.Div("Share the HTML file — it opens in any browser.", className='lf-muted')],
                            className='lf-msg lf-msg-ok')
        return html.Div(msg, className='lf-msg lf-msg-err')

    @app.callback(
        [Output('export-render-job', 'data'), Output('export-render-poll', 'disabled'),
         Output('export-render-status', 'children'), Output('btn-export-render', 'disabled'),
         Output('btn-export-render-cancel', 'disabled')],
        Input('btn-export-render', 'n_clicks'),
        prevent_initial_call=True
    )
    def export_render(n):
        if not n:
            return no_update, no_update, no_update, no_update, no_update
        folder = get_active_folder()
        cfg = load_global_config()
        st = video.load_settings(folder)
        if st:
            bounds, url, layers, speed = st.get('bounds'), st.get('basemap_url'), st.get('layers', []), st.get('speed', 5)
        else:
            layers = []
            if cfg.get('include_shapefile') and cfg.get('shapefile_path'):
                layers.append('SHP')
            if cfg.get('include_reference_radius'):
                layers.append('RAD')
            if cfg.get('include_reference_waypoint'):
                layers.append('WPT')
            bounds, url, speed = None, video.BASEMAPS['esri'], 5
        job_id, msg = video.start_job(folder, cfg, bounds, url, layers, speed)
        if not job_id:
            return None, True, html.Div(msg, className='lf-msg lf-msg-err'), False, True
        return job_id, False, html.Div(msg, className='lf-msg lf-msg-info'), True, False

    @app.callback(
        [Output('export-render-status', 'children', allow_duplicate=True),
         Output('export-render-poll', 'disabled', allow_duplicate=True),
         Output('btn-export-render', 'disabled', allow_duplicate=True),
         Output('btn-export-render-cancel', 'disabled', allow_duplicate=True),
         Output('export-section-toggle', 'options', allow_duplicate=True),
         Output('export-section-toggle', 'value', allow_duplicate=True)],
        Input('export-render-poll', 'n_intervals'),
        [State('export-render-job', 'data'), State('export-section-toggle', 'options'),
         State('export-section-toggle', 'value')],
        prevent_initial_call=True
    )
    def export_poll(_, job_id, options, values):
        status, poll_disabled, btn_disabled = anim_module.render_status_view(job_id)
        job = video.job_status(job_id) if job_id else None
        if job and job['status'] == 'done':
            options = [dict(o, disabled=False, label=" Propagation video") if o['value'] == 'video' else o
                       for o in options]
            values = sorted(set((values or []) + ['video']), key=['anomalies', 'mapper', 'speed', 'video'].index)
            return status, poll_disabled, btn_disabled, not btn_disabled, options, values
        return status, poll_disabled, btn_disabled, not btn_disabled, no_update, no_update

    @app.callback(
        Output('btn-export-render-cancel', 'disabled', allow_duplicate=True),
        Input('btn-export-render-cancel', 'n_clicks'),
        State('export-render-job', 'data'),
        prevent_initial_call=True
    )
    def export_cancel(n, job_id):
        if n and job_id:
            video.cancel_job(job_id)
        return True
