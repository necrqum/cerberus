# Cerberus 🛡️
> A robust, modular CLI tool for fetching and downloading videos from across the "underworld" of the internet.

[![GitHub Release](https://img.shields.io/github/v/release/necrqum/cerberus?include_prereleases)](https://github.com/necrqum/cerberus/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey)](#)

---

**Cerberus** combines the power of [**Selenium**](https://github.com/SeleniumHQ/Selenium) network interception and [**yt-dlp**](https://github.com/yt-dlp/yt-dlp) to extract media even from websites that don't provide direct download links.

## 🚀 Key Features
- **Dual-Engine Extraction**: Seamlessly switches between `yt-dlp` for known hosts and a Selenium-based network logger for everything else.
- **Interactive Setup**: Get started in seconds with a guided setup wizard.
- **Professional Progress UI**: Clean, `tqdm`-powered progress bars with speed and ETA.
- **Automatic Sorting**: Organizes downloads into subfolders based on Platform, Artist, or Genre.
- **FFmpeg Integration**: Robust handling of HLS streams and video conversions.

## 📦 Installation

### Prerequisites
- **Python 3.8+**
- **FFmpeg** (Required for merging video/audio)
- **Browser**: Chrome, Chromium, Brave, or Edge.

### Quick Start
```bash
# 1. Clone the repository
git clone https://github.com/necrqum/cerberus.git
cd cerberus

# 2. Setup environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install Cerberus
pip install .

# 4. Run Guided Setup
cerberus --setup
```

## 🛠️ Usage Examples

### Single Video Download
```bash
cerberus -l "https://example.com/video-page"
```

### Batch Download (Comma-separated)
```bash
cerberus -u "https://site1.com/vid1,https://site2.com/vid2"
```

### Download from List File
```bash
cerberus -r urls.txt
```

### Force yt-dlp Engine
```bash
cerberus -l "https://youtube.com/watch?v=..." -f
```

## ⚙️ Configuration
Cerberus uses a centralized configuration located at `~/.Cerberus` (Linux/Mac) or `%APPDATA%/.Cerberus` (Windows).

| Argument | Description |
| :--- | :--- |
| `--setup` | Runs the interactive setup wizard. |
| `--config` | Opens the settings file in your default editor. |
| `--list-config` | Prints all current settings to the terminal. |
| `--example-config` | Generates a template with all available options. |

## 🏗️ Project Structure
- `cerberus/main.py`: CLI Entry point.
- `cerberus/config.py`: Configuration & Setup Wizard.
- `cerberus/downloader.py`: Core download coordination.
- `cerberus/adapters/`: Download engines (`ytdlp.py`, `selenium.py`).
- `tests/`: Automated test suite.

## ⚖️ License & Legal
Distributed under the MIT License. See `LICENSE` for more information.

**Disclaimer**: This tool is for technical and educational purposes only. Users are responsible for complying with the terms of service of the websites they visit.

---
*Maintained by @Necrqum*
