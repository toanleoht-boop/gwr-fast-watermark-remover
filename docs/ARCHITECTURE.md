# Architecture

```text
PyQt6 UI (main.py)
  ├─ file/folder selection, preview, ROI drawing
  ├─ fixed-logo detector
  └─ WatermarkWorker (worker.py)
       ├─ Unicode-safe image decoding
       ├─ neighbouring patch selection + seamlessClone
       ├─ OpenCV video frame loop
       └─ FFmpeg mux: processed video + original audio
```

The watermark is assumed to be fixed in screen coordinates. For each frame, the worker picks a nearby patch whose boundary best matches the destination and blends it using Poisson cloning. This keeps the operation local and fast without a full-frame generative model.

## Extension points

- Add a tracked ROI for moving watermarks.
- Add a temporal clean-plate cache for difficult backgrounds.
- Add codec/profile options to release settings.
- Keep all new media operations local and document their privacy impact.
