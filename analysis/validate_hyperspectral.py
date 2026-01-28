# analysis/validate_hyperspectral.py

import numpy as np
import pandas as pd
from flask import jsonify

@app.route("/validate_hyperspectral")
def validate_hyperspectral():
    try:
        # Load hyperspectral plate dataframe (you already have this logic)
        df = load_hyperspectral_plate_df()  # <-- your existing loader

        # Find CV columns
        cv_cols = [c for c in df.columns if c.lower().endswith("_cv")]
        if not cv_cols:
            return jsonify({
                "status": "warn",
                "message": "No CV columns found in hyperspectral data"
            })

        cvs = df[cv_cols].to_numpy().flatten()
        cvs = cvs[np.isfinite(cvs)]

        stats = {
            "min_cv": float(np.min(cvs)),
            "max_cv": float(np.max(cvs)),
            "mean_cv": float(np.mean(cvs)),
            "stable_pct": float((cvs < 10).mean() * 100),
            "moderate_pct": float(((cvs >= 10) & (cvs < 20)).mean() * 100),
            "unstable_pct": float((cvs >= 20).mean() * 100),
        }

        return jsonify({
            "status": "ok",
            "stats": stats
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
