# =====================================================
# analysis/merge_spectral_hsv.py
# Purpose: merge spectral + HSV/texture metrics
# Stateless: NO disk writes
# =====================================================

import pandas as pd
import numpy as np
import re

EPS_CONC = 1.0  # safe floor for log10


def find_deltae_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        if str(c).strip().lower().startswith("deltae"):
            return c
    raise ValueError("No DeltaE* column found.")


def zscore(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    mu = x.mean(skipna=True)
    sd = x.std(skipna=True, ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.zeros(len(x)), index=series.index)
    return (x - mu) / sd


def extract_well_from_image(name: str):
    m = re.search(
        r"\b([A-P])\s*([1-9]|1[0-9]|2[0-4])\b",
        str(name),
        re.IGNORECASE,
    )
    if not m:
        return None
    return f"{m.group(1).upper()}{int(m.group(2))}"


def merge_spectral_hsv(
    spectral_csv_path: str,
    texture_csv_path: str,
    join_on: str = "Well",
):
    """
    Expects:
      spectral CSV: Well, DeltaE*, LambdaMax, etc.
      texture CSV: Well OR image, texture_score, optional concentration

    Returns:
      merged DataFrame
      dict of correlation metrics
      top-ranked wells by fusion score
    """

    # ---- Load ----
    spec = pd.read_csv(spectral_csv_path)
    tex = pd.read_csv(texture_csv_path)

    # ---- Join key handling ----
    if join_on not in tex.columns:
        if "image" not in tex.columns:
            raise ValueError("Texture CSV must contain Well or image column.")
        tex[join_on] = tex["image"].apply(extract_well_from_image)

    spec[join_on] = spec[join_on].astype(str).str.upper().str.strip()
    tex[join_on] = tex[join_on].astype(str).str.upper().str.strip()

    tex = tex[tex[join_on].notna()].copy()
    spec = spec[spec[join_on].notna()].copy()

    # ---- Merge ----
    df = spec.merge(tex, on=join_on, how="inner")

    if df.empty:
        raise ValueError("Merged dataset is empty. Check well mapping.")

    # ---- Core columns ----
    delta_col = find_deltae_col(df)

    if "texture_score" not in df.columns:
        raise ValueError("texture_score missing in texture CSV.")

    # ---- Log concentration (optional) ----
    if "concentration" in df.columns:
        conc = pd.to_numeric(df["concentration"], errors="coerce").fillna(0)
        df["log_conc"] = np.log10(np.maximum(conc, EPS_CONC))

    # ---- Correlations ----
    dE = pd.to_numeric(df[delta_col], errors="coerce")
    tx = pd.to_numeric(df["texture_score"], errors="coerce")

    stats = {
        "corr_deltaE_texture": dE.corr(tx)
    }

    if "concentration" in df.columns:
        conc = pd.to_numeric(df["concentration"], errors="coerce").fillna(0)
        stats.update({
            "corr_conc_deltaE": conc.corr(dE),
            "corr_conc_texture": conc.corr(tx),
            "corr_logconc_deltaE": df["log_conc"].corr(dE),
            "corr_logconc_texture": df["log_conc"].corr(tx),
        })

    # ---- Fusion score ----
    df["z_deltaE"] = zscore(df[delta_col])
    df["z_texture"] = zscore(df["texture_score"])
    df["fusion_score"] = df["z_deltaE"] + df["z_texture"]

    # ---- Top wells (for UI display) ----
    top = df.sort_values("fusion_score", ascending=False).head(15)

    return df, stats, top
