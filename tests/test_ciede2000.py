import unittest
import numpy as np

from colorimetry import delta_e2000


class TestCIEDE2000_Golden(unittest.TestCase):
    """
    Golden test pairs from Sharma/Wu/Dalal (Table I).
    We validate that our delta_e2000 call-site matches the published ΔE00 values.
    """

    def test_sharma_table_I_pairs_1_to_10(self):
        # (L1,a1,b1, L2,a2,b2, expected_DE00)
        cases = [
            (50.0000,  2.6772, -79.7751, 50.0000, 0.0000, -82.7485,  2.0425),
            (50.0000,  3.1571, -77.2803, 50.0000, 0.0000, -82.7485,  2.8615),
            (50.0000,  2.8361, -74.0200, 50.0000, 0.0000, -82.7485,  3.4412),
            (50.0000, -1.3802, -84.2814, 50.0000, 0.0000, -82.7485,  1.0000),
            (50.0000, -1.1848, -84.8006, 50.0000, 0.0000, -82.7485,  1.0000),
            (50.0000, -0.9009, -85.5211, 50.0000, 0.0000, -82.7485,  1.0000),
            (50.0000,  0.0000,   0.0000, 50.0000, -1.0000,   2.0000,  2.3669),
            (50.0000, -1.0000,   2.0000, 50.0000,  0.0000,   0.0000,  2.3669),
            (50.0000,  2.4900,  -0.0010, 50.0000, -2.4900,   0.0009,  7.1792),
            (50.0000,  2.4900,  -0.0010, 50.0000, -2.4900,   0.0010,  7.1792),
        ]

        for L1, a1, b1, L2, a2, b2, expected in cases:
            lab1 = np.array([L1, a1, b1], dtype=float)
            lab2 = np.array([L2, a2, b2], dtype=float)

            got = delta_e2000(lab1, lab2)

            # Published values are to 4 decimals; enforce tight tolerance
            self.assertAlmostEqual(got, expected, places=4)


if __name__ == "__main__":
    unittest.main()
