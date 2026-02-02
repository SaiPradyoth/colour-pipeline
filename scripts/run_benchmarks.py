import os
import sys
import json
from datetime import datetime

# Ensure repo root is on sys.path BEFORE local imports
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

from colorimetry import delta_e2000
from pipeline import process_plate
from benchmarks.uncertainty import estimate_lab_uncertainty
from benchmarks.qc import qc_flags_for_rows


def _as_float(x):
    if x is None:
        return None
    try:
        if isinstance(x, (np.ndarray,)):
            return [float(v) for v in x.tolist()]
        return float(x)
    except Exception:
        return x


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(root, "benchmarks", "mini_dataset", "mini_plate.csv")

    df_results, wells, reference_well, blanks, delta_col = process_plate(
        excel_file=csv_path,
        reference_mode="lab",
        lab_target=[100.0, 0.0, 0.0],
        illuminant_key="D65",
        observer_angle_deg=2.0,
        blank_wells=None,
    )

    # Keep stable ordering
    df_results = df_results.sort_values("Well").reset_index(drop=True)
    # --- Uncertainty proxy (Monte Carlo sensitivity) ---
    # We re-run uncertainty on the same mini dataset using the same pipeline parameters.
    # This does NOT require instrument data; it quantifies numerical/measurement-noise sensitivity.
    import colour

    wavelengths = np.arange(360, 781, 1, dtype=float)
    interval = wavelengths[1] - wavelengths[0]
    shape = colour.SpectralShape(wavelengths.min(), wavelengths.max(), interval)

    illum_key = "D65"
    illum_sd = colour.SDS_ILLUMINANTS[illum_key].copy().align(shape)
    domain = illum_sd.domain

    observer = "CIE 1931 2 Degree Standard Observer"
    whitepoint_xy = colour.CCS_ILLUMINANTS[observer][illum_key]

    ones = np.ones(len(domain), dtype=float)
    sd_ones = colour.SpectralDistribution(ones, domain)
    XYZ_white = colour.sd_to_XYZ(sd_ones, illuminant=illum_sd)
    Y_max = float(XYZ_white[1])

    raw = np.genfromtxt(csv_path, delimiter=",", names=True)
    abs_A1 = raw["A1"].astype(float)
    abs_A3 = raw["A3"].astype(float)
    abs_A2 = raw["A2"].astype(float)
    abs_A4 = raw["A4"].astype(float)

    unc = {}
    for well, absorb in [("A1", abs_A1), ("A3", abs_A3), ("A2", abs_A2), ("A4", abs_A4)]:
        # Skip uncertainty if absorbance is entirely non-finite (e.g., NaN-only QC sentinel well)
        if not np.isfinite(np.asarray(absorb, dtype=float)).any():
            unc[well] = {"Lab_std": None, "DeltaE_std": None}
            continue

        lab_mean, lab_std, de_std = estimate_lab_uncertainty(
            absorbance=absorb,
            wavelengths=domain,
            domain=domain,
            illum_sd=illum_sd,
            whitepoint_xy=whitepoint_xy,
            Y_max=Y_max,
            noise_sigma=0.002,
            n=200,
            seed=123,
        )
        unc[well] = {
            "Lab_std": [float(lab_std[0]), float(lab_std[1]), float(lab_std[2])],
            "DeltaE_std": float(de_std),
        }

    # Attach to rows
    rows = df_results.to_dict(orient="records")
    # Attach absorbance sanity stats (min/max) for QC (from raw CSV columns)
    raw = np.genfromtxt(csv_path, delimiter=",", names=True)
    for r in rows:
        w = r["Well"]
        if w in raw.dtype.names:
            a = np.asarray(raw[w], dtype=float)
            finite = a[np.isfinite(a)]
            if finite.size:
                r["Abs_min"] = float(finite.min())
                r["Abs_max"] = float(finite.max())
            else:
                r["Abs_min"] = None
                r["Abs_max"] = None

    for r in rows:
        u = unc.get(r["Well"])
        if u:
            r.update(u)
    # --- Repeatability (A1 vs A1_rep) ---
    def _find_row(well):
        for rr in rows:
            if rr["Well"] == well:
                return rr
        return None

    r1 = _find_row("A1")
    r2 = _find_row("A3")
    repeatability = None
    if r1 and r2:
        lab1 = np.array([r1["L*"], r1["a*"], r1["b*"]], dtype=float)
        lab2 = np.array([r2["L*"], r2["a*"], r2["b*"]], dtype=float)
        repeatability = {
            "pair": ["A1", "A3"],
            "deltaE_between_reps": float(delta_e2000(lab1, lab2)),
            "Lab_diff": [float(lab2[0]-lab1[0]), float(lab2[1]-lab1[1]), float(lab2[2]-lab1[2])],
        }

    # --- QC flags (uncertainty-aware, repeatability-aware) ---
    flags_by_well, qc_summary = qc_flags_for_rows(
        rows,
        delta_col=delta_col,
        repeatability=repeatability,
        k=3.0,
    )

    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "benchmark": "mini_dataset_v1",
        "delta_col": delta_col,
        "rows": rows,
        "summary": {
        "wells": wells,
        "reference_well": reference_well,
        "repeatability": repeatability,
        "qc_summary": qc_summary,
        },
        "qc_flags_by_well": flags_by_well,

    }

    out_dir = os.path.join(root, "benchmarks", "out")
    os.makedirs(out_dir, exist_ok=True)

    out_path = os.path.join(out_dir, "mini_dataset_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
