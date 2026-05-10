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
- **Rich TUI Dashboard**: Modern, parallel progress tracking with speed, ETA, and styled status updates (powered by `rich`).
- **Library Mode**: Import Cerberus into your own Python projects as a module for programmatic downloading.
- **Persistent Resume**: Interrupted sessions can be picked up exactly where they left off with `--resume`.
- **Download Profiles**: Save and load custom configurations (quality, path, rate-limit) via named profiles.
- **Automation Hooks**: Run custom post-download scripts automatically.
- **Automatic Sorting**: Organizes downloads into subfolders based on Platform, Artist, or Genre.

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

## 🔄 Updating Cerberus
To update your local installation to the latest version, run:
```bash
cd cerberus
git pull origin main
pip install .  # Ensure dependencies are up to date
```

## 📦 Downloading Specific Versions
You can find pre-compiled binaries and source code for all past releases on our [Releases Page](https://github.com/necrqum/cerberus/releases).
- **Windows**: Download `cerberus.exe`
- **Linux**: Download `cerberus-linux`

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
| `--resume` | Resumes the last interrupted download queue. |
| `-P / --profile` | Loads a specific download profile (e.g., `high-res`). |
| `--config` | Opens the settings file in your default editor. |
| `--list-config` | Prints all current settings to the terminal. |
| `--example-config` | Generates a template with all available options. |

## 📦 Library Mode (Experimental)
You can now use Cerberus's engine in your own scripts:
```python
from cerberus.downloader import download_video_from_page

download_video_from_page(
    url="https://...",
    save_folder="./downloads",
    settings_dict={'browser_path': '/usr/bin/chrome', 'minimized': 'true'}
)
```

## 🗺️ Roadmap
- [x] **v0.2.3**: Rich TUI, Profiles, Library Mode, and Hooks. (Released)
- [ ] **v0.3.0**: Queue Management GUI & Advanced Sorting.
- [ ] **v0.4.0**: Multi-Connection Chunks & Hardware Acceleration.
- [ ] **v1.0.0**: Stable Release & PyPI Distribution.

## 🤝 Contributing & Issues
Found a bug or have a feature request? We use GitHub Issues to track everything.
- **Report a Bug**: [Create Bug Report](https://github.com/necrqum/cerberus/issues/new?template=bug_report.md)
- **Request a Feature**: [Create Feature Request](https://github.com/necrqum/cerberus/issues/new?template=feature_request.md)

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
