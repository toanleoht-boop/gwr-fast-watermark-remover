import cv2
import numpy as np

from main import MainWindow


def test_fixed_logo_detector_prefers_stable_corner_mark():
    frames = []
    for _ in range(4):
        frame = np.full((240, 320, 3), 80, dtype=np.uint8)
        cv2.circle(frame, (285, 215), 10, (255, 255, 255), -1)
        frames.append(frame)

    roi = MainWindow._detect_fixed_mark(frames)

    assert roi is not None
    x, y, width, height = roi
    assert x > 220 and y > 170
    assert width >= 20 and height >= 15
