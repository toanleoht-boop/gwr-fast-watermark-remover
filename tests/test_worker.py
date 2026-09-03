import cv2
import numpy as np

from worker import WatermarkWorker


def test_roi_is_clamped_to_frame():
    assert WatermarkWorker._roi((100, 200, 3), (99, 99, 20, 20)) == (198, 99, 2, 1)


def test_smart_remove_changes_only_requested_area():
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    for y in range(image.shape[0]):
        image[y, :, :] = y
    original = image.copy()
    image[45:65, 70:95] = (255, 255, 255)
    result = WatermarkWorker.smart_remove(image, 70, 45, 25, 20)
    outside = np.ones(image.shape[:2], dtype=bool)
    outside[38:72, 63:102] = False
    assert np.max(np.abs(result[outside].astype(int) - original[outside].astype(int))) == 0
    assert np.mean(result[45:65, 70:95]) < 255


def test_unicode_image_round_trip(tmp_path):
    source = tmp_path / "ảnh thử.png"
    output = tmp_path / "kết quả.png"
    image = np.full((50, 70, 3), 90, dtype=np.uint8)
    ok, data = cv2.imencode(".png", image)
    assert ok
    data.tofile(str(source))
    worker = WatermarkWorker([], roi_params=(10, 10, 20, 20))
    worker._image(str(source), str(output))
    assert output.exists() and output.stat().st_size > 0


def test_output_path_preserves_nested_folder(tmp_path):
    source_root = tmp_path / "source"
    nested = source_root / "episode 01"
    nested.mkdir(parents=True)
    source = nested / "clip.mp4"
    output_root = tmp_path / "Template"

    worker = WatermarkWorker([], output_root, source_root=source_root)
    output = worker._output_path(str(source))

    assert output == str(output_root / "episode 01" / "clip.mp4")
    assert (output_root / "episode 01").is_dir()


def test_output_path_uses_template_sibling(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "photo.png"

    worker = WatermarkWorker([])
    output = worker._output_path(str(source))

    assert output == str(tmp_path / "Template" / "photo.png")


def test_output_path_does_not_escape_source_root(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    external_source = tmp_path / "outside" / "clip.mp4"
    external_source.parent.mkdir()

    worker = WatermarkWorker([], tmp_path / "Template", source_root=source_root)
    output = worker._output_path(str(external_source))

    assert output == str(tmp_path / "Template" / "clip.mp4")
