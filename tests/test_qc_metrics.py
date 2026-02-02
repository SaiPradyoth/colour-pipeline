import json
import os
import subprocess
import sys
import unittest


class TestQCMetrics(unittest.TestCase):
    def test_qc_labels_schema(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        labels_path = os.path.join(root, "benchmarks", "qc_labels.json")
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)

        self.assertIn("mini_dataset_v1", labels)
        self.assertIn("expected_pass_wells", labels["mini_dataset_v1"])
        self.assertIn("expected_fail_wells", labels["mini_dataset_v1"])

    def test_qc_precision_recall(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Run benchmarks to generate current output
        subprocess.check_call([sys.executable, os.path.join(root, "scripts", "run_benchmarks.py")])

        out_path = os.path.join(root, "benchmarks", "out", "mini_dataset_results.json")
        with open(out_path, "r", encoding="utf-8") as f:
            out = json.load(f)

        labels_path = os.path.join(root, "benchmarks", "qc_labels.json")
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)["mini_dataset_v1"]

        expected_fail = set(labels["expected_fail_wells"])
        expected_pass = set(labels["expected_pass_wells"])

        flagged = {
            w for w, reasons in out.get("qc_flags_by_well", {}).items()
            if ("absorbance_out_of_range" in reasons) or ("absorbance_non_finite" in reasons)
        }
        all_wells = {r["Well"] for r in out["rows"]}

        # Confusion matrix
        tp = len(flagged & expected_fail)
        fp = len(flagged & expected_pass)
        fn = len((expected_fail & all_wells) - flagged)

        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0

        # In this benchmark, A4 must be caught, and A1/A2/A3 must not be flagged.
        self.assertEqual(tp, 1)
        self.assertEqual(fp, 0)
        self.assertEqual(fn, 0)
        self.assertEqual(precision, 1.0)
        self.assertEqual(recall, 1.0)


if __name__ == "__main__":
    unittest.main()
