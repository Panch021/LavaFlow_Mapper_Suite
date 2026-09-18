# Installation

The suite runs on Windows, macOS and Linux with Python ≥ 3.10.
Its geospatial dependencies (GDAL/PROJ through geopandas and pyproj) install most
reliably from **conda-forge**, so we recommend Pixi or Conda.

## Option 1 — Pixi (recommended)

Install Pixi:

=== "Windows (PowerShell)"

    ```powershell
    powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"
    ```

=== "macOS / Linux"

    ```bash
    curl -fsSL https://pixi.sh/install.sh | sh
    ```

Then clone the repository and start the application:

```bash
git clone https://github.com/Panch021/LavaFlow_Mapper_Suite.git
cd LavaFlow_Mapper_Suite
pixi run start
```

Pixi creates the environment the first time and opens the dashboard in your browser
(<http://127.0.0.1:9050>).

Other tasks:

```bash
pixi run -e test test        # run the test suite
pixi run -e docs docs        # serve this documentation locally
```

## Option 2 — Conda

```bash
git clone https://github.com/Panch021/LavaFlow_Mapper_Suite.git
cd LavaFlow_Mapper_Suite
conda env create -f environment.yml
conda activate lavaflow_mapper
lavaflow-suite
```

`environment.yml` installs the package in editable mode, which provides the
`lavaflow-suite` command. `python lavaflow_mapper_suite.py` still works as well.

## Option 3 — pip

```bash
python -m pip install "git+https://github.com/Panch021/LavaFlow_Mapper_Suite.git"
lavaflow-suite --workdir ~/lavaflow_projects
```

!!! warning
    With pip, geopandas/pyproj come from PyPI wheels. They work in most cases. If you see
    PROJ errors, see [Troubleshooting](troubleshooting.md).

## Command-line options

```text
lavaflow-suite [--workdir DIR] [--port 9050] [--host 127.0.0.1] [--no-browser] [--debug] [--version]
```

| Option | Meaning |
|---|---|
| `--workdir` | Folder that holds `projects/`, `examples/` and `active_volcano.txt` (default: current folder) |
| `--port`, `--host` | Where the Dash server listens |
| `--no-browser` | Do not open a browser tab automatically |
| `--debug` | Dash debug mode (developers) |

## NASA FIRMS MAP_KEY

Downloading data requires a free personal key:
<https://firms.modaps.eosdis.nasa.gov/api/map_key/>. Enter it in **1. Global Config**. It
is stored only in the project's configuration file.

!!! danger "Keep your key private"
    Do not commit configuration files that contain your MAP_KEY. The repository's
    `.gitignore` excludes `projects/`, but check `examples/` before pushing.
