# Architecture

```text
LavaFlow_Mapper_Suite/
├── lavaflow_suite/            # the Python package
│   ├── cli.py                 # `lavaflow-suite` command (handles --workdir)
│   ├── app.py                 # Dash app, Global Config tab, tab routing
│   ├── common.py              # config, dates, waypoints, shapefiles, stats, animation steps
│   ├── firms_download.py      # 2. FIRMS API client and CSV merging
│   ├── anomalies.py           # 3. aggregation + figure + summary
│   ├── frp_statistics.py      # 4. cumulative FRP statistics
│   ├── mapper.py              # 5. filters, folium map, time series
│   ├── animation.py           # 6. dash-leaflet animation
│   ├── video.py               # 6. MP4 renderer (matplotlib + ffmpeg, background jobs)
│   ├── speed.py               # 7. advance rate
│   ├── report.py              # 8. HTML report
│   ├── assets/lavaflow.css    # responsive styles (served by Dash)
│   └── data/                  # GVP Holocene volcano list
├── tests/                     # pytest suite (offline)
├── docs/                      # this documentation (MkDocs)
├── examples/                  # read-only example projects
├── paper/                     # JOSS paper
└── lavaflow_mapper_suite.py   # backwards-compatible launcher
```

## Design rules

* **One builder per figure.** The app tabs and the HTML report call the same functions,
  e.g. `anomalies.build_counts_figure` and `mapper.build_timeseries_figure`, so the report
  always matches the app.
* **Shared helpers live in `common.py`**: active project, config parsing, date parsing,
  waypoints, shapefile reading and the animation time steps used by both the Propagation
  tab and the video.
* **Callbacks are registered by each module** through `register_callbacks(app)`, and
  `app.py` only assembles the layout.
* **Project data live in the working directory**, never inside the package.
