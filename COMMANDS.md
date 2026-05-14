# Cerberus 🛡️ - Full Command Reference

This document provides a comprehensive guide to all command-line arguments and configuration settings available in Cerberus.

---

## 🚀 Command-Line Arguments

### Core Inputs
- `-l, --link [URL]`: Download a single video or album.
- `-u, --urls [URL1,URL2]`: Download a comma-separated list of URLs. Supports naming: `URL:::Name`.
- `-r, --list [FILE]`: Download URLs from a text file. One URL per line. Supports naming: `URL:::Name`.

### Naming & Organization
- `-n, --name [NAME]`: 
    - `-n "My Video"`: Forces all downloads to use this name (albums will be indexed).
    - `-n` (flag only): **Interactive Mode**. Prompts for each video name upfront.
- `-p, --path [FOLDER]`: Specify a custom download folder for this run.

### Performance & Engine
- `-t, --threads [N]`: Number of parallel downloads (Default: 1).
- `-b, --limit-rate [RATE]`: Maximum speed (e.g., `500K`, `1M`, `5M`).
- `-f, --force`: Skip Selenium and force `yt-dlp` for all links.
- `-q, --quality [QUAL]`: Target quality (e.g., `best`, `720p`, `worst`).

### Configuration & Profiles
- `-P, --profile [NAME]`: Load settings from a specific profile `.txt` file.
- `--add-profile "[NAME]:key=val,..."`: Create or update a profile via CLI.
- `--del-profile [NAME]`: Delete a profile.
- `--setup`: Run the interactive first-time configuration wizard.
- `--config`: Open the `Settings.txt` file in your default editor.
- `--list-config`: Display all current settings in the terminal.
- `--example-config`: Generate a fully commented example configuration file.

### Advanced
- `-H, --hidden`: Hide all console output (useful for scripts).
- `--resume`: Continue an interrupted queue from `queue.json`.

---

## ⚙️ Configuration Settings (`Settings.txt`)

The following keys can be used in `Settings.txt` or in `Profiles/`:

| Key | Description | Default |
| :--- | :--- | :--- |
| `browser_path` | Full path to your browser (Chrome, Brave, Edge). | Auto-detected |
| `minimized` | Hide the browser window during Selenium extraction. | `false` |
| `default_quality` | Preferred video quality. | `best` |
| `overwrite_existing` | Replace existing files instead of skipping. | `false` |
| `sort_by` | Auto-sort into folders (`platform`, `artist`, `genre`, `none`). | `none` |
| `default_limit_rate` | Global bandwidth throttle (e.g., `1M`). | `none` |
| `post_download_command`| Shell command to run after download. | `none` |
| `use_browser_cookies` | Use your browser's cookies for logins/auth. | `false` |
| `selenium_wait_time` | Seconds to wait for page to load links. | `5` |
| `custom_hosts` | Comma-separated domains for direct `yt-dlp` use. | `none` |
| `proxy` | Proxy URL (e.g., `socks5://127.0.0.1:9050`). | `none` |
| `ignoreerrors` | Keep going even if a single download fails. | `false` |

---

## 📁 File Structure
- **Config Folder**: `~/.Cerberus` (Linux) or `%APPDATA%/.Cerberus` (Windows).
- **Settings**: `~/.Cerberus/Settings.txt`
- **Profiles**: `~/.Cerberus/Profiles/*.txt`
- **Logs**: `~/.Cerberus/Logs/`
- **Queue**: `~/.Cerberus/queue.json`
