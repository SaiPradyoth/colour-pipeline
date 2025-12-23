import pandas as pd
import numpy as np

# ---------- CONFIG ----------
SPECTRAL_CSV = "plate_results.csv"        # from your Flask export (has Well, DeltaE..., LambdaMax, etc.)
TEXTURE_CSV  = "v6_texture_results.csv"   # from your image pipeline (has image, concentration, texture_score...)
JOIN_ON = "Well"                          # preferred if you can map image->well
EPS_CONC = 1.0                            # safe floor for log10
# ----------------------------

def find_deltae_col(df: pd.DataFrame) -> str:
    # Find first column that starts with "DeltaE" (case-insensitive)
    for c in df.columns:
        if str(c).strip().lower().startswith("deltae"):
            return c
    raise ValueError("No DeltaE* column found in spectral CSV.")

def zscore(series: pd.Series) -> pd.Series:
    # Safe z-score: if std==0, returns zeros
    x = pd.to_numeric(series, errors="coerce")
    mu = x.mean(skipna=True)
    sd = x.std(skipna=True, ddof=0)  # population std to avoid small-N blowups
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.zeros(len(x)), index=series.index)
    return (x - mu) / sd

# ---- Load ----
spec = pd.read_csv(SPECTRAL_CSV)
tex  = pd.read_csv(TEXTURE_CSV)

# ---- Normalize / choose join key ----
# If your texture data does NOT have Well, you MUST create it (e.g., from filename mapping).
# Placeholder: if filename contains well like "A1" etc, extract it:
if JOIN_ON not in tex.columns:
    # Example regex: looks for A1..P24 patterns inside filename
    import re
    def extract_well(name):
        m = re.search(r"\b([A-P])\s*([1-9]|1[0-9]|2[0-4])\b", str(name), re.IGNORECASE)
        if not m: 
            return None
        return f"{m.group(1).upper()}{int(m.group(2))}"
    tex[JOIN_ON] = tex["image"].apply(extract_well)

# ---- Merge ----
df = spec.merge(tex, on=JOIN_ON, how="inner", suffixes=("_spec", "_img"))

if df.empty:
    raise ValueError("Merged dataset is empty. Your JOIN key doesn't match between spectral and texture data.")

# ---- Core columns ----
delta_col = find_deltae_col(df)
if "texture_score" not in df.columns:
    raise ValueError("texture_score not found in texture CSV.")
if "concentration" not in df.columns:
    # ok if you don't have conc; we'll skip those analyses
    pass

# ---- Log concentration safely ----
if "concentration" in df.columns:
    conc = pd.to_numeric(df["concentration"], errors="coerce").fillna(0)
    df["log_conc"] = np.log10(np.maximum(conc, EPS_CONC))

# ---- Correlations (triple-checked safe handling) ----
dE = pd.to_numeric(df[delta_col], errors="coerce")
tx = pd.to_numeric(df["texture_score"], errors="coerce")

corr_dE_tx = dE.corr(tx)  # Pearson
print(f"Pearson corr(ΔE, texture_score) = {corr_dE_tx:.4f}")

if "concentration" in df.columns:
    conc = pd.to_numeric(df["concentration"], errors="coerce").fillna(0)
    corr_conc_dE = conc.corr(dE)
    corr_conc_tx = conc.corr(tx)
    corr_logconc_dE = df["log_conc"].corr(dE)
    corr_logconc_tx = df["log_conc"].corr(tx)
    print(f"Pearson corr(conc, ΔE)         = {corr_conc_dE:.4f}")
    print(f"Pearson corr(conc, texture)     = {corr_conc_tx:.4f}")
    print(f"Pearson corr(log10(conc), ΔE)   = {corr_logconc_dE:.4f}")
    print(f"Pearson corr(log10(conc), tex)  = {corr_logconc_tx:.4f}")

# ---- Fusion score (interpretable) ----
df["z_deltaE"] = zscore(df[delta_col])
df["z_texture"] = zscore(df["texture_score"])
df["fusion_score"] = df["z_deltaE"] + df["z_texture"]  # w1=w2=1 baseline

# ---- Output merged dataset ----
out_path = "merged_spectral_texture.csv"
df.to_csv(out_path, index=False)
print(f"Saved merged dataset -> {out_path}")

# Quick ranking example (best-case: top suspicious wells)
top = df.sort_values("fusion_score", ascending=False).head(15)[[JOIN_ON, delta_col, "texture_score", "fusion_score"]]
print("\nTop 15 by fusion_score:")
print(top.to_string(index=False))
