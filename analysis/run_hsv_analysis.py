# =====================================================
# analysis/run_hsv_analysis.py
# Purpose: HSV-based texture & saturation analysis
# Matches validated in-memory pipeline
# Stateless: NO disk writes
# =====================================================

import os
import cv2
import numpy as np
import pandas as pd
import re

IMG_DIR = "uploads/hsv_images"

LOWER_PERCENTILE = 25
UPPER_PERCENTILE = 75
LIQUID_SAMPLE_RADIUS_PERCENT = 0.4


def extract_well_id(filename):
    m = re.match(r"([A-P][0-9]+)", filename.upper())
    return m.group(1) if m else None


def analyze_image(path):
    img = cv2.imread(path)
    if img is None:
        return None

    h, w = img.shape[:2]
    mh, mw = int(h * 0.2), int(w * 0.2)
    center = img[mh : h - mh, mw : w - mw]

    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)

    mask = (
        cv2.inRange(hsv, (0, 30, 30), (20, 255, 255))
        | cv2.inRange(hsv, (150, 30, 30), (179, 255, 255))
    )

    # Morphological stabilization (IMPORTANT)
    kernel = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None

    c = max(cnts, key=cv2.contourArea)

    (cx, cy), r = cv2.minEnclosingCircle(c)
    cx, cy = int(cx), int(cy)
    r = max(int(r * LIQUID_SAMPLE_RADIUS_PERCENT), 10)

    # ROI bounds
    y0 = max(cy - r, 0)
    y1 = min(cy + r, center.shape[0])
    x0 = max(cx - r, 0)
    x1 = min(cx + r, center.shape[1])

    roi = center[y0:y1, x0:x1]
    if roi.size == 0:
        return None

    roi_h, roi_w = roi.shape[:2]

    # Circular mask
    circular_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    cv2.circle(
        circular_mask,
        (roi_w // 2, roi_h // 2),
        min(r, roi_w // 2, roi_h // 2),
        255,
        -1,
    )

    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv_roi[:, :, 1].astype(np.float32)
    val = hsv_roi[:, :, 2].astype(np.float32)

    valid_vals = val[circular_mask > 0]
    if len(valid_vals) < 10:
        return None

    lo = np.percentile(valid_vals, LOWER_PERCENTILE)
    hi = np.percentile(valid_vals, UPPER_PERCENTILE)

    percentile_mask = (val >= lo) & (val <= hi)
    final_mask = percentile_mask & (circular_mask > 0)

    if np.sum(final_mask) < 10:
        return None

    valid_sat = sat[final_mask]

    return {
        "texture_score": float(np.std(valid_sat)),      # raw std dev
        "mean_saturation": float(np.mean(valid_sat)),   # raw HSV
        "pixel_count": int(len(valid_sat)),
    }


def run_hsv_analysis(img_dir: str = IMG_DIR):
    records = []

    for f in os.listdir(img_dir):
        if not f.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        well = extract_well_id(f)
        if not well:
            continue

        res = analyze_image(os.path.join(img_dir, f))
        if res:
            records.append({"Well": well, **res})

    if not records:
        raise RuntimeError("No valid HSV results")

    return pd.DataFrame(records)
