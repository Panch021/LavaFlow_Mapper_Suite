---
title: 'LavaFlow Mapper Suite: a collection of Python modules for monitoring lava flow propagation in near-real-time from space'
tags:
  - Python
  - Volcanology
  - Remote Sensing
  - Lava flows
  - Near-real-time monitoring
authors:
  - name: Francisco J. Vasconez
    orcid: 0000-0003-2000-1636
    affiliation: 1
affiliations:
  - name: Instituto Geofísico, Escuela Politécnica Nacional, Quito, Ecuador
    index: 1
date: 17 September 2026
bibliography: paper.bib
---

# Summary

LavaFlow Mapper Suite is an open-source Python package for the preliminary mapping and monitoring of active lava flows from satellite thermal observations. It implements and extends the methodology of @Vasconez2022a. Data acquisition, filtering, visualization, analysis and reporting are combined in a single graphical user interface (GUI). The software uses the thermal anomalies detected several times per day by the VIIRS and MODIS sensors. With them, users can rapidly map active lava, follow its advance, estimate maximum runout distances and propagation rates, animate the evolution of an eruption and produce standardized reports. These products support hazard assessment and emergency response by volcano observatories, civil-protection agencies and researchers during effusive eruptions.

# Statement of need

During effusive eruptions, the location, extent and advance of active lava flows must be known quickly to evaluate impacts on infrastructure, population and natural resources. Field observations are detailed but hazardous and often impossible at remote volcanoes. Airborne and UAS thermal surveys are very effective [@Dietterich2021; @Pedersen2022; @Hrysiewicz2025; @Zoeller2020], but they require equipment, trained staff and funding that many observatories lack.

Satellite thermal observations have therefore become a cornerstone of volcano monitoring [@Poland2015; @Coppola2025a]. Sentinel-2 MSI and Landsat OLI image a volcano every 5–7 days at 20–30 m resolution. In contrast, VIIRS (375 m) and MODIS (1 km), aboard Suomi-NPP, NOAA-20, NOAA-21, Aqua and Terra, observe it several times per day. Thermal anomaly data have been used to detect unrest [@Laiolo2017; @Girona2021; @Aveni2025], to follow eruptions, estimate effusion rates and volumes, and map lava flows [@Blackett2015; @Harris2017; @Marchese2019; @Naismith2019; @Bernard2019; @Walter2019; @Plank2019; @Genzano2020; @Coppola2020; @Coppola2022; @Coppola2025b; @Musacchio2021; @Vasconez2022b; @Vasconez2026]. However, turning these records into operational maps still requires expertise in remote sensing, programming and GIS.

LavaFlow Mapper Suite removes this barrier. It retrieves [FIRMS](https://firms.modaps.eosdis.nasa.gov/) detections for any volcano, applies user-defined thermal and geometric filters, and produces maps, time series, animations, velocity estimates and reports without any programming. The original method of @Vasconez2022a was released as an R tool on [GHub](https://theghub.org/resources/lavaflowmapper). This package re-implements it in Python, extends it, and packages it as a tested, documented application. It can be used for ongoing eruptions, with FIRMS near-real-time data available about three hours after acquisition, and for past events, with records from 2012 onwards.

# State of the field

[MODVOLC](http://modis.higp.hawaii.edu/) [@Wright2004] and [MIROVA](https://www.mirovaweb.it/NRT/) [@Coppola2016] provide global, automatic detection of volcanic thermal anomalies and radiative power, and they are fundamental monitoring tools. They deliver standardized products, however, rather than user-driven analyses. Users cannot choose their own filters or study areas, and the systems do not provide lava-flow maps, propagation distances or speeds, or reports tailored to a specific crisis. These analyses therefore usually require exporting data and processing them with GIS software or custom scripts. LavaFlow Mapper Suite complements these systems. It turns FIRMS detections into lava-flow mapping products through a reproducible workflow in which the study area, time window, filters and thresholds are chosen by the user. Its contribution is to bridge thermal-anomaly detection and operational lava-flow mapping in an open and accessible package.

# Software design

The design prioritizes operational simplicity, reproducibility and accessibility for users with diverse technical backgrounds. A key decision was to rely on FIRMS thermal anomalies instead of higher-resolution imagery. This trades spatial detail for the temporal frequency and latency needed for situational awareness during a crisis.

The core of the method is the spatial and thermal filtering of the detections. Raw VIIRS detections spread beyond the lava field because off-nadir pixels are large and because low-intensity anomalies are also detected. Retaining only pixels with a small along-track size and a Fire Radiative Power (FRP) above a user-defined threshold isolates the anomalies produced by active lava (\autoref{fig:filter}). For each day, the farthest filtered pixel from the vent is taken as the flow front. When the front advances, the advance is divided by the time since the previous advance to give the propagation rate.

![Thermal anomalies detected by VIIRS (Suomi-NPP and NOAA-20) during the 2018 lower East Rift Zone eruption of Kīlauea, coloured by date, before (left) and after (right) applying the track and FRP filters implemented in LavaFlow Mapper Suite. The black outline is the official lava-flow map of the eruption [@Zoeller2020; @Dietterich2021].\label{fig:filter}](Abstract_a-01.png){ width=100% }

The package (`lavaflow_suite`) is a Dash web application organized in eight modules, each providing its own layout and callbacks:

1. **Global Configuration**: project creation from the Global Volcanism Program catalogue, vent, period, filters and optional reference layers (radius, shapefile, waypoints).
2. **FIRMS Download**: chunked API requests for VIIRS and MODIS, merged into per-sensor archives without duplicates.
3. **Anomalies Count**: detections per sensor, as daily and weekly counts for periods shorter than two months and weekly and monthly counts otherwise, with a period summary computed from the same aggregation as the plots.
4. **FRP Statistics**: cumulative FRP distributions that help choose filtering thresholds.
5. **LavaFlow Mapper**: filtered anomaly maps and FRP and distance-to-vent series whose mean, 95th percentile and maximum follow the plot zoom.
6. **LavaFlow Propagation**: an animation with 12-hour steps for periods of up to two weeks and daily steps otherwise, and export to a portrait MP4 video.
7. **Propagation Speed**: maximum runout and advance rates.
8. **Export Report**: self-contained HTML reports built with the same figure functions as the application, so that reports and screen always agree.

Shared logic (project handling, configuration, date parsing, shapefile reading and animation time steps) lives in a common module. Shapefiles in geographic or UTM coordinates are read even when the PROJ database is unavailable, a frequent problem on institutional computers. The software runs on Windows, macOS and Linux. It installs with Pixi, Conda or pip and provides a `lavaflow-suite` command. An offline test suite runs on all three platforms through continuous integration. It uses a synthetic eruption and mocked FIRMS and tile services, and it also runs the bundled Galápagos example projects. Documentation is built with MkDocs.

# Research impact statement

The methodology implemented here was developed for, and applied to, eruptions in the Galápagos Islands and elsewhere [@Vasconez2022a; @Hidalgo2024; @Ramayanti2025; @Coppola2025a; @Vasconez2026]. These studies showed that thermal anomaly data can be turned into rapid assessments of lava-flow propagation and inundation. The software was developed within the operational monitoring of the Instituto Geofísico (Ecuador). There, automating data retrieval, filtering, visualization and reporting substantially reduces the time needed to prepare preliminary lava-flow maps and reports compared with manual GIS workflows. It relies exclusively on public satellite data and includes example projects (Fernandina 2024, Wolf 2022, Sierra Negra 2018). Its results can therefore be reproduced and verified independently, which lowers the barrier for observatories and agencies with limited remote-sensing resources.

# AI usage disclosure

Generative AI tools (Anthropic's Claude) were used to assist in translating code from the original R implementation to Python and in integrating the modules into a single interface. They were also used for refactoring, writing tests, packaging, continuous-integration and documentation files, and editing the English of this manuscript; the author is not a native English speaker. The scientific methodology, software design and all volcanological analyses were conceived by the author. All AI-assisted code and text were reviewed, modified, tested and validated by the author, who takes full responsibility for the software and the manuscript.

# Acknowledgements

The author acknowledges the support of the Instituto Geofísico – Escuela Politécnica Nacional (Ecuador). This work was inspired by the Galápagos eruptions of 2022 and 2024 and developed as part of the monitoring of active volcanism in Ecuador.

# References
