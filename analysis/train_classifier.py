# =====================================================
# analysis/train_classifier.py
# Purpose: train & evaluate classifier on ΔE + HSV features
# Stateless: NO disk I/O
# =====================================================

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

LABEL_COL = "is_positive"


def train_classifier(df: pd.DataFrame, delta_col: str):
    """
    Expects:
      - df: merged dataframe from fusion_qc
      - delta_col: name of ΔE column (e.g. 'DeltaE00')
      - df[LABEL_COL] ∈ {0,1}

    Returns:
      - dict with AUC per fold and mean AUC
    """

    if LABEL_COL not in df.columns:
        raise ValueError(f"Missing label column '{LABEL_COL}' (0/1 required).")

    if delta_col not in df.columns:
        raise ValueError(f"Missing deltaE column '{delta_col}'.")

    X = df[[delta_col, "texture_score"]].apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(df[LABEL_COL], errors="coerce")

    mask = X.notna().all(axis=1) & y.notna()
    X = X[mask]
    y = y[mask].astype(int)

    if len(y.unique()) < 2:
        raise ValueError("Need both positive and negative samples for training.")

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000))
    ])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    auc = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")

    return {
        "auc_per_fold": np.round(auc, 3).tolist(),
        "mean_auc": float(np.mean(auc)),
        "n_samples": int(len(y)),
    }
