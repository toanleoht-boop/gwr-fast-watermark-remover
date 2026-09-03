# GWR Fast Watermark Remover

Desktop tool for removing a fixed watermark from images and videos. It supports automatic Gemini-style watermark detection, manual ROI selection, batch processing, Unicode paths, and original audio preservation.

> Use this tool only on media you own or have permission to modify.

## Features

- Drag and drop images, videos, or folders
- Batch processing with one ROI
- Automatic fixed-logo detection
- Fast neighboring-texture reconstruction with seamless blending
- Original video audio preserved through FFmpeg
- Results saved to a sibling folder named `Template`

## Run from source

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Build for Windows

```powershell
pip install pyinstaller
pyinstaller --noconfirm GWR-Desktop.spec
```

The packaged application is created in `dist/GWR-Fast-Watermark-Remover`.

## Notes

Best results are obtained when the watermark is fixed on screen and the selected ROI is only slightly larger than the mark. Always review the red detection box before batch processing.

