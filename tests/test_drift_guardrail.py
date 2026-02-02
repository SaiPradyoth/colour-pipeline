import os
import subprocess
import sys
import unittest


class TestDriftGuardrail(unittest.TestCase):
    def test_drift_check_passes(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Ensure current benchmark exists
        subprocess.check_call([sys.executable, os.path.join(root, "scripts", "run_benchmarks.py")])
        # Drift check must pass
        subprocess.check_call([sys.executable, os.path.join(root, "scripts", "check_drift.py")])


if __name__ == "__main__":
    unittest.main()
