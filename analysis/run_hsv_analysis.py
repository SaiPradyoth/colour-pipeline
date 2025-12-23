import os
import cv2
import numpy as np
import pandas as pd
import re

IMG_DIR = "uploads/hsv_images"
OUT_CSV = "results/v6_texture_results.csv"

LOWER_PERCENTILE = 25
UPPER_PERCENTILE = 75
LIQUID_SAMPLE_RADIUS_PERCENT = 0.4


def extract_well_id(filename):
    m = re.match(r"([A-H][0-9]+)", filename.upper())
    return m.group(1) if m else None


def analyze_image(path):
    img = cv2.imread(path)
    if img is None:
        return None

    h, w = img.shape[:2]
    mh, mw = int(h * 0.2), int(w * 0.2)
    center = img[mh:h-mh, mw:w-mw]

    hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0,30,30), (20,255,255)) + \
           cv2.inRange(hsv, (150,30,30), (180,255,255))

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None

    c = max(cnts, key=cv2.contourArea)
    (_, _), r = cv2.minEnclosingCircle(c)
    r = max(int(r * LIQUID_SAMPLE_RADIUS_PERCENT), 10)

    roi = img[h//2-r:h//2+r, w//2-r:w//2+r]
    if roi.size == 0:
        return None

    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv_roi[:,:,1]
    val = hsv_roi[:,:,2]

    lo = np.percentile(val, LOWER_PERCENTILE)
    hi = np.percentile(val, UPPER_PERCENTILE)

    m = (val >= lo) & (val <= hi)
    if np.sum(m) < 10:
        return None

    return {
        "texture_score": float(np.std(sat[m])),
        "mean_saturation": float(np.mean(sat[m])),
        "pixel_count": int(np.sum(m))
    }


def main():
    records = []

    for f in os.listdir(IMG_DIR):
        if not f.lower().endswith((".jpg",".jpeg",".png")):
            continue

        well = extract_well_id(f)
        if not well:
            continue

        res = analyze_image(os.path.join(IMG_DIR, f))
        if res:
            records.append({"Well": well, **res})

    if not records:
        raise RuntimeError("No valid HSV results")

    df = pd.DataFrame(records)
    df.to_csv(OUT_CSV, index=False)


if __name__ == "__main__":
    os.makedirs("results", exist_ok=True)
    main()
