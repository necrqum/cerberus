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