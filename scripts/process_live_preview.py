"""
Standalone tuning script for exclamation-mark preprocess.

Usage examples:
  python scripts/process_live_preview.py --image path/to/game_screenshot.png
  python scripts/process_live_preview.py --live
  python scripts/process_live_preview.py --loop
  python scripts/process_live_preview.py --image img.png --compare-sample 3
  python scripts/process_live_preview.py --config assets/exclamation_preprocess.json --live

Saves debug strips to  debug/preprocess/
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.exclamation_preprocess import (
    PreprocessConfig,
    load_config,
    run_preprocess,
    save_config,
)
from utils.constants import DETECTION_ZONE_SIZE_X, DETECTION_ZONE_SIZE_Y

DEBUG_DIR = ROOT / "debug" / "preprocess"
ASSETS_DIR = ROOT / "assets"


def _get_zone_crop_bgr(frame_bgra: np.ndarray) -> np.ndarray:
    bgr = frame_bgra[:, :, :3]
    h, w = bgr.shape[:2]
    zw = max(64, int(w * DETECTION_ZONE_SIZE_X))
    zh = max(64, int(h * DETECTION_ZONE_SIZE_Y))
    x1 = max(0, (w - zw) // 2)
    y1 = max(0, (h - zh) // 2)
    return bgr[y1 : y1 + zh, x1 : x1 + zw].copy()


def _live_capture_bgra() -> np.ndarray | None:
    """Grab one frame from the Play Together client using MSS."""
    try:
        import mss
        from utils.win32_utils import find_play_together_window
        from utils.coords import get_client_area_screen_rect
    except ImportError as e:
        print(f"Live capture dependency missing: {e}")
        return None

    hwnd, _ = find_play_together_window()
    if not hwnd:
        print("Play Together window not found — is the game running?")
        return None
    rect = get_client_area_screen_rect(hwnd)
    if not rect:
        print("Could not get client rect")
        return None
    l, t, r, b = rect
    w, h = r - l, b - t
    if w < 10 or h < 10:
        return None
    with mss.mss() as sct:
        frame = np.array(sct.grab({"left": l, "top": t, "width": w, "height": h}))
    return frame


def _build_strip(
    zone_bgr: np.ndarray,
    result,
    sample_bgr: np.ndarray | None = None,
) -> np.ndarray:
    """Horizontal strip: raw zone | soft mask (gray) | composite [| sample ref]."""
    h, w = zone_bgr.shape[:2]

    raw_rgb = cv2.cvtColor(zone_bgr, cv2.COLOR_BGR2RGB)
    mask_rgb = cv2.cvtColor(result.mask, cv2.COLOR_GRAY2RGB)
    preview = result.preview_rgb

    panels = [raw_rgb, mask_rgb, preview]
    if sample_bgr is not None:
        sample_resized = cv2.resize(sample_bgr, (w, h), interpolation=cv2.INTER_AREA)
        sample_rgb = cv2.cvtColor(sample_resized, cv2.COLOR_BGR2RGB)
        panels.append(sample_rgb)

    strip = np.hstack(panels)
    return strip


def _save_strip(strip_rgb: np.ndarray, tag: str = "") -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
    name = f"strip_{tag}_{ts}.png" if tag else f"strip_{ts}.png"
    out = DEBUG_DIR / name
    bgr = cv2.cvtColor(strip_rgb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(out), bgr)
    return out


def _load_sample(n: int) -> np.ndarray | None:
    path = ASSETS_DIR / f"sample ({n}).png"
    if not path.is_file():
        print(f"Sample not found: {path}")
        return None
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def process_image(image_path: str, cfg: PreprocessConfig, compare_sample: int | None):
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Cannot read image: {image_path}")
        return
    # Treat as full frame: extract zone crop
    bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    zone = _get_zone_crop_bgr(bgra)
    result = run_preprocess(zone, cfg)
    sample = _load_sample(compare_sample) if compare_sample else None
    strip = _build_strip(zone, result, sample)
    out = _save_strip(strip, "image")
    print(f"Saved: {out}  (mask pixels: {result.mark_pixel_count}, bbox: {result.bbox})")


def process_live(cfg: PreprocessConfig, compare_sample: int | None):
    frame = _live_capture_bgra()
    if frame is None:
        return
    zone = _get_zone_crop_bgr(frame)
    result = run_preprocess(zone, cfg)
    sample = _load_sample(compare_sample) if compare_sample else None
    strip = _build_strip(zone, result, sample)
    out = _save_strip(strip, "live")
    print(f"Saved: {out}  (mask pixels: {result.mark_pixel_count}, bbox: {result.bbox})")


def process_loop(cfg: PreprocessConfig, compare_sample: int | None):
    print("Looping at ~3 FPS — press Ctrl+C to stop")
    interval = 1.0 / 3.0
    try:
        while True:
            t0 = time.perf_counter()
            frame = _live_capture_bgra()
            if frame is not None:
                zone = _get_zone_crop_bgr(frame)
                result = run_preprocess(zone, cfg)
                sample = _load_sample(compare_sample) if compare_sample else None
                strip = _build_strip(zone, result, sample)
                out = _save_strip(strip, "loop")
                print(f"\r{out.name}  mask={result.mark_pixel_count:5d}  bbox={result.bbox}", end="", flush=True)
            elapsed = time.perf_counter() - t0
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(description="Exclamation preprocess tuning")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", type=str, help="Path to a game screenshot (BGR)")
    group.add_argument("--live", action="store_true", help="Single MSS grab from Play Together")
    group.add_argument("--loop", action="store_true", help="~3 FPS live strips (Ctrl+C to stop)")
    parser.add_argument("--compare-sample", type=int, default=None,
                        help="Append assets/sample (N).png as reference column (visual only)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to JSON config (default: assets/exclamation_preprocess.json)")
    args = parser.parse_args()

    cfg_path = Path(args.config) if args.config else None
    cfg = load_config(cfg_path)

    if args.image:
        process_image(args.image, cfg, args.compare_sample)
    elif args.live:
        process_live(cfg, args.compare_sample)
    elif args.loop:
        process_loop(cfg, args.compare_sample)


if __name__ == "__main__":
    main()
