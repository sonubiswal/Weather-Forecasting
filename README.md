<div align="center">

<img src="assets/banner.svg" width="100%" alt="Weather Forecasting"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-Qt-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Open-Meteo](https://img.shields.io/badge/Open--Meteo-No%20API%20Key-00A0E9?style=for-the-badge)](https://open-meteo.com/)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

![Platform](https://img.shields.io/badge/Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square&logo=windows-terminal&logoColor=white)
![Models](https://img.shields.io/badge/ensemble-4%20models-8b5cf6?style=flat-square)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)
![Made with love](https://img.shields.io/badge/made%20with-%E2%99%A5-ef4444?style=flat-square)

**A modern desktop weather app that asks four world-class models, shows you where they disagree, and grades its own accuracy.**

[✨ Features](#-features) &nbsp;•&nbsp;
[📸 Screenshots](#-screenshots) &nbsp;•&nbsp;
[🚀 Quick Start](#-quick-start) &nbsp;•&nbsp;
[🔬 How It Works](#-how-it-works) &nbsp;•&nbsp;
[🗺️ Roadmap](#%EF%B8%8F-roadmap)

<br/>

<img src="assets/screenshots/main.png?v=2" width="820" alt="Weather Forecasting main window"/>

</div>

<br/>

## 🌟 At a Glance

<table align="center">
  <tr>
    <td align="center" width="25%"><h3>4</h3><sub>weather models<br/>queried in parallel</sub></td>
    <td align="center" width="25%"><h3>24h + 5d</h3><sub>hourly strip and<br/>daily outlook</sub></td>
    <td align="center" width="25%"><h3>0</h3><sub>API keys<br/>required</sub></td>
    <td align="center" width="25%"><h3>MAE + Hit&nbsp;Rate</h3><sub>self-scored vs.<br/>persistence &amp; IFS</sub></td>
  </tr>
</table>

---

## 🎯 Why This Project

Most weather apps present one model's output as if it were certain. But models disagree, and that disagreement is useful information.

**Weather Forecasting** queries several independent models at once, reports the **median**, shows **how far apart they are**, and then checks itself against what actually happened, so you can see *how much to trust* a forecast, not just what it says.

> 💡 **Narrow spread = models agree. Wide spread = treat the forecast with caution.**

---

## ✨ Features

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>🧠 Ensemble Forecasts</h3>
      Queries <b>ECMWF IFS</b>, <b>ECMWF AIFS</b>, <b>GFS</b> and <b>ICON</b> in parallel and reports the median temperature with a confidence spread.
    </td>
    <td width="33%" valign="top">
      <h3>📈 Self-Scoring Accuracy</h3>
      Grades forecasts against observed conditions and benchmarks them against <b>persistence</b> and <b>IFS</b> baselines.
    </td>
    <td width="33%" valign="top">
      <h3>🚨 Severe Weather Alerts</h3>
      Automatic detection of <b>heat, cold, wind, rain</b> and <b>storm</b> conditions.
    </td>
  </tr>
  <tr>
    <td valign="top">
      <h3>📊 Location Scoring</h3>
      Ranks locations by <b>comfort</b>, <b>safety</b> and overall conditions.
    </td>
    <td valign="top">
      <h3>🌗 Sun &amp; Moon Arc</h3>
      Daylight curve with sunrise and sunset markers, plus the current moon phase.
    </td>
    <td valign="top">
      <h3>📅 Hourly &amp; 5-Day</h3>
      A 24-hour strip and 5-day outlook with precipitation probabilities.
    </td>
  </tr>
  <tr>
    <td valign="top">
      <h3>🎨 Adaptive Dark UI</h3>
      Card-based layout with dynamic colors and icons that follow conditions.
    </td>
    <td valign="top">
      <h3>🔍 Search &amp; Geolocation</h3>
      City search with geolocation calibration.
    </td>
    <td valign="top">
      <h3>🖥️ Headless CLI</h3>
      A quick terminal preview of the full ensemble, great for scripting.
    </td>
  </tr>
</table>

---

## 📸 Screenshots

<div align="center">

<table>
  <tr>
    <td align="center">
      <img src="assets/screenshots/forecast.png?v=2" width="560" alt="Hourly strip, 5-day outlook, and forecast accuracy"/>
      <br/><sub><b>⏱️ Hourly strip · 5-day outlook · Forecast accuracy</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="assets/screenshots/cli.png" width="560" alt="CLI ensemble forecast"/>
      <br/><sub><b>⌨️ CLI preview · Multi-model ensemble output</b></sub>
    </td>
  </tr>
</table>

</div>

---

## 🔬 How It Works

```mermaid
flowchart LR
    A["City search<br/>or geolocation"] --> B["fetcher.py"]
    B --> C1["ECMWF IFS"]
    B --> C2["ECMWF AIFS"]
    B --> C3["GFS"]
    B --> C4["ICON"]
    C1 --> D["Ensemble merge<br/>median + spread"]
    C2 --> D
    C3 --> D
    C4 --> D
    D --> E["alerts.py"]
    D --> F["scoring.py"]
    D --> G["ui.py + widgets.py"]
    E --> G
    F --> G

    style A fill:#1b5fa8,color:#fff
    style D fill:#8b5cf6,color:#fff
    style G fill:#22c55e,color:#fff
```

| Step | What happens |
|:---:|---|
| **1 · Fetch** | Open-Meteo is queried once per configured model, in parallel |
| **2 · Merge** | Responses are normalized; the **median** is reported and the **spread** becomes the confidence signal |
| **3 · Assess** | Alert rules flag hazards; scoring ranks comfort and safety |
| **4 · Grade** | Past forecasts are compared with observations using **MAE** and **hit rate**, against persistence and IFS baselines |

---

## 🚀 Quick Start

> **Requirements:** Python **3.10+** and an internet connection. No API key.

**1 · Clone**

```bash
git clone https://github.com/sonubiswal/Weather-Forecasting.git
cd Weather-Forecasting
```

**2 · Create a virtual environment**

<table>
<tr><th>🪟 Windows</th><th>🍎 macOS / 🐧 Linux</th></tr>
<tr>
<td>

```bash
python -m venv venv
venv\Scripts\activate
```

</td>
<td>

```bash
python3 -m venv venv
source venv/bin/activate
```

</td>
</tr>
</table>

**3 · Install**

```bash
pip install -r requirements.txt
```

**4 · Run**

<table>
<tr><th>🖥️ Desktop GUI</th><th>⌨️ CLI preview</th></tr>
<tr>
<td>

```bash
cd src
python -m weather_app.main
```

</td>
<td>

```bash
python preview.py
```

</td>
</tr>
</table>

<details>
<summary><b>📟 Sample CLI output</b></summary>

```
Puri, India  (19.798, 85.825)
  median temperature : 26.1 °C  (spread 2.1° across 4/4 models)
  feels like         : 31.6 °C
  humidity / wind    : 88% / 4.8 km/h
  condition          : Clear sky
  confidence         : Good confidence · 4 models within 2.1°
  hours / days       : 24 / 5
  models configured  : ecmwf_ifs025, ecmwf_aifs025_single, gfs_seamless, icon_seamless
```

</details>

---

## 🏗️ Architecture

```
Weather-Forecasting/
├── 🖼️  assets/
│   ├── banner.svg
│   └── screenshots/
├── 📦 src/weather_app/
│   ├── __init__.py     # Package metadata and version
│   ├── main.py         # Entry point (QApplication + event loop)
│   ├── fetcher.py      # Open-Meteo client, ensemble merge, normalization
│   ├── scoring.py      # Comfort / safety scoring, accuracy tracking
│   ├── alerts.py       # Severe weather detection rules
│   ├── theme.py        # Dynamic color, font, and icon selection
│   ├── widgets.py      # Reusable PySide6 components (cards, strips, arcs)
│   └── ui.py           # Main window layout and event wiring
├── preview.py          # Headless CLI preview
├── requirements.txt
├── pyproject.toml
└── .env.example
```

| Principle | In practice |
|---|---|
| **Separation of concerns** | Data (`fetcher`), logic (`scoring`, `alerts`) and presentation (`ui`, `widgets`, `theme`) are separate modules |
| **Reusable widgets** | UI building blocks are isolated in `widgets.py` |
| **Provider-agnostic data layer** | Normalization in `fetcher.py` keeps the rest of the app independent of the API's response shape |

---

## ⚙️ Configuration

Open-Meteo needs **no key**, so this is optional. To add a custom provider later:

<table>
<tr><th>🪟 Windows</th><th>🍎 macOS / 🐧 Linux</th></tr>
<tr>
<td>

```bash
copy .env.example .env
```

</td>
<td>

```bash
cp .env.example .env
```

</td>
</tr>
</table>

| Model ID | Provider |
|---|---|
| `ecmwf_ifs025` | 🇪🇺 ECMWF IFS |
| `ecmwf_aifs025_single` | 🤖 ECMWF AIFS |
| `gfs_seamless` | 🇺🇸 NOAA GFS |
| `icon_seamless` | 🇩🇪 DWD ICON |

---

## 🩺 Troubleshooting

<details>
<summary><b>❌ ModuleNotFoundError: No module named 'weather_app'</b></summary>

<br/>

Run from inside `src` using the module form:

```bash
cd src
python -m weather_app.main
```

</details>

<details>
<summary><b>🌐 The app opens but shows no data</b></summary>

<br/>

Check your internet connection and that Open-Meteo is reachable. The CLI line shows how many models responded (for example `4/4 models`).

</details>

<details>
<summary><b>📦 PySide6 fails to install or the window won't launch</b></summary>

<br/>

Use Python 3.10+ and upgrade pip first:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On some Linux distributions, Qt may need extra system libraries (for example `libxcb`-related packages).

</details>

<details>
<summary><b>🪟 venv won't activate in PowerShell</b></summary>

<br/>

Use Command Prompt, or allow scripts for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

</details>

---

## 🛠️ Tech Stack

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/PySide6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Requests](https://img.shields.io/badge/requests-HTTP-2c3e50?style=for-the-badge)
![Open-Meteo](https://img.shields.io/badge/Open--Meteo-00A0E9?style=for-the-badge)
![ECMWF](https://img.shields.io/badge/ECMWF-IFS%20%7C%20AIFS-003399?style=for-the-badge)
![GFS](https://img.shields.io/badge/NOAA-GFS-0b5fa5?style=for-the-badge)
![ICON](https://img.shields.io/badge/DWD-ICON-ef4444?style=for-the-badge)
![setuptools](https://img.shields.io/badge/setuptools-pyproject.toml-6b7280?style=for-the-badge)

</div>

---

## 🗺️ Roadmap

- [ ] 📉 Historical trend charts (30 / 90-day temperature and rainfall)
- [ ] ⭐ Saved locations and quick-switch favorites
- [ ] 🔔 System tray notifications for active alerts
- [ ] 🌓 Light / dark theme toggle
- [ ] 📦 Standalone executable (PyInstaller)
- [ ] 🏆 Expanded accuracy dashboard (per-model scoring breakdown)

Have an idea? [Open an issue](https://github.com/sonubiswal/Weather-Forecasting/issues) 💬

---

## 🤝 Contributing

Contributions, bug reports and feature requests are welcome.

1. 💬 **Open an issue** first to discuss any major change
2. 🍴 **Fork** the repo and create a branch: `git checkout -b feature/your-feature`
3. ✍️ **Commit** with clear, descriptive messages
4. 🚀 **Open a Pull Request** explaining what changed and why

Please keep changes focused, match the existing module structure, and include screenshots for UI changes.

---

## 🙏 Data Attribution

Weather data by **[Open-Meteo.com](https://open-meteo.com/)** under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Forecasts derive from models operated by ECMWF, NOAA (GFS) and DWD (ICON).

> ⚠️ **Disclaimer:** For informational use only. Do not rely on this app as your sole source for safety-critical decisions; consult official meteorological authorities during severe weather.

---

## 📄 License

Released under the **MIT License**. See [LICENSE](LICENSE).

## 👤 Author

**Sonu Biswal** · [@sonubiswal](https://github.com/sonubiswal)

<div align="center">

<br/>

### ⭐ If this project helped you, give it a star!

<sub>Built with Python, PySide6 and Open-Meteo</sub>

</div>