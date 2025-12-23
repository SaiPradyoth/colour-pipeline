# =====================================================
# 1) Create: analysis/fusion_qc.py
# Purpose: merge spectral + HSV, add QC flags + lighting suggestions
# =====================================================

import re
import numpy as np
import pandas as pd


WELL_RE = re.compile(r"^([A-Pa-p])(\d{1,2})$")


def _norm_well(w):
    if w is None:
        return None
    w = str(w).strip().upper()
    m = WELL_RE.match(w)
    return w if m else None


def _extract_well_from_image_name(name: str):
    # Accept "B5.jpg", "B5.png", "B5_anything.jpg"
    base = str(name).split("/")[-1]
    base = base.split("\\")[-1]
    stem = base.rsplit(".", 1)[0].strip().upper()
    # Try exact stem first
    if _norm_well(stem):
        return stem
    # Try first token split by underscore/space/dash
    tok = re.split(r"[\s_\-]+", stem)[0]
    return _norm_well(tok)


def _corr(a: pd.Series, b: pd.Series):
    # Safe correlation: returns NaN if <2 valid points
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    mask = a.notna() & b.notna()
    if int(mask.sum()) < 2:
        return float("nan")
    return float(a[mask].corr(b[mask]))


def build_fusion_table(
    spectral_csv_path: str,
    hsv_csv_path: str,
    out_csv_path: str = "results/fusion_results.csv",
    # thresholds (tweak later)
    texture_hi: float = 18.0,
    sat_lo: float = 40.0,
    sat_hi: float = 120.0,
    pix_lo: int = 8000,
):
    """
    Expects:
      - spectral CSV contains columns: Well, L*, a*, b*, LambdaMax, and DeltaE... (any DeltaE col)
      - hsv CSV contains either:
          A) columns: Well, texture_score, mean_saturation, pixel_count
          OR
          B) columns: image, texture_score, mean_saturation, pixel_count  (well extracted from image name)
    Produces:
      - results/fusion_results.csv
      - dict of plate-level correlations to display
    """

    spec = pd.read_csv(spectral_csv_path)
    hsv = pd.read_csv(hsv_csv_path)

    # ----- identify DeltaE column in spectral -----
    delta_col = None
    for c in spec.columns:
        if str(c).lower().startswith("deltae"):
            delta_col = c
            break

    # ----- normalize wells -----
    if "Well" in hsv.columns:
        hsv["Well"] = hsv["Well"].apply(_norm_well)
    elif "image" in hsv.columns:
        hsv["Well"] = hsv["image"].apply(_extract_well_from_image_name)
    else:
        raise ValueError("HSV CSV must have 'Well' or 'image' column")

    spec["Well"] = spec["Well"].apply(_norm_well)

    # Drop invalid wells
    hsv = hsv[hsv["Well"].notna()].copy()
    spec = spec[spec["Well"].notna()].copy()

    # If HSV has duplicates per well, keep the last one (most recent upload)
    hsv = hsv.drop_duplicates(subset=["Well"], keep="last")

    merged = pd.merge(spec, hsv, on="Well", how="left")

    # ----- numeric coercion -----
    for c in ["texture_score", "mean_saturation", "pixel_count"]:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce")

    # ----- per-well QC flags -----
    merged["qc_low_pixels"] = merged["pixel_count"].fillna(0).astype(float) < float(pix_lo)
    merged["qc_high_texture"] = merged["texture_score"].astype(float) > float(texture_hi)
    merged["qc_sat_low"] = merged["mean_saturation"].astype(float) < float(sat_lo)
    merged["qc_sat_high"] = merged["mean_saturation"].astype(float) > float(sat_hi)

    # This is the "camera/lighting likely bad" flag:
    merged["qc_imaging_bad"] = (
        merged["qc_low_pixels"]
        | merged["qc_high_texture"]
        | merged["qc_sat_low"]
        | merged["qc_sat_high"]
    )

    # ----- plate-level correlations (diagnostics) -----
    # If these are strong, HSV is driven by chemistry; if weak/erratic, lighting dominates.
    stats = {}
    if delta_col:
        stats["corr_deltaE_texture"] = _corr(merged[delta_col], merged["texture_score"])
        stats["corr_deltaE_sat"] = _corr(merged[delta_col], merged["mean_saturation"])
    if "L*" in merged.columns:
        stats["corr_L_texture"] = _corr(merged["L*"], merged["texture_score"])
        stats["corr_L_sat"] = _corr(merged["L*"], merged["mean_saturation"])

    # ----- human-readable suggestions -----
    def suggest(row):
        # Keep simple, actionable
        if pd.isna(row.get("texture_score")) and pd.isna(row.get("mean_saturation")):
            return "No image for this well."
        notes = []
        if bool(row.get("qc_low_pixels")):
            notes.append("ROI too small/failed → reframe/closer shot.")
        if bool(row.get("qc_high_texture")):
            notes.append("High texture → glare/bubbles/blur; retake with diffuser + steady focus.")
        if bool(row.get("qc_sat_low")):
            notes.append("Low saturation → underexposed/washed; increase light or lock exposure.")
        if bool(row.get("qc_sat_high")):
            notes.append("High saturation → over-saturated/cast; lock white balance + reduce exposure.")
        if not notes:
            notes.append("Imaging looks stable.")
        return " ".join(notes)

    merged["imaging_suggestion"] = merged.apply(suggest, axis=1)

    # ----- optional: a simple fusion score (0..1) -----
    # High when ΔE is large AND imaging is stable. (You can tune later.)
    # math (triple-checked):
    # - delta_norm = (ΔE - min) / (max - min)
    # - stable = 1 if qc_imaging_bad==False else 0.4
    if delta_col and merged[delta_col].notna().any():
        d = pd.to_numeric(merged[delta_col], errors="coerce")
        dmin = float(d.min())
        dmax = float(d.max())
        denom = (dmax - dmin) if (dmax - dmin) != 0 else 1.0
        merged["deltaE_norm"] = (d - dmin) / denom
        stable_factor = np.where(merged["qc_imaging_bad"].fillna(True), 0.4, 1.0)
        merged["fusion_score"] = np.clip(merged["deltaE_norm"].fillna(0) * stable_factor, 0, 1)
    else:
        merged["fusion_score"] = np.nan

    merged.to_csv(out_csv_path, index=False)
    return out_csv_path, stats
