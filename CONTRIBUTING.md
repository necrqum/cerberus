# Contributing to Cerberus

First off, thank you for considering contributing to Cerberus! It's people like you who make the open-source community such an amazing place to learn, inspire, and create.

Everything you need to know about contributing is right here.

## Code of Conduct
By participating in this project, you agree to abide by its terms. Be respectful, inclusive, and professional.

## How Can I Contribute?

### Reporting Bugs
* **Check the Issues:** Before opening a new issue, please search if it has already been reported.
* **Be Specific:** Include your OS, Python version, and a link to the website where the download failed.
* **Logs:** Attach the `converter.log` file from your config directory.

### Suggesting Enhancements
We are always looking for ways to make Cerberus better! Whether it's a new sorting algorithm or better error handling, feel free to open an issue with the tag `enhancement`.

### Pull Requests (PRs)
1. **Fork the Repo** and create your branch from `main`.
2. **Install Dev Dependencies**: 
   ```bash
   pip install -e .
3. **Keep it Clean**: Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines.
4. **Document Changes**: Update the README.md if you add new CLI arguments or settings.
5. **Submit PR**: Provide a clear description of what you changed and why.

## Current Focus Areas (Roadmap)
We are specifically looking for help with:
- **YouTube Support**: Fixing the extraction logic for YouTube links.
- **Unit Tests**: Adding tests for the metadata parsing logic in downloader.py.
- **Browser Support**: Expanding the browser_path logic to automatically detect common installations.