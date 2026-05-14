# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [0.2.4] - 2026-05-14

### Added
- **"Naming First" Architecture**: Interactive naming now happens in a dedicated preparation phase before downloads start.
- **Advanced List Naming**: Added support for `URL:::Name` format in batch lists and files.
- **Improved Profile System**: Profiles are now stored as individual `.txt` files in a `Profiles/` folder.
- **CLI Profile Management**: Added `--add-profile` and `--del-profile` commands.
- **Force Exit**: Double `Ctrl+C` now forces an immediate shutdown.

### Fixed
- **Renaming Priority**: Fixed bug where original titles overrode custom `-n` names (The "Erome Bug").
- **TUI Stability**: Fixed `AttributeError` crash and interleaved output during parallel downloads.
- **Ctrl+C Resilience**: Restored abort functionality across all program phases.
- **Redundant Downloads**: Implemented automatic list deduplication and fixed loop-break logic.

### Changed
- **HUD HUD Cleanliness**: Completed tasks are now automatically removed from the terminal progress bars.
- **Keyword Argument Strengthening**: Refactored internal API to use keyword arguments for improved robustness.

## [0.2.3] - 2026-05-10
### Added
- **Library Mode (Programmatic API)**: Cerberus can now be imported as a Python module. Core functions now accept a `settings_dict` to bypass global configuration files.
- **Rich TUI Dashboard**: Completely redesigned the CLI interface using the `rich` library. Features parallel download tracking with professional progress bars, styled headers, and status panels.
- **Persistent Queue & Resume**: Implemented a state-persistence system (`queue.json`). Interrupted batch downloads can now be resumed using the new `--resume` flag.
- **Download Profiles**: Added support for named configuration profiles via `-P` / `--profile`. Users can now save multiple settings (e.g., quality, path, rate-limit) in `profiles.json`.
- **Post-processing Hooks**: Added `post_download_command` to settings. Allows executing custom shell commands automatically after each successful download (supports templates like `{file_path}`, `{filename}`, `{url}`).
- **Enhanced Setup Wizard**: Improved detection for existing configurations and added reset/abort options.

### Changed
- **Modular Refactoring**: Decoupled core download logic from CLI-specific path handling for library readiness.
- **UI Upgrade**: Replaced `tqdm` with `rich.progress` for a more modern and stable parallel UI.
- **Atomic Operations**: Improved file safety using `os.replace` for final assembly.

### Fixed
- **Bandwidth Limiting Consistency**: Fixed a bug where rate limits were not correctly applied in certain batch download scenarios.
- Improved error handling for system-level warnings on Linux terminals.

## [0.2.2] - 2026-04-02
### Added
- **Resume Support**: Downloads can now be resumed if interrupted (uses HTTP Range requests).
- **CI/CD Optimization**: Fixed GitHub Actions to correctly attach binaries to releases without warnings.

## [0.2.1] - 2026-04-02
### Added
- **Parallel Downloads**: New `-t` / `--threads` argument to download multiple videos simultaneously.
- **Thread-Safe UI**: Implemented thread-local progress bars with `tqdm`.

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