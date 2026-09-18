# Troubleshooting

## `PROJ: proj_create_from_database: ... no database context specified`

This comes from a broken or mixed PROJ installation (common when pip and conda packages
are mixed). The suite detects it: shapefiles in WGS84 or WGS84/UTM are then read with a
built-in reader, and the map still works. To repair PROJ:

```bash
conda install -c conda-forge --force-reinstall proj pyproj
```

## The map or the video has a grey/white background

The basemap tiles could not be downloaded (no internet, firewall or proxy). The app
switches automatically from OpenTopoMap to Esri and then to OpenStreetMap. The video shows
a note when no provider was reachable.

## "Valid NASA FIRMS API Key is required"

Enter your MAP_KEY in **1. Global Config** and press **SAVE ALL PARAMETERS**.

## Nothing appears in Propagation / Speed / Report

Run **5. LavaFlow Mapper** (**RUN MAPPER ENGINE**) first; it writes the filtered files these tabs use.

## The video is not created

The MP4 encoder comes from `imageio-ffmpeg`. Reinstall it with
`python -m pip install imageio-ffmpeg`, or install a system `ffmpeg`.

## Still stuck?

Open an issue: <https://github.com/Panch021/LavaFlow_Mapper_Suite/issues>
(see [Support](contributing.md#getting-help)).
