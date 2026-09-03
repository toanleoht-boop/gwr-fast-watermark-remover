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
- Corrected the PyQtDarkTheme dependency range so a clean install works from
  PyPI and Dependabot updates stay within compatible major versions.

## 1.0.1

- Fast workflow polish and packaging reliability improvements after the initial
  public release.

## 1.0.0

- Initial open-source desktop release.
