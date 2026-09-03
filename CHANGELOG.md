# Changelog

## Unreleased

- Removed the hidden legacy cut-video and audio-only tools; the public surface is
  now focused on image/video watermark removal.
- Added an in-memory before/after preview and a safe **Dừng** action for long
  batches.
- Fixed recursive folder loading so generated `Template` files are skipped,
  duplicate inputs are removed, and nested source folders are preserved.
- Hardened Unicode paths, atomic image writes, video container/audio muxing, and
  cancellation cleanup.

## 1.0.2 - 2026-09-03

- Fixed packaged startup failures caused by mismatched Qt DLL versions.
- Removed the redundant theme package and isolated the bundled Qt runtime.
- Added a real packaged-application startup test to CI and releases.

## 1.0.1

- Fast workflow polish and packaging reliability improvements after the initial
  public release.

## 1.0.0

- Initial open-source desktop release.
