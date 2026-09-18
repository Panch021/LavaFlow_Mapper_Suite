# Output files

All outputs are written inside the project folder.

| File | Written by | Content |
|---|---|---|
| `historical_VIIRS_SNPP_NRT_<name>.csv` (and NOAA20, NOAA21, MODIS) | FIRMS Download | Raw FIRMS detections, merged over successive downloads |
| `filter_VIIRS_combined.csv` | LavaFlow Mapper | Filtered VIIRS detections with `date` (UTC) and `distance_km` |
| `max_distance_per_day_VIIRS.csv` | LavaFlow Mapper | Farthest detection and maximum FRP per day and satellite |
| `LavaFlow_propagation.csv` | Propagation Speed | Days with front advance: `max_distance` (km), `speed` (m/h) |
| `<Volcano>_<start>_<end>_propagation.mp4` | LavaFlow Propagation | Portrait animation |
| `<Volcano>_<start>_<end>_report.html` | Export Report | Self-contained report |
| `.tile_cache/` | video renderer | Cached basemap tiles (safe to delete) |
