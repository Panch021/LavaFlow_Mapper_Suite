# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- LavaFlow Mapper: **📍 Add waypoints** control on the map. Clicking captures coordinates in decimal
  degrees, which can be named and saved as project waypoints (**SAVE AS PROJECT WAYPOINTS**), so they
  are also drawn in the propagation, the video and the report. While capturing, map layers do not
  intercept the click, so points can be captured on top of the anomalies.
- `common.update_config_values()` updates individual configuration keys without rewriting the rest
  of the file.

### Changed
- LavaFlow Propagation: the map now opens fitted to the filtered anomalies (same extent as the
  LavaFlow Mapper) instead of a fixed zoom level around the vent.

### Fixed
- LavaFlow Propagation: permanent waypoint labels no longer blink during playback. The basemap,
  shapefile, radius and waypoints are now drawn by their own callbacks instead of being rebuilt on
  every animation step.

## [2.1.0] - 2026-09-17

### Added
- Installable package `lavaflow_suite` (`pyproject.toml`) with the `lavaflow-suite` command
  (`--workdir`, `--port`, `--host`, `--no-browser`, `--debug`, `--version`).
- Offline pytest suite (73 tests) and GitHub Actions CI on Linux, macOS and Windows
  (Python 3.10–3.12), plus lint, documentation and JOSS-paper builds.
- MkDocs documentation (installation, quick start, user guide, configuration, outputs,
  methodology, troubleshooting, architecture, testing).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, issue and pull-request templates,
  release workflow.
- LavaFlow Propagation: **RENDER MP4** (portrait video with map, date bar and FRP/distance
  series) with **CANCEL RENDER**; the Export Report can embed the video.
- 12-hour animation steps with real overpass times for periods of two weeks or less.
- LavaFlow Mapper and Propagation Speed: mean/P95/max and speed statistics that follow the
  plot zoom; radius show/hide button.
- Anomalies Count: total labels on every bar; daily + weekly panels and a matching period
  summary for periods shorter than two months.
- Shapefiles are read even when the PROJ database is broken (WGS84 and WGS84/UTM).
- OpenTopoMap is the default basemap, with automatic fallback to Esri and OpenStreetMap.

### Changed
- Code moved from top-level scripts into the `lavaflow_suite` package. The old launcher
  `lavaflow_mapper_suite.py` still works.
- The GVP volcano list is shipped inside the package.
- New projects start with radius, shapefile and waypoints disabled and the map centred on the
  vent. Waypoints at 0,0 are ignored.
- The report uses the same figure builders as the app, and its map zooms to all anomalies.
- Responsive interface for desktop and mobile screens.

### Fixed
- Period summary totals now match the Anomalies Count chart.
- Blank (white) basemap in videos and reports (tile extent computed from tile size).
- Numeric (1.7e18) date axis in distance plots.
- Artificial zero speeds when several satellites detected the flow on the same day.

## [2.0.0] - 2026-06-10

### Added
- Dash multi-tab application: Global Config, FIRMS Download, Anomalies Count, FRP
  Statistics, LavaFlow Mapper, LavaFlow Propagation, Propagation Speed, Export Report.
- Example projects (Fernandina 2024, Wolf 2022, Sierra Negra 2018).
- Pixi and Conda environments.

## [1.0.0] - 2022-07-22

- Original R implementation accompanying Vasconez et al. (2022),
  <https://doi.org/10.3390/rs14143483>.

[Unreleased]: https://github.com/Panch021/LavaFlow_Mapper_Suite/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/Panch021/LavaFlow_Mapper_Suite/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/Panch021/LavaFlow_Mapper_Suite/releases/tag/v2.0.0
