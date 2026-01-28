# analysis/lighting_diagnostics.py
# --------------------------------
# Image Lighting Diagnostics
# Exposure • White Balance • Uniformity • Glare
# --------------------------------

import os
import cv2
import numpy as np
import pandas as pd
import re

WELL_RE = re.compile(r"([A-H][0-9]{1,2})", re.IGNORECASE)

def extract_well_id(filename: str):
    m = WELL_RE.search(filename)
    return m.group(1).upper() if m else None


def analyze_lighting(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        return None

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # ------------------
    # Exposure
    # ------------------
    V = img_hsv[:, :, 2] / 255.0
    mean_v = float(np.mean(V))
    pct_dark = float(np.mean(V < 0.05) * 100)
    pct_bright = float(np.mean(V > 0.95) * 100)

    if mean_v < 0.35:
        exposure = "Underexposed"
    elif mean_v > 0.75:
        exposure = "Overexposed"
    else:
        exposure = "OK"

    # ------------------
    # White balance
    # ------------------
    R, G, B = img_rgb[:, :, 0], img_rgb[:, :, 1], img_rgb[:, :, 2]
    r_mean, g_mean, b_mean = np.mean(R), np.mean(G), np.mean(B)

    wb_bias = r_mean - b_mean
    if wb_bias > 15:
        wb = "Warm"
    elif wb_bias < -15:
        wb = "Cool"
    else:
        wb = "Neutral"

    # ------------------
    # Uniformity
    # ------------------
    h, w = V.shape
    center = V[h//4:3*h//4, w//4:3*w//4]
    edges = np.concatenate([
        V[:h//4, :].ravel(),
        V[3*h//4:, :].ravel(),
        V[:, :w//4].ravel(),
        V[:, 3*w//4:].ravel(),
    ])

    uniformity_ratio = float(np.mean(center) / (np.mean(edges) + 1e-6))
    uniformity = "Uniform" if 0.9 <= uniformity_ratio <= 1.1 else "Non-uniform"

    # ------------------
    # Glare
    # ------------------
    glare = "Yes" if pct_bright > 1.5 else "No"

    # ------------------
    # Lighting score (0–100)
    # ------------------
    score = 100
    score -= abs(mean_v - 0.55) * 80
    score -= pct_bright * 5
    score -= pct_dark * 3
    score -= abs(wb_bias) * 0.3
    score -= abs(uniformity_ratio - 1.0) * 50
    score = int(np.clip(score, 0, 100))

    return {
        "mean_v": round(mean_v, 3),
        "pct_dark": round(pct_dark, 2),
        "pct_bright": round(pct_bright, 2),
        "exposure": exposure,
        "wb_bias": round(wb_bias, 2),
        "white_balance": wb,
        "uniformity_ratio": round(uniformity_ratio, 3),
        "uniformity": uniformity,
        "glare": glare,
        "lighting_score": score,
    }


def run_lighting_diagnostics(image_dir: str):
    rows = []

    for fname in os.listdir(image_dir):
        well = extract_well_id(fname)
        if not well:
            continue

        path = os.path.join(image_dir, fname)
        metrics = analyze_lighting(path)
        if not metrics:
            continue

        metrics["Well"] = well
        rows.append(metrics)

    df = pd.DataFrame(rows)
    return df
