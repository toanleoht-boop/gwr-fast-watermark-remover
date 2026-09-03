# Contributing

Thanks for helping improve GWR Fast Watermark Remover.

## Development setup

Use Python 3.11 or 3.12 on Windows and install `requirements-dev.txt`. Keep
changes small and focused. Do not commit personal media, generated output,
build folders, credentials, or model caches.

## Pull requests

1. Open an issue for substantial behavior changes.
2. Add or update tests for the changed behavior.
3. Run `python -m pytest -q --basetemp=.pytest-tmp`, `ruff check main.py worker.py tests`, and `ruff format --check main.py worker.py tests` locally.
4. Describe the media formats tested and any known limitations.

## Media and privacy

Use synthetic fixtures or media you have permission to share. Redact file paths, faces, and private metadata from issue reports.
