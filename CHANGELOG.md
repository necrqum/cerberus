# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [Unreleased]
### Added
- Plan for Binary distribution improvements.

## [0.2.1] - 2026-04-02
### Added
- **Parallel Downloads**: New `-t` / `--threads` argument to download multiple videos simultaneously using `ThreadPoolExecutor`.
- **Thread-Safe UI**: Implemented thread-local progress bars with `tqdm` to ensure clean terminal output during parallel processing.

## [0.2.0] - 2026-04-02
### Added
- **Interactive Setup Wizard**: Guided configuration via `--setup`.
- **Professional Progress UI**: Switched to `tqdm` for cleaner, more robust download bars.
- Improved browser auto-detection on Windows, Linux, and macOS.
- Unified progress reporting for all download methods.

### Changed
- Refined `main.py` to automatically trigger setup if configuration is missing.
- Updated documentation for a more professional look.

### Fixed
- SIGINT (Ctrl+C) handling for proper download interruption.
- progress bar flickering on some terminals.

## [0.1.1] - 2026-03-12
### Added
- `default_download_dir` setting to allow configuring the default download folder when `use_cwd_as_default=false`.
- `get_default_download_dir(settings)` helper to centralize default-download-path resolution.
- Example settings (`example_settings.txt`) and `build_settings()` updated to surface `default_download_dir`.

### Fixed
- `overwrite_existing=true` logic and unit tests.
- modular architecture refactoring completed.

## [0.1.0] - 2025-12-12
### Added
- Initial release of Cerberus.
- Selenium-based network logging for video extraction.
- yt-dlp integration for fallback and HLS streams.
...
- Centralized configuration system (`%APPDATA%` on Windows, `~` on Linux).
- Automatic sorting by Platform, Artist, and Genre.
- CLI arguments for single, batch, and file-based downloads.
- Custom README with ASCII art and detailed instructions.

---
*Created by [necrqum](https://github.com/necrqum)*