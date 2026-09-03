"""Fast, local watermark removal worker for image and video batches.

The worker deliberately keeps the processing model small and deterministic:
the caller supplies one fixed ROI in percentages, then each frame is repaired
from the closest matching neighbouring texture. It does not upload media or
load a generative model.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover - exercised only in minimal installs
    imageio_ffmpeg = None


IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
VIDEO_EXTS = frozenset({".mp4", ".webm", ".mov", ".avi", ".mkv"})
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


class WatermarkWorker(QThread):
    """Process a batch without blocking the Qt UI thread."""

    finished = pyqtSignal(int, int)
    progress = pyqtSignal(int, int, str)
    error = pyqtSignal(str)

    def __init__(
        self,
        input_paths,
        output_dir=None,
        mode="smart",
        roi_params=None,
        source_root=None,
    ):
        super().__init__()
        self.input_paths = tuple(os.path.abspath(os.fspath(path)) for path in input_paths)
        self.output_dir = os.path.abspath(os.fspath(output_dir)) if output_dir else None
        self.source_root = os.path.abspath(os.fspath(source_root)) if source_root else None
        self.mode = mode  # Kept as a compatibility argument for older callers.
        self.roi_params = tuple(roi_params or (77.5, 86.8, 13.0, 8.5))
        self._cancelled = False
        self.was_cancelled = False

    def cancel(self):
        """Request a safe stop; a partially processed file is never published."""

        self._cancelled = True
        self.requestInterruption()

    def _stop_requested(self):
        return self._cancelled or self.isInterruptionRequested()

    def run(self):
        succeeded = 0
        failed = 0
        total = len(self.input_paths)

        for index, source in enumerate(self.input_paths, 1):
            if self._stop_requested():
                break
            try:
                output = self._output_path(source)
                if os.path.normcase(os.path.abspath(output)) == os.path.normcase(os.path.abspath(source)):
                    raise ValueError("Thư mục đầu ra không được trùng thư mục nguồn.")

                self.progress.emit(index - 1, total, f"Đang xử lý {os.path.basename(source)}")
                extension = Path(source).suffix.lower()
                if extension in VIDEO_EXTS:
                    self._video(source, output, index - 1, total)
                elif extension in IMAGE_EXTS:
                    self._image(source, output)
                else:
                    raise ValueError("Định dạng không được hỗ trợ.")
                succeeded += 1
            except Exception as exc:  # A single bad file must not abort a batch.
                failed += 1
                self.error.emit(f"{os.path.basename(source)}: {exc}")

        self.was_cancelled = self._stop_requested()
        status = "Đã dừng theo yêu cầu" if self.was_cancelled else "Hoàn tất"
        self.progress.emit(succeeded + failed, total, status)
        self.finished.emit(succeeded, failed)

    def _output_path(self, source):
        """Return a path, preserving selected subfolders under ``Template``."""

        source = os.path.abspath(source)
        source_dir = os.path.dirname(source)
        destination = self.output_dir or os.path.join(os.path.dirname(source_dir), "Template")

        if self.source_root:
            try:
                relative_parent = os.path.relpath(source_dir, self.source_root)
            except ValueError:  # Different Windows drives.
                relative_parent = "."
            outside_root = relative_parent == os.pardir or relative_parent.startswith(f"..{os.sep}")
            if relative_parent not in (".", "") and not outside_root:
                destination = os.path.join(destination, relative_parent)

        os.makedirs(destination, exist_ok=True)
        return os.path.join(destination, os.path.basename(source))

    @staticmethod
    def _roi(shape, values):
        height, width = shape[:2]
        x = max(0, min(int(float(values[0]) * width / 100), width - 1))
        y = max(0, min(int(float(values[1]) * height / 100), height - 1))
        roi_width = max(1, min(int(float(values[2]) * width / 100), width - x))
        roi_height = max(1, min(int(float(values[3]) * height / 100), height - y))
        return x, y, roi_width, roi_height

    @staticmethod
    def smart_remove(image, x, y, roi_width, roi_height):
        """Repair one ROI with a nearby texture and a feathered Poisson blend."""

        height, width = image.shape[:2]
        x = max(0, min(int(x), width - 1))
        y = max(0, min(int(y), height - 1))
        roi_width = max(1, min(int(roi_width), width - x))
        roi_height = max(1, min(int(roi_height), height - y))
        gap = max(4, min(roi_width, roi_height) // 10)
        options = [
            (sx, sy)
            for sx, sy in (
                (x - roi_width - gap, y),
                (x + roi_width + gap, y),
                (x, y - roi_height - gap),
                (x, y + roi_height + gap),
            )
            if sx >= 0 and sy >= 0 and sx + roi_width <= width and sy + roi_height <= height
        ]

        if not options:
            mask = np.zeros((height, width), np.uint8)
            mask[y : y + roi_height, x : x + roi_width] = 255
            return cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)

        border = max(2, min(6, min(roi_width, roi_height) // 6))
        target = image[y : y + roi_height, x : x + roi_width].astype(np.float32)
        edge = np.zeros((roi_height, roi_width), bool)
        edge[:border] = edge[-border:] = True
        edge[:, :border] = edge[:, -border:] = True

        def edge_error(position):
            sx, sy = position
            candidate = image[sy : sy + roi_height, sx : sx + roi_width].astype(np.float32)
            return float(np.mean((candidate[edge] - target[edge]) ** 2))

        sx, sy = min(options, key=edge_error)
        source = image[sy : sy + roi_height, sx : sx + roi_width].copy()
        mask = np.full((roi_height, roi_width), 255, np.uint8)
        feather = max(3, min(10, min(roi_width, roi_height) // 8))
        ramp = np.linspace(0, 255, feather, dtype=np.uint8)
        mask[:feather] = np.minimum(mask[:feather], ramp[:, None])
        mask[-feather:] = np.minimum(mask[-feather:], ramp[::-1, None])
        mask[:, :feather] = np.minimum(mask[:, :feather], ramp[None, :])
        mask[:, -feather:] = np.minimum(mask[:, -feather:], ramp[None, ::-1])

        try:
            return cv2.seamlessClone(
                source,
                image,
                mask,
                (x + roi_width // 2, y + roi_height // 2),
                cv2.NORMAL_CLONE,
            )
        except cv2.error:
            full_mask = np.zeros((height, width), np.uint8)
            full_mask[y : y + roi_height, x : x + roi_width] = 255
            return cv2.inpaint(image, full_mask, 3, cv2.INPAINT_TELEA)

    def _image(self, source, output):
        image = cv2.imdecode(np.fromfile(source, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Không đọc được ảnh.")
        result = self.smart_remove(image, *self._roi(image.shape, self.roi_params))
        extension = Path(output).suffix.lower() or ".png"
        ok, data = cv2.imencode(extension, result)
        if not ok:
            raise ValueError("Không ghi được ảnh đầu ra.")
        output_path = Path(output)
        temporary_output = str(output_path.with_name(f"{output_path.stem}.gwr-partial{output_path.suffix}"))
        try:
            data.tofile(temporary_output)
            os.replace(temporary_output, output)
        finally:
            try:
                os.remove(temporary_output)
            except OSError:
                pass

    def _video(self, source, output, file_index, total):
        temp_dir = tempfile.mkdtemp(prefix="gwr_")
        capture = writer = None
        try:
            local = os.path.join(temp_dir, "input" + (Path(source).suffix or ".mp4"))
            raw = os.path.join(temp_dir, "video.mp4")
            shutil.copy2(source, local)
            capture = cv2.VideoCapture(local)
            if not capture.isOpened():
                raise ValueError("Không mở được video.")

            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if not np.isfinite(fps) or fps <= 0:
                fps = 30.0
            frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
            writer = cv2.VideoWriter(raw, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
            if not writer.isOpened():
                raise ValueError("Không tạo được video đầu ra.")

            roi = self._roi((height, width), self.roi_params)
            done = 0
            while not self._stop_requested():
                ok, frame = capture.read()
                if not ok:
                    break
                writer.write(self.smart_remove(frame, *roi))
                done += 1
                if done % 12 == 0:
                    percent = min(100, int(done * 100 / frame_count))
                    self.progress.emit(file_index, total, f"{os.path.basename(source)} · {percent}%")

            capture.release()
            capture = None
            writer.release()
            writer = None
            if not self._stop_requested():
                self._mux(raw, local, output)
        finally:
            if capture is not None:
                capture.release()
            if writer is not None:
                writer.release()
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _run_ffmpeg(command):
        kwargs = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "check": False,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(command, **kwargs)

    @classmethod
    def _mux(cls, video, original, output):
        """Mux original audio while choosing a compatible target container."""

        extension = Path(output).suffix.lower()
        output_path = Path(output)
        temporary_output = str(output_path.with_name(f"{output_path.stem}.gwr-partial{output_path.suffix}"))
        if imageio_ffmpeg is None:
            if extension not in {".mp4", ".mov", ".mkv", ".avi"}:
                raise ValueError("Không tìm thấy FFmpeg để tạo định dạng video này.")
            try:
                shutil.copy2(video, temporary_output)
                os.replace(temporary_output, output)
            finally:
                try:
                    os.remove(temporary_output)
                except OSError:
                    pass
            return

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        command = [
            ffmpeg,
            "-y",
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            video,
            "-i",
            original,
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
            "-map_metadata",
            "1",
        ]
        if extension == ".webm":
            command += [
                "-c:v",
                "libvpx-vp9",
                "-deadline",
                "realtime",
                "-cpu-used",
                "8",
                "-crf",
                "32",
                "-b:v",
                "0",
                "-c:a",
                "libopus",
                "-b:a",
                "128k",
            ]
        elif extension == ".avi":
            command += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-c:v", "copy", "-c:a", "copy"]
        if extension in {".mp4", ".mov"}:
            command += ["-movflags", "+faststart"]
        command += ["-shortest", temporary_output]

        result = cls._run_ffmpeg(command)
        if result.returncode and extension not in {".webm", ".avi"}:
            # Some source tracks (for example Opus in an MP4) cannot be copied
            # into the requested container. Keep the processed video and only
            # transcode audio as a safe fallback.
            fallback = command.copy()
            try:
                audio_index = fallback.index("-c:a")
                fallback[audio_index : audio_index + 2] = ["-c:a", "aac"]
            except ValueError:
                pass
            result = cls._run_ffmpeg(fallback)
        if result.returncode or not os.path.exists(temporary_output):
            try:
                os.remove(temporary_output)
            except OSError:
                pass
            detail = (result.stderr or "").strip()[-300:]
            raise ValueError("FFmpeg: " + (detail or "không tạo được file đầu ra"))
        try:
            os.replace(temporary_output, output)
        finally:
            try:
                os.remove(temporary_output)
            except OSError:
                pass
