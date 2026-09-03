# GWR Fast Watermark Remover

[![CI](https://github.com/toanleoht-boop/gwr-fast-watermark-remover/actions/workflows/ci.yml/badge.svg)](https://github.com/toanleoht-boop/gwr-fast-watermark-remover/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/toanleoht-boop/gwr-fast-watermark-remover?display_name=tag)](https://github.com/toanleoht-boop/gwr-fast-watermark-remover/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A lightweight Windows desktop application for removing a **fixed, visible watermark** from images and videos you own or are authorized to edit.

The app is designed for practical batch work: select a set of files or a folder, detect or draw the logo region once, and export to a sibling folder named `Template`. Video audio is copied from the original file without re-encoding.

## What it does

- Drag-and-drop images, videos, or folders.
- Process many files in one run with a single ROI.
- Automatically detect the common Gemini-style fixed sparkle watermark, with manual ROI fallback.
- Reconstruct the covered area from the best neighbouring texture and blend the boundary to reduce rectangular blur.
- Preserve original AAC audio in videos through the bundled FFmpeg binary.
- Support Unicode filenames and Windows paths.
- Save results to `Template` by default, never to the source folder itself.

> Best results require a watermark that stays in the same screen position. Moving logos, large opaque objects, and content that is permanently hidden underneath require a tracking or generative-inpainting workflow and may need manual review.

## Quick start (Windows)

1. Download the latest `GWR-Fast-Watermark-Remover-windows.zip` from [Releases](https://github.com/toanleoht-boop/gwr-fast-watermark-remover/releases).
2. Extract the ZIP and run `GWR Fast Watermark Remover.exe`.
3. Choose files/folder, click **Tự động tìm Logo**, verify the red ROI, then click **Bắt đầu xóa watermark hàng loạt**.

The output folder is created beside the selected source folder:

```text
Photos\image.jpg       -> Template\image.jpg
Videos\clip.mp4        -> Template\clip.mp4
```

## Preview

![Synthetic before/after preview](docs/demo.svg)

This preview is synthetic so the repository does not publish anyone's private media. Use permission-cleared media when recording a real workflow GIF for a release.

## Run from source

```powershell
git clone https://github.com/toanleoht-boop/gwr-fast-watermark-remover.git
cd gwr-fast-watermark-remover
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

For development and tests:

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

## Build the portable Windows release

```powershell
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm GWR-Desktop.spec
```

The output is `dist/GWR-Fast-Watermark-Remover/`. To create the release ZIP:

```powershell
Compress-Archive -Path 'dist/GWR-Fast-Watermark-Remover/*' `
  -DestinationPath 'dist/GWR-Fast-Watermark-Remover-windows.zip' -Force
```

## Project layout

```text
main.py                 PyQt6 desktop UI and ROI/detection workflow
worker.py               Batch media worker and fast reconstruction engine
GWR-Desktop.spec        Reproducible PyInstaller configuration
tests/                  Unit tests for the reconstruction engine
docs/                   Architecture and contribution notes
.github/workflows/      Continuous integration
```

## Privacy and responsible use

Processing is local. The application does not upload media or call a cloud AI service. Only remove marks from media you own or have permission to modify; do not use it to misrepresent authorship or evade rights-management notices.

## Contributing

Bug reports and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), include a reproducible example without private media, and run the test suite before opening a pull request.

## License

Released under the [MIT License](LICENSE). FFmpeg and Python dependencies retain their own licenses.
