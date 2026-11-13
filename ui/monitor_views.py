"""Display helpers for the three live monitor panels (no detection processing)."""
from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt6.QtGui import QImage, QPixmap


def downscale_rgb_for_display(
    rgb: np.ndarray, max_w: int, max_h: int
) -> np.ndarray:
    if rgb is None or rgb.size == 0:
        return rgb
    if len(rgb.shape) == 2:
        rgb = cv2.cvtColor(rgb, cv2.COLOR_GRAY2RGB)
    elif rgb.shape[2] == 4:
        rgb = cv2.cvtColor(rgb, cv2.COLOR_BGRA2RGB)
    h, w = rgb.shape[:2]
    scale = min(max_w / max(w, 1), max_h / max(h, 1), 1.0)
    if scale >= 0.999:
        return np.ascontiguousarray(rgb)
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    return cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)


def numpy_to_pixmap(rgb: np.ndarray, max_w: int, max_h: int) -> QPixmap:
    if rgb is None or rgb.size == 0:
        return QPixmap()
    small = downscale_rgb_for_display(rgb, max_w, max_h)
    h, w = small.shape[:2]
    qimg = QImage(
        small.data.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888
    )
    return QPixmap.fromImage(qimg)


def draw_detection_zone(
    rgb: np.ndarray,
    zone: Optional[Tuple[int, int, int, int]],
) -> np.ndarray:
    out = rgb.copy()
    if zone is None:
        return out
    x, y, w, h = zone
    if w < 4 or h < 4:
        return out
    cv2.rectangle(out, (x, y), (x + w, y + h), (80, 200, 255), 2)
    cv2.putText(
        out,
        "Detection zone",
        (max(0, x + 4), max(12, y + 14)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (120, 210, 255),
        1,
        cv2.LINE_AA,
    )
    return out


def crop_raw_zone_rgb(
    frame_bgr: np.ndarray,
    zone: Tuple[int, int, int, int],
) -> Optional[np.ndarray]:
    """Unprocessed detection-zone crop (BGR → RGB)."""
    if frame_bgr is None or frame_bgr.size == 0:
        return None
    if len(frame_bgr.shape) == 2:
        bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_GRAY2BGR)
    elif frame_bgr.shape[2] == 4:
        bgr = cv2.cvtColor(frame_bgr, cv2.COLOR_BGRA2BGR)
    else:
        bgr = frame_bgr[:, :, :3]
    zx, zy, zw, zh = zone
    if zw < 8 or zh < 8:
        return None
    roi = bgr[zy : zy + zh, zx : zx + zw]
    return cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)


def crop_zone_zoom_rgb(
    frame_rgb: np.ndarray,
    zone: Tuple[int, int, int, int],
    *,
    target_min: int = 140,
) -> Optional[np.ndarray]:
    """Enlarged raw zone crop for the bottom monitor."""
    patch = crop_raw_zone_rgb(
        cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR), zone
    )
    if patch is None or patch.size == 0:
        return None
    h, w = patch.shape[:2]
    scale = max(target_min / max(h, 1), target_min / max(w, 1), 1.0)
    scale = min(scale, 4.0)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(patch, (nw, nh), interpolation=cv2.INTER_LINEAR)


def zoom_preprocess_bbox_rgb(
    preview_rgb: np.ndarray,
    bbox: Optional[Tuple[int, int, int, int]],
    *,
    target_min: int = 140,
    pad: int = 12,
) -> Optional[np.ndarray]:
    """Zoom into the preprocess bbox region on the preview image.
    Falls back to None when no bbox is available."""
    if preview_rgb is None or preview_rgb.size == 0 or bbox is None:
        return None
    h, w = preview_rgb.shape[:2]
    bx, by, bw, bh = bbox
    x1 = max(0, bx - pad)
    y1 = max(0, by - pad)
    x2 = min(w, bx + bw + pad)
    y2 = min(h, by + bh + pad)
    if (x2 - x1) < 6 or (y2 - y1) < 6:
        return None
    patch = preview_rgb[y1:y2, x1:x2]
    ph, pw = patch.shape[:2]
    scale = max(target_min / max(ph, 1), target_min / max(pw, 1), 1.0)
    scale = min(scale, 6.0)
    nw = max(1, int(round(pw * scale)))
    nh = max(1, int(round(ph * scale)))
    return cv2.resize(patch, (nw, nh), interpolation=cv2.INTER_LINEAR)
