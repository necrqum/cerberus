# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Working on better YouTube extraction logic.
- Plan for automated unit tests.

### Fixed
- Open issue with `overwrite_existing=true` logic.

## [0.1.1] - 2026-26-01
### Added
- `default_download_dir` setting to allow configuring the default download folder when `use_cwd_as_default=false`.
- `get_default_download_dir(settings)` helper to centralize default-download-path resolution.
- Example settings (`example_settings.txt`) and `build_settings()` updated to surface `default_download_dir`.
- Plan for automated unit tests and CI integration --> view [README](README.md##Roadmap-Todo).

### Changed
- Unified progress reporting for direct/Selenium downloads: `download_media_url()` now reports progress via the existing `ytdlp_progress_hook` so that yt-dlp and direct downloads 


## [0.1.0] - 2025-12-12
### Added
- Initial release of Cerberus.
- Selenium-based network logging for video extraction.
- yt-dlp integration for fallback and HLS streams.
- Centralized configuration system (`%APPDATA%` on Windows, `~` on Linux).
- Automatic sorting by Platform, Artist, and Genre.
- CLI arguments for single, batch, and file-based downloads.
- Custom README with ASCII art and detailed instructions.

---
*Created by [necrqum](https://github.com/necrqum)*