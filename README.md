# 🌋 LavaFlow Mapper Suite

[![tests](https://github.com/Panch021/LavaFlow_Mapper_Suite/actions/workflows/tests.yml/badge.svg)](https://github.com/Panch021/LavaFlow_Mapper_Suite/actions/workflows/tests.yml)
[![docs](https://readthedocs.org/projects/lavaflow-mapper-suite/badge/?version=latest)](https://lavaflow-mapper-suite.readthedocs.io)
[![release](https://img.shields.io/github/v/release/Panch021/LavaFlow_Mapper_Suite)](https://github.com/Panch021/LavaFlow_Mapper_Suite/releases)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22832022.svg)](https://doi.org/10.5281/zenodo.22832022)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](pyproject.toml)

## Overview

`LavaFlow Mapper Suite` is an open-source Python application for the near-real-time mapping and monitoring of active lava flows using thermal satellite data from [NASA/FIRMS](https://firms.modaps.eosdis.nasa.gov/download/) (VIIRS and MODIS sensors). The software integrates data retrieval, processing, visualization, and reporting tools into a single graphical user interface (GUI), enabling users to rapidly assess lava flow propagation during volcanic eruptions.

Built upon the methodology of [Vasconez et al. (2022)](https://doi.org/10.3390/rs14143483), the suite automatically downloads thermal anomaly data, applies customizable filtering criteria, and generates interactive maps, time-series analyses, propagation animations, and lava flow velocity estimates. These products provide valuable information on lava flow inundation, eruption chronology, active flow fields, propagation rates, and maximum runout distances.

The software is designed for volcano observatories, civil protection agencies, researchers, and hazard managers seeking a rapid and accessible tool for volcanic crisis response and hazard assessment.

### Main Features

* 🌋 Volcano selection from the Global Volcanism Program [(GVP)](https://volcano.si.edu/volcanolist_holocene.cfm) database
* 🛰️ Automated download of VIIRS and MODIS thermal anomaly data from NASA/FIRMS using a personal [API key](https://firms.modaps.eosdis.nasa.gov/api/map_key/)
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

`LavaFlow Mapper Suite` addresses this challenge by providing an integrated graphical interface that automates the retrieval, processing, visualization, and analysis of thermal anomaly data from NASA's Fire Information for Resource Management System [(FIRMS)](https://firms.modaps.eosdis.nasa.gov/). The software generates interactive lava flow maps, temporal analyses, propagation animations, velocity estimates, and shareable reports, allowing users to rapidly transform satellite observations into actionable information.

Originally developed to support volcanic crises in the Galápagos Islands and based on the methodology of [Vasconez et al. (2022)](https://doi.org/10.3390/rs14143483), the software has proven applicable to volcanic systems worldwide. By reducing technical barriers and integrating multiple workflows into a single application, `LavaFlow Mapper Suite` makes advanced satellite-based lava flow monitoring accessible to volcano observatories, civil protection agencies, researchers, students, and hazard managers.

## Installation

Full instructions: **[documentation › Installation](https://lavaflow-mapper-suite.readthedocs.io/en/latest/installation/)**.

## 0. Git (required)

The commands below clone the repository, so Git must be available. Check with `git --version`;
if the command is not found, install it:

=== "Windows"

```powershell
    winget install --id Git.Git -e
```

    Alternatively download [Git for Windows](https://git-scm.com/download/win) and run the commands
    in *Git Bash*.

=== "macOS"

```bash
    xcode-select --install
```

    Or, with [Homebrew](https://brew.sh): `brew install git`.

=== "Linux"

```bash
    sudo apt update && sudo apt install git     # Debian / Ubuntu
    sudo dnf install git                        # Fedora / RHEL
    sudo pacman -S git                          # Arch
```

Close and reopen the terminal afterwards.

!!! tip "Without Git"
    You can also click **Code → Download ZIP** on the repository page and unzip it. Updates then have
    to be downloaded by hand, so Git is recommended.

### Pixi (recommended)

Install [Pixi](https://pixi.sh):

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"
```
**macOS / Linux:**
```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

Then:
```bash
git clone https://github.com/Panch021/LavaFlow_Mapper_Suite.git
cd LavaFlow_Mapper_Suite
pixi run start
```

### Conda
```bash
git clone https://github.com/Panch021/LavaFlow_Mapper_Suite.git
cd LavaFlow_Mapper_Suite
conda env create -f environment.yml
conda activate lavaflow_mapper
lavaflow-suite          # or: python lavaflow_mapper_suite.py
```

### pip
```bash
python -m pip install "git+https://github.com/Panch021/LavaFlow_Mapper_Suite.git"
lavaflow-suite --workdir ~/lavaflow_projects
```

The dashboard opens at <http://127.0.0.1:9050>. Run `lavaflow-suite --help` for the options.
Downloading new data requires a free [NASA FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key/).
The bundled example projects work without one.

## Usage

| Tab | What it does |
|---|---|
| 1. Global Config | Create/select a project (GVP catalogue), vent, period, filters, optional radius/shapefile/waypoints |
| 2. FIRMS Download | VIIRS (SNPP, NOAA-20, NOAA-21) and MODIS detections, merged without duplicates |
| 3. Anomalies Count | Daily/weekly (< 2 months) or weekly/monthly counts per sensor, with a matching period summary |
| 4. FRP Statistics | Cumulative FRP statistics every 12 h |
| 5. LavaFlow Mapper | Filtered anomaly map + FRP and distance series (mean/P95/max follow the zoom) |
| 6. LavaFlow Propagation | Animation (12-h steps for periods of up to two weeks) and portrait MP4 export |
| 7. Propagation Speed | Maximum runout and advance rate |
| 8. Export Report | Self-contained HTML report |

See the [quick start](https://lavaflow-mapper-suite.readthedocs.io/en/latest/quickstart/) and the
[user guide](https://lavaflow-mapper-suite.readthedocs.io/en/latest/user-guide/).

## Examples
* Comparison between thermal anomaly maps generated using all FIRMS thermal detections (left) and only those anomalies that satisfy the geolocation and Fire Radiative Power (FRP) filtering criteria implemented in LavaFlow Mapper Suite (right). The black polygon outlines the lava flow inundation area mapped by the Hawaiian Volcano Observatory for the 2018 Lower East Rift Zone (LERZ) eruption of Kīlauea [(Zoeller et al. 2020)](https://www.sciencebase.gov/catalog/item/5eba3f6082ce25b5135d5b85). The applied filters substantially reduce false detections and improve the spatial correspondence between satellite-derived thermal anomalies and the observed lava flow extent.
<img width="6210" height="2605" alt="Abstract_a-01" src="https://github.com/user-attachments/assets/ca5ad3e0-a525-496f-b130-3b05bb679ba1" />

* Animation of lava flow propagation during the March-May 2024 eruption of Fernandina volcano (Galápagos) derived from VIIRS thermal anomaly data. Thermal anomalies are displayed chronologically to illustrate the spatial and temporal development of the active lava field. The accompanying plots show the evolution of Fire Radiative Power (FRP) and the maximum distance reached by the lava flow relative to the eruptive vent through time.
[![Fernandina 2024 eruption - Video](https://github.com/user-attachments/assets/8113ca36-7fff-492d-87b6-f9558a7e7906)](https://github.com/user-attachments/assets/00ee9a6f-a2bc-4112-9838-29153161748a)

<p align="center"><i> Click on the image to play the video.</i></p>

## Research use

LavaFlow Mapper Suite is used at the Instituto Geofísico – Escuela Politécnica Nacional (IG-EPN, Ecuador)
for the monitoring of effusive eruptions. The methodology it implements has been applied in:

* Vasconez F.J. et al. (2022). *Remote Sensing* 14, 3483. <https://doi.org/10.3390/rs14143483>
* Hidalgo S. et al. (2024). *Bulletin of Volcanology* 86, 4. <https://doi.org/10.1007/s00445-023-01685-6>
* Coppola D. (2025). *Modern Volcano Monitoring*. <https://doi.org/10.1007/978-3-031-86841-2_11>
* Ramayanti S. (2025). *Jurnal Ilmiah Pendidikan Fisika Al-Biruni* 14, 1. <https://doi.org/10.24042/jipfalbiruni.v14i1.26753>
* Vasconez F.J. et al. (2026). *Bulletin of Volcanology* 88, 10. <https://doi.org/10.1007/s00445-026-02039-8>

Have you used the suite? Please [tell us](https://github.com/Panch021/LavaFlow_Mapper_Suite/issues/new?labels=use-case)
so we can list your work here.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest            # offline test suite
mkdocs serve                # documentation preview
```

The package lives in `lavaflow_suite/`, and its architecture is described in the
[documentation](https://lavaflow-mapper-suite.readthedocs.io/en/latest/architecture/).
Continuous integration runs the tests on Linux, macOS and Windows.

## Contributing and support

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md).
For questions or bugs, open an [issue](https://github.com/Panch021/LavaFlow_Mapper_Suite/issues). We aim to answer within two weeks.
Changes are listed in the [CHANGELOG](CHANGELOG.md).

## Citation

If you use LavaFlow Mapper Suite, please cite the software and the methodology paper (see also [CITATION.cff](CITATION.cff)):

* Vasconez F.J. (2026). LavaFlow Mapper Suite (v2.1.0). Zenodo. <https://doi.org/10.5281/zenodo.22832022>

* Vasconez F.J., Anzieta J.C., Müller A.V., Bernard B., Ramón P. (2022). A Near Real-Time and Free Tool for the
  Preliminary Mapping of Active Lava Flows during Volcanic Crises: The Case of Hotspot Subaerial Eruptions.
  *Remote Sensing*, 14(14), 3483. <https://doi.org/10.3390/rs14143483>

## License

GPL-3.0. See [LICENSE](LICENSE).

## Acknowledgements

The authors acknowledge the support of the Instituto Geofísico at Escuela Politécnica Nacional (Ecuador).
This work was inspired by the Galápagos eruptions that occurred in 2022 and 2024 and developed as part of the
monitoring efforts for active volcanism in Ecuador.
