# Configuration file

Every project folder contains `config_<Folder>.txt`, a plain `key=value` file that
**1. Global Config** writes for you.

| Key | Type | Example | Description |
|---|---|---|---|
| `volcano` | text | `Fernandina` | Display name |
| `lats_vent`, `longs_vent` | float | `-0.3893`, `-91.5166` | Vent coordinates (WGS84) |
| `start_day_str`, `end_day_str` | `DD/MM/YYYY HH:MM` | `01/03/2024 00:00` | Analysis period (UTC) |
| `filter_frp` | float | `20` | FRP threshold (MW) |
| `frp_filter_mode` | `gt` / `lt` | `gt` | Keep FRP ≥ (gt) or ≤ (lt) the threshold |
| `filter_track` | float | `0.5` | Maximum VIIRS along-track pixel size (km) |
| `map_key` | text | — | NASA FIRMS MAP_KEY (**private**) |
| `include_reference_radius` | bool | `False` | Draw the reference radius |
| `ref_radius_m` | float | `5000` | Radius in metres |
| `include_shapefile` | bool | `False` | Draw a shapefile |
| `shapefile_path` | text | `flow_2024.shp` | Path relative to the project folder, or absolute |
| `include_reference_waypoint` | bool | `False` | Draw waypoints |
| `wpt_names`, `wpt_lats`, `wpt_lons`, `wpt_symbols` | `;`-separated lists | `Station A;Station B` | Waypoints (`circle`, `triangle`, `square`) |

`active_volcano.txt` in the working directory stores the path of the selected project,
for example `projects/Sangay`.

Rendering choices of the Propagation tab (basemap, layers, speed) are saved in
`animation_settings.json`.
