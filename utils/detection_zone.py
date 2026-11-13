"""Detection zone geometry (80% client, centered)."""
from typing import Tuple

from utils.constants import DETECTION_ZONE_SIZE_X, DETECTION_ZONE_SIZE_Y

BBox = Tuple[int, int, int, int]


def get_detection_zone(frame_w: int, frame_h: int) -> BBox:
    zw = max(64, int(frame_w * DETECTION_ZONE_SIZE_X))
    zh = max(64, int(frame_h * DETECTION_ZONE_SIZE_Y))
    x1 = max(0, (frame_w - zw) // 2)
    y1 = max(0, (frame_h - zh) // 2)
    return (x1, y1, min(zw, frame_w - x1), min(zh, frame_h - y1))
