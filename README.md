# 🌋 LavaFlow Mapper Suite

An integrated Python suite for monitoring volcanic thermal anomalies and lava flow propagation using NASA FIRMS data.

## 🛠️ Installation Guide

We use **Pixi** to manage the environment. It automatically handles Python, complex geospatial dependencies (GIS), and all required libraries for Windows, macOS, and Linux.

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
cd LavaFlow_Mapper_Suite
```

### 3. Run the Dashboard
Since the project includes a pixi.toml file, you don't need to install dependencies manually. Just run this command and Pixi will set up everything and launch the app:

```bash
pixi run start
```
