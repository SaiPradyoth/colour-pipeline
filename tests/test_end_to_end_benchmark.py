import json
import numpy as np
import os
import unittest

from pipeline import process_plate


class TestEndToEndBenchmark(unittest.TestCase):
    def test_mini_dataset_matches_expected(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(root, "benchmarks", "mini_dataset", "mini_plate.csv")
        expected_path = os.path.join(root, "benchmarks", "expected", "mini_dataset_results.json")

        df_results, wells, reference_well, blanks, delta_col = process_plate(
            excel_file=csv_path,
            reference_mode="lab",
            lab_target=[100.0, 0.0, 0.0],
            illuminant_key="D65",
            observer_angle_deg=2.0,
            blank_wells=None,
        )

        df_results = df_results.sort_values("Well").reset_index(drop=True)

        actual_rows = df_results.to_dict(orient="records")

        with open(expected_path, "r", encoding="utf-8") as f:
            expected = json.load(f)

        expected_rows = expected["rows"]
        self.assertIn("repeatability", expected["summary"])
        rep = expected["summary"]["repeatability"]
        self.assertIsNotNone(rep)
        self.assertTrue(np.isfinite(rep["deltaE_between_reps"]))

        # Strict shape check
        self.assertEqual(len(actual_rows), len(expected_rows))

        # Strict numerical tolerance per field
        float_fields = ["X", "Y", "Z", "L*", "a*", "b*", delta_col]

        for a, e in zip(actual_rows, expected_rows):
            self.assertEqual(a["Well"], e["Well"])
            for k in float_fields:
                self.assertAlmostEqual(float(a[k]), float(e[k]), places=6)
            self.assertEqual(a["LambdaMax"], e["LambdaMax"])


if __name__ == "__main__":
    unittest.main()
