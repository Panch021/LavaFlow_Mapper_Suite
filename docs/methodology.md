# Methodology

The suite follows [Vasconez et al. (2022)](https://doi.org/10.3390/rs14143483), which was
developed for hotspot subaerial eruptions in the Galápagos Islands.

1. **Data**: VIIRS 375 m active-fire detections (SNPP, NOAA-20, NOAA-21) and MODIS 1 km
   detections from NASA FIRMS, in a box around the vent.
2. **Geolocation filter**: VIIRS pixels grow towards the swath edge. Keeping pixels with a
   small along-track size (`track`, default ≤ 0.5 km) removes most of the geolocation
   scatter.
3. **Radiative filter**: an FRP threshold removes weak detections that are unrelated to
   active lava (e.g. hot ground, fires, noise). The threshold depends on the volcano and can
   be inverted (≤) to study weak signals.
4. **Distance to the vent**: great-circle (haversine) distance for every filtered pixel.
   The daily maximum is taken as the position of the flow front.
5. **Advance rate**: when the daily maximum exceeds all previous maxima, the advance
   (m) is divided by the time since the previous advance (h). The first advance has no
   reference and gets no speed.
6. **Counts and FRP statistics**: all sensors (including MODIS) are used to describe the
   evolution of thermal activity.

!!! note "Limitations"
    Thermal detections mark *hot* pixels, not the full lava-flow outline. Cloud and
    plume cover, viewing geometry and saturation affect detection. Results are preliminary
    and should be validated with field or high-resolution data whenever possible.
