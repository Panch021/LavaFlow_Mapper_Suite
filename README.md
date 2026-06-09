# 🌋 LavaFlow Mapper Suite

## Overview

`LavaFlow Mapper Suite` is an open-source Python application for the near-real-time mapping and monitoring of active lava flows using thermal satellite data from NASA FIRMS (VIIRS and MODIS). The software integrates data retrieval, processing, visualization, and reporting tools into a single graphical user interface (GUI), enabling users to rapidly assess lava flow propagation during volcanic eruptions.

Built upon the methodology of [Vasconez et al. (2022)](https://doi.org/10.3390/rs14143483), the suite automatically downloads thermal anomaly data, applies customizable filtering criteria, and generates interactive maps, time-series analyses, propagation animations, and lava flow velocity estimates. These products provide valuable information on lava flow inundation, eruption chronology, active flow fields, propagation rates, and maximum runout distances.

The software is designed for volcano observatories, civil protection agencies, researchers, and hazard managers seeking a rapid and accessible tool for volcanic crisis response and hazard assessment.

### Main Features

* 🌋 Volcano selection from the Global Volcanism Program (GVP) database
* 🛰️ Automated download of VIIRS and MODIS thermal anomaly data from NASA-FIRMS using an API key
* 📈 Weekly and monthly thermal anomaly statistics
* 🔥 Fire Radiative Power (FRP) threshold analysis
* 🗺️ Interactive mapping of active lava flows
* 🎬 Lava flow propagation animations
* ⚡ Lava flow velocity estimation
* 📄 Exportable HTML reports for sharing and decision-making

By automating the entire workflow within a single dashboard, `LavaFlow Mapper Suite` significantly reduces the time required to transform satellite observations into actionable information during effusive volcanic crises.

## Why LavaFlow Mapper Suite?

Rapid mapping of active lava flows is essential during volcanic crises to support hazard assessment, emergency response, and risk communication. However, obtaining timely information on lava flow extent and propagation can be challenging, especially at remote volcanoes where field observations, airborne surveys, or ground-based monitoring data may be limited or unavailable.

Satellite thermal observations have become a cornerstone of modern volcano monitoring, providing frequent, repeatable, and globally available measurements of volcanic activity. In particular, the VIIRS and MODIS sensors provide near-real-time thermal anomaly detections that can be used to track active lava flows. Despite the availability of these datasets, transforming raw thermal anomaly records into operational mapping products often requires expertise in remote sensing, GIS, and programming, creating a barrier for many users.

`LavaFlow Mapper Suite` addresses this challenge by providing an integrated graphical interface that automates the retrieval, processing, visualization, and analysis of thermal anomaly data from NASA's Fire Information for Resource Management System (FIRMS). The software generates interactive lava flow maps, temporal analyses, propagation animations, velocity estimates, and shareable reports, allowing users to rapidly transform satellite observations into actionable information.

Originally developed to support volcanic crises in the Galápagos Islands and based on the methodology of [Vasconez et al. (2022)](https://doi.org/10.3390/rs14143483), the software has proven applicable to volcanic systems worldwide. By reducing technical barriers and integrating multiple workflows into a single application, `LavaFlow Mapper Suite` makes advanced satellite-based lava flow monitoring accessible to volcano observatories, civil protection agencies, researchers, students, and hazard managers.


## Installation Guide

We use **Pixi** to manage the environment. It automatically handles Python, complex geospatial dependencies, and all required libraries for Windows, macOS, and Linux.

### 1. Install Pixi
Open your terminal (macOS/Linux) or PowerShell (Windows) and paste the corresponding command:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"
```
**macOS / Linux:**
```bash
curl -fsSL https://pixi.sh/install.sh | sh
```
Close and re-open PowerShell/terminal, then confirm:
```bash
pixi --version
```

### 2. Setup the Project
Clone this repository and enter the project folder:
```bash
git clone https://github.com/Panch021/LavaFlow_Mapper_Suite.git
```
```bash
cd LavaFlow_Mapper_Suite
```
### 3. Run the Dashboard
Since the project includes a pixi.toml file, you don't need to install dependencies manually. Just run this command and Pixi will set up everything and launch the app:

```bash
pixi run start
```

## Examples
* Comparison between thermal anomaly maps generated using all FIRMS thermal detections (left) and only those anomalies that satisfy the geolocation and Fire Radiative Power (FRP) filtering criteria implemented in LavaFlow Mapper Suite (right). The black polygon outlines the lava flow inundation area mapped by the Hawaiian Volcano Observatory (HVO) for the 2018 Lower East Rift Zone (LERZ) eruption of Kīlauea. The applied filters substantially reduce false detections and improve the spatial correspondence between satellite-derived thermal anomalies and the observed lava flow extent.
<img width="6210" height="2605" alt="Abstract_a-01" src="https://github.com/user-attachments/assets/ca5ad3e0-a525-496f-b130-3b05bb679ba1" />

* Animation of lava flow propagation during the March-May 2024 eruption of Fernandina Volcano (Galápagos) derived from VIIRS thermal anomaly data. Thermal anomalies are displayed chronologically to illustrate the spatial and temporal development of the active lava field. The accompanying plots show the evolution of Fire Radiative Power (FRP) and the maximum distance reached by the lava flow relative to the eruptive vent through time.
[![Fernandina 2024 eruption - Video](https://github.com/user-attachments/assets/8113ca36-7fff-492d-87b6-f9558a7e7906)](https://github.com/user-attachments/assets/cdcec3b3-9905-435c-8148-094ed53d3a59)


## Citations
If you find LavaFlow Mapper useful in your research, please consider citing the following paper to support my work. Thank you for your support.

* Vasconez FJ, Anzieta JC, Müller AV, Bernard B, Ramón P. (2022) A Near Real-Time and Free Tool for the Preliminary Mapping of Active Lava Flows during Volcanic Crises: The Case of Hotspot Subaerial Eruptions. Remote Sensing 23. https://doi.org/https://doi.org/10.3390/rs14143483


## Acknowledgements
The authors acknowledge the support of the Instituto Geofísico at Escuela Politécnica Nacional (Ecuador). This work was inspired by the Galápagos eruptions that occurred in 2022 and 2024 and developed as part of the monitoring efforts for active volcanism in Ecuador.
