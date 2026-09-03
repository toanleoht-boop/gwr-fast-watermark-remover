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
    source = tmp_path / 'ảnh thử.png'
    output = tmp_path / 'kết quả.png'
    image = np.full((50, 70, 3), 90, dtype=np.uint8)
    ok, data = cv2.imencode('.png', image)
    assert ok
    data.tofile(str(source))
    worker = WatermarkWorker([], roi_params=(10, 10, 20, 20))
    worker._image(str(source), str(output))
    assert output.exists() and output.stat().st_size > 0
