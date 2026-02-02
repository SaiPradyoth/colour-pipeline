import numpy as np


def qc_flags_for_rows(rows, delta_col, repeatability=None, k=3.0):
    """
    Returns:
      flags_by_well: {well: [reasons]}
      summary: {n_flagged, reasons_count, repeatability_flag}
    """
    flags_by_well = {}
    reasons_count = {}

    def add(well, reason):
        flags_by_well.setdefault(well, []).append(reason)
        reasons_count[reason] = reasons_count.get(reason, 0) + 1

    for r in rows:
        w = r["Well"]

        # Absorbance range sanity: typical plate absorbance should be within [0, 3] (configurable)
        a_min = r.get("Abs_min")
        a_max = r.get("Abs_max")
        if a_min is None or a_max is None:
            add(w, "absorbance_non_finite")
        else:
            if float(a_min) < 0.0 or float(a_max) > 3.0:
                add(w, "absorbance_out_of_range")

        # non-finite check (XYZ/Lab/ΔE)
        vals = [
            r.get("X"), r.get("Y"), r.get("Z"),
            r.get("L*"), r.get("a*"), r.get("b*"),
            r.get(delta_col),
        ]
        if not np.isfinite(np.array(vals, dtype=float)).all():
            add(w, "non_finite")
            continue

        # Lab bounds
        if not (0.0 <= float(r["L*"]) <= 100.0):
            add(w, "L_out_of_range")

        # Target / reference error threshold:
        # - uncertainty-aware when available
        # - hard floor threshold so we still flag even if uncertainty is missing
        hard_thresh = 2.0  # conservative "visibly different" threshold in ΔE00

        sigma = None
        if r.get("DeltaE_std") is not None:
            try:
                sigma = float(r["DeltaE_std"])
            except Exception:
                sigma = None

        unc_thresh = (k * sigma) if (sigma is not None and sigma > 0) else None
        thresh = max(hard_thresh, unc_thresh) if unc_thresh is not None else hard_thresh

        if float(r[delta_col]) > thresh:
            add(w, "deltaE_exceeds_threshold")

    # repeatability flag
    repeatability_flag = None
    if repeatability and repeatability.get("deltaE_between_reps") is not None:
        de_rep = float(repeatability["deltaE_between_reps"])
        # very conservative default; later we can use sigma from baseline
        if de_rep > 0.5:
            repeatability_flag = {"flag": True, "deltaE": de_rep, "threshold": 0.5}
        else:
            repeatability_flag = {"flag": False, "deltaE": de_rep, "threshold": 0.5}

    summary = {
        "n_flagged": len(flags_by_well),
        "reasons_count": reasons_count,
        "repeatability": repeatability_flag,
    }
    return flags_by_well, summary
