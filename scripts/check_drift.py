import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from colorimetry import delta_e2000


def _load_rows(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = {r["Well"]: r for r in data["rows"]}
    return data, rows


def main():
    root = ROOT
    baseline_path = os.path.join(root, "benchmarks", "baselines", "mini_dataset_baseline.json")
    current_path = os.path.join(root, "benchmarks", "out", "mini_dataset_results.json")

    if not os.path.exists(baseline_path):
        raise FileNotFoundError(f"Baseline missing: {baseline_path}")
    if not os.path.exists(current_path):
        raise FileNotFoundError(f"Current output missing: {current_path} (run scripts/run_benchmarks.py first)")

    base_data, base_rows = _load_rows(baseline_path)
    cur_data, cur_rows = _load_rows(current_path)

    controls = ["A1", "A3"]  # control + technical replicate

    drifts = []
    for w in controls:
        if w not in base_rows or w not in cur_rows:
            continue
        b = base_rows[w]
        c = cur_rows[w]

        lab_b = [b["L*"], b["a*"], b["b*"]]
        lab_c = [c["L*"], c["a*"], c["b*"]]

        drift_de = float(delta_e2000(lab_b, lab_c))
        drifts.append((w, drift_de))

    # Threshold rule: baseline uncertainty as sigma proxy if present
    # Flag if drift > k*sigma, with k=3 by default (3-sigma rule).
    k = 3.0
    flags = []
    for w, drift_de in drifts:
        sigma = None
        if "DeltaE_std" in base_rows[w]:
            sigma = float(base_rows[w]["DeltaE_std"])
        thresh = (k * sigma) if (sigma is not None and sigma > 0) else 0.5  # fallback
        if drift_de > thresh:
            flags.append({"well": w, "drift_deltaE": drift_de, "threshold": thresh})

    print("Drift summary")
    for w, d in drifts:
        print(f"  {w}: ΔE drift = {d:.6f}")

    if flags:
        print("\nFAIL: Drift exceeded thresholds")
        for f in flags:
            print(f"  {f['well']}: drift {f['drift_deltaE']:.6f} > thresh {f['threshold']:.6f}")
        raise SystemExit(2)

    print("\nOK: Drift within thresholds")


if __name__ == "__main__":
    main()
