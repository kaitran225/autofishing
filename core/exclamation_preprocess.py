"""
Enhanced exclamation mark preprocess — color-agnostic, multi-scale detection.

Pipeline:
  1. LAB saliency map (any color mark on any background)
  2. Chroma gate (existing HSV bands as boost signal)
  3. Combined mask (union of saliency + chroma)
  4. Multi-scale candidate extraction (handles any mark size)
  5. Advanced ! shape verification (dot + stem structure scoring)
  6. Best candidate selection
  7. Soft composite + red bbox + contour

Config: assets/exclamation_preprocess.json (hand-tuned on game frames).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

BBox = Tuple[int, int, int, int]
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
CONFIG_PATH = ASSETS_DIR / "exclamation_preprocess.json"


@dataclass
class HueBand:
    h_min: int
    h_max: int
    s_min: int = 45
    s_max: int = 255
    v_min: int = 70
    v_max: int = 255


@dataclass
class PreprocessConfig:
    # Chroma gate (boost)
    hue_bands: List[HueBand] = field(default_factory=list)
    v_norm_floor: int = 55
    clahe_clip: float = 2.0
    clahe_grid: int = 8

    # Saliency
    saliency_blur_small: int = 15
    saliency_blur_large: int = 41
    saliency_weight: float = 1.0

    # Multi-scale
    pyramid_scales: List[float] = field(default_factory=lambda: [1.0, 0.5, 0.25])

    # Shape verification
    min_detection_score: float = 0.35
    dot_circularity_min: float = 0.4
    stem_elongation_min: float = 1.5
    group_max_gap_frac: float = 0.4
    group_align_tolerance: float = 0.35

    # Blob filtering
    max_blob_area_ratio: float = 0.20
    min_component_area: int = 30
    max_pole_aspect: float = 8.0

    # Composite
    dim_factor: float = 0.38
    dilate_px: int = 3
    blur_sigma: float = 1.2


@dataclass
class DetectedCandidate:
    bbox: BBox
    score: float
    is_best: bool = False


@dataclass
class PreprocessResult:
    preview_rgb: np.ndarray
    mask: np.ndarray
    bbox: Optional[BBox] = None
    mark_pixel_count: int = 0
    score: float = 0.0
    candidates: List[DetectedCandidate] = field(default_factory=list)


def default_config() -> PreprocessConfig:
    return PreprocessConfig(
        hue_bands=[
            HueBand(130, 180, 40, 255, 65, 255),
            HueBand(0, 15, 60, 255, 75, 255),
            HueBand(165, 180, 55, 255, 70, 255),
            HueBand(32, 92, 55, 255, 80, 255),
            HueBand(8, 32, 75, 255, 100, 255),
            HueBand(12, 50, 50, 255, 175, 255),
            HueBand(0, 180, 15, 65, 195, 255),
        ],
    )


def load_config(path: Optional[Path] = None) -> PreprocessConfig:
    path = path or CONFIG_PATH
    if not path.is_file():
        return default_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = PreprocessConfig()
        if "hue_bands" in data:
            cfg.hue_bands = [HueBand(**b) for b in data["hue_bands"]]
        else:
            cfg.hue_bands = default_config().hue_bands
        if "pyramid_scales" in data:
            cfg.pyramid_scales = [float(s) for s in data["pyramid_scales"]]
        for key in (
            "v_norm_floor", "clahe_clip", "clahe_grid",
            "saliency_blur_small", "saliency_blur_large", "saliency_weight",
            "min_detection_score", "dot_circularity_min", "stem_elongation_min",
            "group_max_gap_frac", "group_align_tolerance",
            "max_blob_area_ratio", "min_component_area", "max_pole_aspect",
            "dim_factor", "dilate_px", "blur_sigma",
        ):
            if key in data:
                setattr(cfg, key, type(getattr(cfg, key))(data[key]))
        return cfg
    except Exception:
        return default_config()


def save_config(cfg: PreprocessConfig, path: Optional[Path] = None) -> None:
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "hue_bands": [
            {"h_min": b.h_min, "h_max": b.h_max,
             "s_min": b.s_min, "s_max": b.s_max,
             "v_min": b.v_min, "v_max": b.v_max}
            for b in cfg.hue_bands
        ],
        "v_norm_floor": cfg.v_norm_floor,
        "clahe_clip": cfg.clahe_clip,
        "clahe_grid": cfg.clahe_grid,
        "saliency_blur_small": cfg.saliency_blur_small,
        "saliency_blur_large": cfg.saliency_blur_large,
        "saliency_weight": cfg.saliency_weight,
        "pyramid_scales": cfg.pyramid_scales,
        "min_detection_score": cfg.min_detection_score,
        "dot_circularity_min": cfg.dot_circularity_min,
        "stem_elongation_min": cfg.stem_elongation_min,
        "group_max_gap_frac": cfg.group_max_gap_frac,
        "group_align_tolerance": cfg.group_align_tolerance,
        "max_blob_area_ratio": cfg.max_blob_area_ratio,
        "min_component_area": cfg.min_component_area,
        "max_pole_aspect": cfg.max_pole_aspect,
        "dim_factor": cfg.dim_factor,
        "dilate_px": cfg.dilate_px,
        "blur_sigma": cfg.blur_sigma,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage 1: LAB saliency (color-agnostic)
# ---------------------------------------------------------------------------

def _compute_saliency(bgr: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """Compute local color contrast saliency in LAB space."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    ks = cfg.saliency_blur_small | 1
    kl = cfg.saliency_blur_large | 1

    mean_small = cv2.GaussianBlur(lab, (ks, ks), 0)
    mean_large = cv2.GaussianBlur(lab, (kl, kl), 0)

    diff_small = lab - mean_small
    diff_large = lab - mean_large

    sal_small = np.sqrt(np.sum(diff_small ** 2, axis=2))
    sal_large = np.sqrt(np.sum(diff_large ** 2, axis=2))

    saliency = np.maximum(sal_small, sal_large)

    # Normalize to 0-255
    smax = saliency.max()
    if smax > 1e-3:
        saliency = (saliency / smax * 255.0)
    return saliency.astype(np.uint8)


def _saliency_mask(saliency: np.ndarray, percentile: float = 88.0) -> np.ndarray:
    """Keep only the top N% most salient pixels.
    Lower percentile = more candidates pass through (shape scoring handles filtering)."""
    if saliency.max() < 5:
        return np.zeros_like(saliency)
    thresh_val = np.percentile(saliency, percentile)
    thresh_val = max(thresh_val, 20)  # absolute floor
    _, mask = cv2.threshold(saliency, int(thresh_val), 255, cv2.THRESH_BINARY)
    return mask


# ---------------------------------------------------------------------------
# Stage 2: Chroma gate (boost, existing logic)
# ---------------------------------------------------------------------------

def _build_chroma_mask(bgr: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """HSV hue bands + CLAHE V-norm floor as boost signal."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v_channel = hsv[:, :, 2]

    clahe = cv2.createCLAHE(clipLimit=cfg.clahe_clip, tileGridSize=(cfg.clahe_grid, cfg.clahe_grid))
    v_norm = clahe.apply(v_channel)

    h, w = hsv.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    for band in cfg.hue_bands:
        lo = np.array([band.h_min, band.s_min, band.v_min], dtype=np.uint8)
        hi = np.array([band.h_max, band.s_max, band.v_max], dtype=np.uint8)
        band_mask = cv2.inRange(hsv, lo, hi)
        mask = cv2.bitwise_or(mask, band_mask)

    v_gate = (v_norm >= cfg.v_norm_floor).astype(np.uint8) * 255
    mask = cv2.bitwise_and(mask, v_gate)
    return mask


# ---------------------------------------------------------------------------
# Stage 3: Mask refinement + watershed separation
# ---------------------------------------------------------------------------

def _refine_saliency_mask(sal_mask: np.ndarray) -> np.ndarray:
    """Light cleanup: remove noise specks, connect very close pixels within a blob."""
    # Small open to remove isolated noise pixels
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    refined = cv2.morphologyEx(sal_mask, cv2.MORPH_OPEN, k_open, iterations=1)
    # Very small close to fill 1-2px internal gaps within solid blobs (not bridge separate blobs)
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    refined = cv2.morphologyEx(refined, cv2.MORPH_CLOSE, k_close, iterations=1)
    return refined


def _watershed_split(mask: np.ndarray, bgr: np.ndarray) -> np.ndarray:
    """Use distance-transform + watershed to separate touching blobs."""
    if np.count_nonzero(mask) < 20:
        return mask

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    dist_max = dist.max()
    if dist_max < 2:
        return mask
    dist_norm = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    _, sure_fg = cv2.threshold(dist_norm, int(0.4 * 255), 255, cv2.THRESH_BINARY)
    sure_fg = sure_fg.astype(np.uint8)

    if np.count_nonzero(sure_fg) < 5:
        return mask

    k_bg = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    sure_bg = cv2.dilate(mask, k_bg, iterations=2)
    unknown = cv2.subtract(sure_bg, sure_fg)

    num_labels, markers = cv2.connectedComponents(sure_fg)
    if num_labels < 2:
        return mask
    markers = markers + 1
    markers[unknown == 255] = 0

    if len(bgr.shape) == 2:
        ws_img = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    elif bgr.shape[2] == 4:
        ws_img = bgr[:, :, :3].copy()
    else:
        ws_img = bgr.copy()

    markers = cv2.watershed(ws_img, markers)

    result = np.zeros_like(mask)
    result[markers > 1] = 255
    return result


# ---------------------------------------------------------------------------
# Stage 4: Multi-scale candidate extraction
# ---------------------------------------------------------------------------

@dataclass
class _Candidate:
    bbox: BBox  # x, y, w, h in native coords
    mask_region: np.ndarray  # binary mask of the candidate region (native size)
    area: int = 0
    score: float = 0.0


def _extract_candidates_single_scale(
    mask: np.ndarray, scale: float, native_h: int, native_w: int, cfg: PreprocessConfig
) -> List[_Candidate]:
    """Extract connected component candidates at one scale."""
    if abs(scale - 1.0) > 0.01:
        sh = max(16, int(native_h * scale))
        sw = max(16, int(native_w * scale))
        scaled_mask = cv2.resize(mask, (sw, sh), interpolation=cv2.INTER_NEAREST)
    else:
        scaled_mask = mask
        sh, sw = native_h, native_w

    total_area = native_h * native_w
    min_area = max(cfg.min_component_area, int(total_area * 0.001))
    max_area = int(total_area * cfg.max_blob_area_ratio)

    contours, _ = cv2.findContours(scaled_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        # Scale area back to native
        native_area = int(area / (scale * scale)) if scale < 0.99 else int(area)
        if native_area < min_area or native_area > max_area:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        # Map back to native coordinates
        inv = 1.0 / scale if scale > 0.01 else 1.0
        nx, ny = int(x * inv), int(y * inv)
        nw, nh = max(4, int(bw * inv)), max(4, int(bh * inv))
        # Clamp
        nx = max(0, min(nx, native_w - 4))
        ny = max(0, min(ny, native_h - 4))
        nw = min(nw, native_w - nx)
        nh = min(nh, native_h - ny)

        # Reject horizontal runs
        if nw > 3 * nh:
            continue

        # Extract native-resolution mask patch
        region_mask = mask[ny:ny + nh, nx:nx + nw]
        candidates.append(_Candidate(
            bbox=(nx, ny, nw, nh),
            mask_region=region_mask,
            area=native_area,
        ))

    return candidates


def _iou(a: BBox, b: BBox) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / max(union, 1)


def _merge_candidates(all_candidates: List[_Candidate]) -> List[_Candidate]:
    """Remove duplicate candidates across scales (keep larger area)."""
    if not all_candidates:
        return []
    # Sort by area descending
    sorted_cands = sorted(all_candidates, key=lambda c: c.area, reverse=True)
    kept: List[_Candidate] = []
    for cand in sorted_cands:
        is_dup = False
        for existing in kept:
            if _iou(cand.bbox, existing.bbox) > 0.3:
                is_dup = True
                break
        if not is_dup:
            kept.append(cand)
    return kept


def _extract_multiscale_candidates(
    mask: np.ndarray, cfg: PreprocessConfig
) -> List[_Candidate]:
    h, w = mask.shape[:2]
    all_cands: List[_Candidate] = []
    for scale in cfg.pyramid_scales:
        cands = _extract_candidates_single_scale(mask, scale, h, w, cfg)
        all_cands.extend(cands)
    return _merge_candidates(all_cands)


# ---------------------------------------------------------------------------
# Stage 5: Advanced ! shape verification + grouping
# ---------------------------------------------------------------------------

def _try_group_dot_stem(candidates: List[_Candidate], cfg: PreprocessConfig) -> List[_Candidate]:
    """Try to group vertically-adjacent small blobs as dot+stem pairs."""
    grouped: List[_Candidate] = []
    used = set()

    for i, top in enumerate(candidates):
        if i in used:
            continue
        tx, ty, tw, th = top.bbox
        top_cx = tx + tw / 2.0

        for j, bot in enumerate(candidates):
            if j <= i or j in used:
                continue
            bx, by, bw, bh = bot.bbox
            bot_cx = bx + bw / 2.0

            # Bot must be below top
            gap = by - (ty + th)
            combined_h = (by + bh) - ty
            if combined_h < 4:
                continue
            if gap < 0 or gap > combined_h * cfg.group_max_gap_frac:
                continue

            # Horizontal alignment
            max_offset = max(tw, bw) * cfg.group_align_tolerance
            if abs(top_cx - bot_cx) > max_offset:
                continue

            # Group them
            gx = min(tx, bx)
            gy = ty
            gw = max(tx + tw, bx + bw) - gx
            gh = (by + bh) - ty
            # Combined mask
            combined_mask = np.zeros((gh, gw), dtype=np.uint8)
            # Place top
            combined_mask[0:th, tx - gx:tx - gx + tw] = top.mask_region[:th, :tw]
            # Place bottom
            by_off = by - gy
            combined_mask[by_off:by_off + bh, bx - gx:bx - gx + bw] = bot.mask_region[:bh, :bw]

            grouped.append(_Candidate(
                bbox=(gx, gy, gw, gh),
                mask_region=combined_mask,
                area=top.area + bot.area,
            ))
            used.add(i)
            used.add(j)
            break

    # Add ungrouped candidates
    for i, c in enumerate(candidates):
        if i not in used:
            grouped.append(c)

    return grouped


def _score_candidate(cand: _Candidate, saliency: np.ndarray, roi_area: int, cfg: PreprocessConfig, chroma_mask: Optional[np.ndarray] = None) -> float:
    """Score how much a candidate looks like a ! mark (0.0 to 1.0).
    Applies hard rejections for things that clearly aren't ! marks.
    Chroma overlap provides a scoring boost (not used for candidate extraction)."""
    x, y, w, h = cand.bbox
    if w < 3 or h < 3:
        return 0.0

    roi_h, roi_w = saliency.shape[:2]

    # --- Hard rejections ---
    # Reject candidates touching the zone border (edge artifacts, not real marks)
    edge_margin = max(8, int(min(roi_h, roi_w) * 0.03))
    if x < edge_margin or y < edge_margin:
        return 0.0
    if (x + w) > (roi_w - edge_margin) or (y + h) > (roi_h - edge_margin):
        return 0.0
    # ! mark is narrow: reject anything wider than 12% of zone width
    if w > roi_w * 0.12:
        return 0.0
    # ! mark is tall-and-narrow: aspect ratio must be at least 1.5:1
    aspect = h / max(w, 1)
    if aspect < 1.5:
        return 0.0
    # ! mark is small: reject huge blobs (> 8% of ROI area)
    area_frac = cand.area / max(roi_area, 1)
    if area_frac > 0.08:
        return 0.0
    # ! mark is not tiny: reject blobs smaller than 0.03% of ROI
    if area_frac < 0.0003:
        return 0.0

    mask = cand.mask_region
    mh, mw = mask.shape[:2]
    mh = min(mh, h)
    mw = min(mw, w)
    work_mask = mask[:mh, :mw]

    total_pixels = np.count_nonzero(work_mask)
    if total_pixels < 8:
        return 0.0

    # --- Dot zone (top 25%) ---
    dot_h = max(2, int(mh * 0.25))
    dot_zone = work_mask[:dot_h, :]
    dot_pixels = np.count_nonzero(dot_zone)

    # --- Gap zone (25%-40%) — should be mostly empty for a real ! ---
    gap_start = int(mh * 0.25)
    gap_end = int(mh * 0.40)
    if gap_end > gap_start + 1:
        gap_zone = work_mask[gap_start:gap_end, :]
        gap_pixels = np.count_nonzero(gap_zone)
        gap_total = gap_zone.size
        gap_fill = gap_pixels / max(gap_total, 1)
    else:
        gap_fill = 0.5

    # --- Stem zone (bottom 55%) ---
    stem_start = max(2, int(mh * 0.45))
    stem_zone = work_mask[stem_start:, :]
    stem_pixels = np.count_nonzero(stem_zone)

    # Must have BOTH dot and stem (hard requirement)
    if dot_pixels < 3 or stem_pixels < 3:
        return 0.0

    # Dot circularity — dot should be compact/round
    dot_circularity = 0.0
    dot_contours, _ = cv2.findContours(dot_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if dot_contours:
        largest_dot = max(dot_contours, key=cv2.contourArea)
        dot_area = cv2.contourArea(largest_dot)
        dot_perim = cv2.arcLength(largest_dot, True)
        if dot_perim > 1:
            dot_circularity = min(1.0, 4.0 * math.pi * dot_area / (dot_perim * dot_perim))

    # Stem elongation — stem should be vertically elongated
    stem_elongation = 0.0
    stem_contours, _ = cv2.findContours(stem_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if stem_contours:
        largest_stem = max(stem_contours, key=cv2.contourArea)
        _, _, sw, sh = cv2.boundingRect(largest_stem)
        if sw > 0:
            raw_elong = sh / max(sw, 1)
            stem_elongation = min(1.0, max(0.0, (raw_elong - 1.0) / 3.0))

    # Vertical alignment between dot center and stem center
    alignment_score = 0.0
    if dot_contours and stem_contours:
        largest_dot = max(dot_contours, key=cv2.contourArea)
        largest_stem = max(stem_contours, key=cv2.contourArea)
        dot_m = cv2.moments(largest_dot)
        stem_m = cv2.moments(largest_stem)
        if dot_m["m00"] > 0 and stem_m["m00"] > 0:
            dot_cx = dot_m["m10"] / dot_m["m00"]
            stem_cx = stem_m["m10"] / stem_m["m00"]
            offset_frac = abs(dot_cx - stem_cx) / max(mw, 1)
            alignment_score = max(0.0, 1.0 - offset_frac * 4.0)

    # Gap quality — a real ! has a visible gap between dot and stem
    gap_score = max(0.0, 1.0 - gap_fill * 2.5)

    # Saliency intensity (mild weight)
    sal_region = saliency[y:y + min(mh, roi_h - y), x:x + min(mw, roi_w - x)]
    sal_mean = float(np.mean(sal_region)) / 255.0 if sal_region.size > 0 else 0.0

    # Compactness: fill ratio of mask within bbox (! is ~30-50% filled)
    fill_ratio = total_pixels / max(mh * mw, 1)
    compactness = 1.0 - abs(fill_ratio - 0.38) * 3.0
    compactness = max(0.0, min(1.0, compactness))

    # Aspect ratio quality: ideal ! is ~2.5:1 to 5:1
    if aspect < 2.0:
        aspect_score = 0.0
    elif aspect <= 5.0:
        aspect_score = 1.0
    else:
        aspect_score = max(0.0, 1.0 - (aspect - 5.0) / 4.0)

    # Chroma overlap boost: if candidate overlaps with known game colors, boost score
    chroma_boost = 0.0
    if chroma_mask is not None:
        chroma_region = chroma_mask[y:y + min(mh, roi_h - y), x:x + min(mw, roi_w - x)]
        if chroma_region.size > 0:
            chroma_overlap = float(np.count_nonzero(chroma_region)) / max(total_pixels, 1)
            chroma_boost = min(1.0, chroma_overlap * 1.5)

    score = (
        0.20 * dot_circularity
        + 0.20 * stem_elongation
        + 0.16 * alignment_score
        + 0.14 * gap_score
        + 0.08 * aspect_score
        + 0.07 * compactness
        + 0.05 * sal_mean
        + 0.10 * chroma_boost
    )

    return min(1.0, score)


# ---------------------------------------------------------------------------
# Stage 7: Composite + visualization
# ---------------------------------------------------------------------------

def _soft_mask(binary: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.dilate_px, cfg.dilate_px))
    dilated = cv2.dilate(binary, k, iterations=1)
    if cfg.blur_sigma > 0.1:
        ksize = max(3, int(cfg.blur_sigma * 4) | 1)
        soft = cv2.GaussianBlur(dilated, (ksize, ksize), cfg.blur_sigma)
    else:
        soft = dilated
    return soft


def _composite(roi_rgb: np.ndarray, soft: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    alpha = soft.astype(np.float32) / 255.0
    dim = cfg.dim_factor
    weight = dim + (1.0 - dim) * alpha
    out = (roi_rgb.astype(np.float32) * weight[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)
    return out


def _mask_bbox(mask: np.ndarray) -> Optional[BBox]:
    ys, xs = np.where(mask > 0)
    if len(xs) < 4:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_preprocess(bgr_roi: np.ndarray, cfg: Optional[PreprocessConfig] = None) -> PreprocessResult:
    """
    Full enhanced preprocess pipeline on a zone crop.
    Returns composite preview (RGB), binary mask, optional bbox, pixel count, score.
    Multi-candidate: all candidates above threshold are reported and drawn.
    """
    if cfg is None:
        cfg = load_config()

    h, w = bgr_roi.shape[:2]
    roi_area = h * w

    # Stage 1: LAB saliency (primary signal for candidate extraction)
    saliency = _compute_saliency(bgr_roi, cfg)
    sal_mask = _saliency_mask(saliency)

    # Stage 2: Chroma gate (used only for scoring boost, not for candidate extraction)
    chroma_mask = _build_chroma_mask(bgr_roi, cfg)

    # Stage 3: Refine saliency mask
    refined = _refine_saliency_mask(sal_mask)

    # Stage 4: Multi-scale candidate extraction (from saliency only)
    candidates = _extract_multiscale_candidates(refined, cfg)

    # Apply watershed only to oversized candidates (split merged blobs, keep small ones intact)
    split_candidates: List[_Candidate] = []
    for cand in candidates:
        cx, cy, cw, ch = cand.bbox
        if cand.area > roi_area * 0.03:
            # Large blob — try to split with watershed
            region_mask = np.zeros((h, w), dtype=np.uint8)
            rh, rw = cand.mask_region.shape[:2]
            paste_h = min(rh, ch, h - cy)
            paste_w = min(rw, cw, w - cx)
            if paste_h > 0 and paste_w > 0:
                region_mask[cy:cy + paste_h, cx:cx + paste_w] = cand.mask_region[:paste_h, :paste_w]
            split_mask = _watershed_split(region_mask, bgr_roi)
            sub_cands = _extract_multiscale_candidates(split_mask, cfg)
            if sub_cands:
                split_candidates.extend(sub_cands)
            else:
                split_candidates.append(cand)
        else:
            split_candidates.append(cand)
    candidates = _merge_candidates(split_candidates)

    # Stage 5: Group dot+stem pairs and score (chroma used as scoring boost)
    candidates = _try_group_dot_stem(candidates, cfg)
    for cand in candidates:
        cand.score = _score_candidate(cand, saliency, roi_area, cfg, chroma_mask)

    # Stage 6: Select all candidates above threshold, sorted by score
    candidates.sort(key=lambda c: c.score, reverse=True)
    accepted = [c for c in candidates if c.score >= cfg.min_detection_score]

    # Build final mask from best candidate
    final_mask = np.zeros((h, w), dtype=np.uint8)
    best_bbox: Optional[BBox] = None
    best_score = 0.0
    detected_list: List[DetectedCandidate] = []

    if accepted:
        best = accepted[0]
        bx, by, bw, bh = best.bbox
        region = best.mask_region
        rh, rw = region.shape[:2]
        paste_h = min(rh, bh, h - by)
        paste_w = min(rw, bw, w - bx)
        if paste_h > 0 and paste_w > 0:
            final_mask[by:by + paste_h, bx:bx + paste_w] = region[:paste_h, :paste_w]
        best_bbox = best.bbox
        best_score = best.score
        detected_list.append(DetectedCandidate(bbox=best.bbox, score=best.score, is_best=True))

        # Add secondary candidates
        for sec in accepted[1:]:
            detected_list.append(DetectedCandidate(bbox=sec.bbox, score=sec.score, is_best=False))

    # Stage 7: Composite + multi-candidate bboxes
    soft = _soft_mask(final_mask, cfg)
    roi_rgb = cv2.cvtColor(bgr_roi, cv2.COLOR_BGR2RGB)
    preview = _composite(roi_rgb, soft, cfg)

    # Draw contour in green for best candidate mask
    contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cv2.drawContours(preview, contours, -1, (100, 255, 120), 1)

    # Draw bboxes: red for best, yellow for secondary candidates
    for det in detected_list:
        bx, by, bw, bh = det.bbox
        if det.is_best:
            color = (255, 40, 40)
            thickness = 2
        else:
            color = (255, 220, 50)
            thickness = 1
        cv2.rectangle(preview, (bx, by), (bx + bw, by + bh), color, thickness)
        label = f"{det.score:.2f}"
        label_color = (255, 80, 80) if det.is_best else (220, 200, 60)
        cv2.putText(preview, label, (bx, max(12, by - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, label_color, 1, cv2.LINE_AA)

    count = int(np.count_nonzero(final_mask))

    return PreprocessResult(
        preview_rgb=preview,
        mask=final_mask,
        bbox=best_bbox,
        mark_pixel_count=count,
        score=best_score,
        candidates=detected_list,
    )
