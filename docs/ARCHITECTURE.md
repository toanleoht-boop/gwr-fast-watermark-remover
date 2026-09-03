# Architecture

```text
PyQt6 UI (main.py)
  ├─ file/folder selection + Template output policy
  ├─ first-frame preview, local before/after toggle, ROI drawing
  ├─ fixed-logo detector with manual fallback
  └─ WatermarkWorker (worker.py)
       ├─ Unicode-safe image decoding
       ├─ neighbouring patch selection + seamlessClone
       ├─ cancellable OpenCV video frame loop
       ├─ atomic image writes and temporary video workspace
       └─ FFmpeg mux: processed video + original audio
```

The watermark is assumed to be fixed in screen coordinates. For each frame, the worker picks a nearby patch whose boundary best matches the destination and blends it using Poisson cloning. This keeps the operation local and fast without a full-frame generative model. When a directory is selected, relative subfolders are reproduced below `Template`; an existing `Template` directory is excluded from recursive input discovery.

The UI and worker communicate only through Qt signals. A cancellation request
sets both a local flag and `QThread`'s interruption flag. The worker checks it
between frames and before muxing, so a partially processed video is never
published as the final output.

## Extension points

- Add a tracked ROI for moving watermarks.
- Add a temporal clean-plate cache for difficult backgrounds.
- Add codec/profile options to release settings.
- Keep all new media operations local and document their privacy impact.
