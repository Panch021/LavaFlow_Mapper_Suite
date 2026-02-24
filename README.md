# 🌋 LavaFlow Mapper Suite

An integrated Python suite for monitoring volcanic thermal anomalies and lava flow propagation using NASA FIRMS data.

## 🛠️ Installation Guide

We use **Pixi** to manage the environment. It automatically handles Python, complex geospatial dependencies (GIS), and all required libraries for Windows, macOS, and Linux.

### 1. Install Pixi
Open your terminal (macOS/Linux) or PowerShell (Windows) and paste the corresponding command:

**Windows (PowerShell):**
```powershell
iwr -useb [https://pixi.sh/install.ps1](https://pixi.sh/install.ps1) | iex
```
**macOS / Linux:**
```bash
curl -fsSL [https://pixi.sh/install.sh](https://pixi.sh/install.sh) | bash
```

### 2. Setup the Project
Clone this repository and enter the project folder:

```bash
git clone https://github.com/Panch021/LavaFlow_Mapper_Suite.git
cd LavaFlow_Mapper_Suite
```

### 3. Install Dependencies
Open your terminal/PowerShell inside the project folder and run this command. Pixi will read your requirements file and install everything automatically:

```bash
pixi add --pypi -r requirements.txt
```
### 4. Run the Dashboard
Once the dependencies are installed, you can launch the application with:

```bash
pixi run python main_dashboard.py
```
