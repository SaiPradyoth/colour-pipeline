# =====================================================
# analysis/fusion_qc.py
# Purpose: merge spectral + HSV, add QC flags + lighting suggestions
# Stateless: NO disk writes
# =====================================================

import re
import numpy as np
import pandas as pd

WELL_RE = re.compile(r"^([A-Pa-p])(\d{1,2})$")


def _norm_well(w):
    if w is None:
        return None
    w = str(w).strip().upper()
    return w if WELL_RE.match(w) else None


def _extract_well_from_image_name(name: str):
    base = str(name).split("/")[-1].split("\\")[-1]
    stem = base.rsplit(".", 1)[0].strip().upper()
    if _norm_well(stem):
        return stem
    tok = re.split(r"[\s_\-]+", stem)[0]
    return _norm_well(tok)


def _corr(a: pd.Series, b: pd.Series):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    mask = a.notna() & b.notna()
    if mask.sum() < 2:
        return float("nan")
    return float(a[mask].corr(b[mask]))


def build_fusion_table(
    spectral_csv_path: str,
    hsv_csv_path: str,
    texture_hi: float = 18.0,
    sat_lo: float = 40.0,
    sat_hi: float = 120.0,
    pix_lo: int = 8000,
):
    """
    Expects:
      - spectral CSV: Well, L*, a*, b*, LambdaMax, DeltaE*
      - hsv CSV:
          A) Well, texture_score, mean_saturation, pixel_count
          B) image, texture_score, mean_saturation, pixel_count

    Returns:
      - merged DataFrame (in-memory only)
      - dict of plate-level correlation stats
    """

    spec = pd.read_csv(spectral_csv_path)
    hsv = pd.read_csv(hsv_csv_path)

    # ----- identify DeltaE column -----
    delta_col = next(
        (c for c in spec.columns if str(c).lower().startswith("deltae")),
        None,
    )

    # ----- normalize wells -----
    if "Well" in hsv.columns:
        hsv["Well"] = hsv["Well"].apply(_norm_well)
    elif "image" in hsv.columns:
        hsv["Well"] = hsv["image"].apply(_extract_well_from_image_name)
    else:
        raise ValueError("HSV CSV must have 'Well' or 'image' column")

    spec["Well"] = spec["Well"].apply(_norm_well)

    hsv = hsv[hsv["Well"].notna()].copy()
    spec = spec[spec["Well"].notna()].copy()

    hsv = hsv.drop_duplicates(subset=["Well"], keep="last")

    merged = pd.merge(spec, hsv, on="Well", how="left")

    # ----- numeric coercion -----
    for c in ["texture_score", "mean_saturation", "pixel_count"]:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce")

    # ----- QC flags -----
    merged["qc_low_pixels"] = merged["pixel_count"].fillna(0) < pix_lo
    merged["qc_high_texture"] = merged["texture_score"] > texture_hi
    merged["qc_sat_low"] = merged["mean_saturation"] < sat_lo
    merged["qc_sat_high"] = merged["mean_saturation"] > sat_hi

    merged["qc_imaging_bad"] = (
        merged["qc_low_pixels"]
        | merged["qc_high_texture"]
        | merged["qc_sat_low"]
        | merged["qc_sat_high"]
    )

    # ----- plate-level correlations -----
    stats = {}
    if delta_col:
        stats["corr_deltaE_texture"] = _corr(
            merged[delta_col], merged["texture_score"]
        )
        stats["corr_deltaE_sat"] = _corr(
            merged[delta_col], merged["mean_saturation"]
        )
    if "L*" in merged.columns:
        stats["corr_L_texture"] = _corr(
            merged["L*"], merged["texture_score"]
        )
        stats["corr_L_sat"] = _corr(
            merged["L*"], merged["mean_saturation"]
        )

    # ----- suggestions -----
    def suggest(row):
        if pd.isna(row.get("texture_score")) and pd.isna(row.get("mean_saturation")):
            return "No image for this well."
        notes = []
        if row.get("qc_low_pixels"):
            notes.append("ROI too small → reframe.")
        if row.get("qc_high_texture"):
            notes.append("High texture → glare/blur; use diffuser.")
        if row.get("qc_sat_low"):
            notes.append("Low saturation → increase exposure.")
        if row.get("qc_sat_high"):
            notes.append("High saturation → reduce exposure / lock WB.")
        return " ".join(notes) if notes else "Imaging looks stable."

    merged["imaging_suggestion"] = merged.apply(suggest, axis=1)

    # ----- optional fusion score -----
    if delta_col and merged[delta_col].notna().any():
        d = pd.to_numeric(merged[delta_col], errors="coerce")
        denom = (d.max() - d.min()) or 1.0
        merged["deltaE_norm"] = (d - d.min()) / denom
        stable = np.where(merged["qc_imaging_bad"], 0.4, 1.0)
        merged["fusion_score"] = np.clip(
            merged["deltaE_norm"].fillna(0) * stable, 0, 1
        )
    else:
        merged["fusion_score"] = np.nan

    return merged, stats
def build_fusion_table_from_dfs(spec_df: pd.DataFrame, hsv_df: pd.DataFrame):
    """
    In-memory fusion: NO CSVs
    """
    # reuse existing logic by pretending columns already loaded
    merged = pd.merge(
        spec_df.copy(),
        hsv_df.copy(),
        on="Well",
        how="left"
    )

    # minimal stats placeholder (expand later if needed)
    stats = {}

    return merged, stats
