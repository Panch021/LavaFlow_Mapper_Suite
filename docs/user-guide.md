# Workflow and tabs

```text
Global Config ─► FIRMS Download ─► Anomalies Count / FRP Statistics
                                 └► LavaFlow Mapper ─► Propagation ─► Speed ─► Export Report
```

The **LavaFlow Mapper** writes the filtered files that Propagation, Speed and the report
read. Run it again whenever you change filters or the period.

## 1. Global Config

* Choose an example or one of your projects, or create a new one from the GVP catalogue.
* **Vent** latitude/longitude: every distance is measured from this point.
* **Analysis period**, **FRP filter** (greater or lower than a threshold, in MW) and
  **track filter** (along-track pixel size in km; smaller values keep better-geolocated
  pixels).
* Optional reference layers:
    * **Reference radius** (m), drawn as a circle on maps and a line on distance plots;
    * **Shapefile** (e.g. an official lava-flow outline), in WGS84 or WGS84/UTM, or any CRS
      if PROJ works;
    * **Waypoints** (name, lat, lon, symbol). Empty or 0,0 rows are ignored.

## 2. FIRMS Download

Downloads `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` and `MODIS_NRT` inside
a square box around the vent. The panel shows your API transaction usage before and after
the request (limit: 5000 per 10 minutes). Dates are always stored as `YYYY-MM-DD`, and
older files are migrated automatically.

## 3. Anomalies Count

Stacked bars per sensor, with the total written above each bar.

| Period length | Upper panel | Lower panel | Summary tiles |
|---|---|---|---|
| < 2 months | daily | weekly | whole period, last day, last week, max per day, max per week |
| ≥ 2 months | weekly | monthly | whole period, last day, last week, last month, max per week, max per month |

The week start day is configurable. Weeks cut by the period limits are marked *partial*.

## 4. FRP Statistics

Cumulative mean, Q1, median and Q3 of FRP every 12 hours, per satellite.

## 5. LavaFlow Mapper

Applies the filters and draws:

* a folium map (OpenTopoMap by default, with Esri imagery and OSM as alternatives, and an
  automatic switch to Esri if OpenTopoMap cannot be reached), with anomalies coloured by
  date, the vent, and the enabled reference layers;
* FRP and distance-to-vent time series per satellite. The statistics panel (mean, P95,
  max) follows the zoom of the plot.

## 6. LavaFlow Propagation

Animated map with date slider, play/pause and speed control.

* Periods of **two weeks or less** advance in **12-hour** steps (VIIRS day and night
  passes), labelled with the actual overpass times.
* Longer periods advance daily (several days per frame for very long periods).

**RENDER MP4** writes a portrait (1080 × 1440) video in the project folder:
`<Volcano>_<start>_<end>_propagation.mp4`. It contains the map with the current view,
basemap, layers and speed, a date bar with automatic ticks, and the FRP and distance
series. Rendering runs in the background and can be cancelled with **CANCEL RENDER**.

## 7. Propagation Speed

For each day on which the flow front advanced, computes the new maximum distance and the
speed relative to the previous advance (m/h). Same-day detections from different
satellites are merged first. The reference radius can be shown or hidden. Maximum
distance, maximum speed and mean speed follow the zoom.

## 8. Export Report

Writes `<Volcano>_<start>_<end>_report.html`. It reuses exactly the figures of the app
(anomaly counts and summary, map and series with zoom-aware statistics, speed) and can
embed the MP4 (up to the size limit shown in the tab). The report works offline, apart
from basemap tiles and the Plotly library.
