# Cerberus

<details>

<summary>etymology</summary>

  

The guardian fetches things from the 'underworld' of the internet.

› Read more about the [Ceberus](https://en.wikipedia.org/wiki/Cerberus).
  

</details>

**Cerberus** is a robust Command-Line Interface (CLI) tool designed to fetch and download videos from across the "underworld" of the internet. By combining the power of [**Selenium**](https://github.com/SeleniumHQ/Selenium) network logging and [**yt-dlp**](https://github.com/yt-dlp/yt-dlp), it can extract media even from websites that don't provide direct download links.

---
## Contents
1. [Key Features](#Key_Features)
2. [Installation](#Installation)
3. [Usage Examples](#Usage_Examples)
4. [Configuration](#Configuration)
5. [Project Structure](#Project_Structure)
6. [License & Legal](License_&_Legal)
7. [Roadmap / Todo](#Roadmap/Todo)
---
## Key Features
- **Dual-Engine Extraction**: Uses `yt-dlp` for known hosts and a Selenium-based network logger to intercept direct video URLs (`.mp4`, `.m3u8`, etc.) from any site.

- **Smart Session Numbering**: Automatically handles pages with multiple videos. It numbers them (e.g., `Video(1).mp4`) within a session to ensure no content is skipped.

- **Automatic Sorting**: Organizes your downloads into subfolders based on Platform, Artist, or Genre by parsing metadata and Open Graph tags.

- **Centralized Config**: Automatically creates a configuration directory in `%APPDATA%/.cerberus` (Windows) or `~/.cerberus` (Linux/Mac) to keep your workspace clean.

- **FFmpeg Integration**: Seamlessly handles HLS streams and video conversions using FFmpeg.
---
## Installation
1. **Clone the repository**:
```bash
  git clone https://github.com/yourusername/cerberus.git
  cd cerberus
```
2. **Install dependencies**:
```bash
  pip install .
```
*This will install all required packages: `selenium`, `yt-dlp`, `requests`, `browser-cookie3`, `beautifulsoup4`, and `tqdm`.*

3. **Initial Setup**: Run the config command to generate your `Settings.txt`:
```bash
  cerberus --config
```
*Make sure to set your `browser_path` to your local Chrome/Edge `.exe` in the settings file.*

---
## Usage Examples
Single Video Download
```bash
cerberus -l "https://example.com/video-page" -p "./my_downloads"
```
Batch Download (Comma-separated)
```bash
cerberus -u "https://site1.com/vid1,https://site2.com/vid2"
```
Download from List File
```bash
cerberus -r urls.txt
```
Force yt-dlp Engine
```bash
cerberus -l "https://youtube.com/watch?v=..." -f
```
---
## Configuration
You can manage your settings via the CLI or by editing `Settings.txt` directly.

| Argument | Description |
|     :---:      |     :---:      |
| `--config`     | git status |
| `--list-config` | git diff |
| `--example-config` | git diff |

Available Settings Highlights:
- `sort_by`: `artist`, `platform`, `genre`, or `none`.
- `overwrite_existing`: `true` or `false`.
- `default_quality`: Choose `best`, `worst`, or `specific` resolutions like `720p`.
- `use_browser_cookies`: Enable to use your browser's login session (useful for restricted sites).
---
## Project Structure
- `cerberus/downloader.py`: The core logic for extraction and downloading.

- `setup.py`: Package configuration for installation.

- `README.md`: Documentation.

- `Settings.txt`: User-specific configurations (generated on first run).
---
## License & Legal
Distributed under the MIT License.

**Disclaimer**: This tool is for technical and educational purposes only. Users are responsible for complying with the terms of service of the websites they visit and ensuring they have the right to download any content.
---
## Roadmap / Todo
- [ ] Fix overwrite_existing=true parameter logic

- [ ] Implement full unit testing suite

- [x] Centralize program files/config

- [x] Add automated metadata-based sorting

- [x] Improve error handling for failed Selenium instances
---
Created by [Necrqum](https://github.com/necrqum)
---