# Quick start

This walkthrough uses the bundled **Fernandina 2024** example, so no API key is needed.

1. **Start the app**: `pixi run start` (or `lavaflow-suite`).
2. **1. Global Config**: pick *Fernandina* in the project selector. Example projects are
   read-only; the parameters (vent, period 01/03/2024–15/05/2024, FRP > 20 MW,
   track ≤ 0.5 km) are shown for reference.
3. **3. Anomalies Count**: look at the stacked detections per sensor. Periods shorter than
   two months show daily and weekly bars; longer periods show weekly and monthly bars. The
   *Period summary* uses the same numbers as the chart.
4. **5. LavaFlow Mapper**: press **RUN MAPPER ENGINE** to filter the detections. The map (OpenTopoMap by
   default) colours anomalies by date. Zoom the lower plots: mean, P95 and maximum FRP and
   distance are recomputed for the visible time window.
5. **6. LavaFlow Propagation**: play the animation or press **RENDER MP4** to save a
   portrait video `Fernandina_20240301_20240515_propagation.mp4` in the project folder.
6. **7. Propagation Speed**: press **CALCULATE SPEED** to see the maximum runout and the advance rate.
7. **8. Export Report**: choose the sections and press **GENERATE HTML REPORT** to write a self-contained HTML report you can
   e-mail or publish.

## Your own volcano

1. In **1. Global Config** search the GVP catalogue, choose a volcano.
   A new folder `projects/<Volcano>/` is created. Radius, shapefile and waypoints are off
   by default, and the map is centred on the vent.
2. Enter the analysis period, filters and your FIRMS MAP_KEY and press **SAVE ALL PARAMETERS**.
3. In **2. FIRMS Download** choose the dates and search radius and press **START DOWNLOAD**.
   Requests longer than five days are split automatically, and data already on disk is
   merged without duplicates.
4. Continue with tabs 3–8 as above.
