import unittest
import numpy as np
import colour

from colorimetry import compute_xyz_lab_from_absorbance, delta_e2000


class TestEdgeCases(unittest.TestCase):
    @staticmethod
    def _setup():
        wavelengths = np.arange(400, 701, 1, dtype=float)
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

        return wavelengths, domain, illum_sd, whitepoint_xy, Y_max

    def test_all_nan_absorbance_raises(self):
        wavelengths, domain, illum_sd, whitepoint_xy, Y_max = self._setup()
        absorb = np.full(len(domain), np.nan, dtype=float)

        with self.assertRaises(Exception):
            compute_xyz_lab_from_absorbance(
                absorbance=absorb,
                wavelengths=domain,
                domain=domain,
                illum_sd=illum_sd,
                whitepoint_xy=whitepoint_xy,
                Y_max=Y_max,
            )

    def test_extreme_absorbance_is_finite(self):
        wavelengths, domain, illum_sd, whitepoint_xy, Y_max = self._setup()

        # Very high absorbance -> transmittance ~ 0
        absorb = np.full(len(domain), 6.0, dtype=float)

        XYZ, Lab = compute_xyz_lab_from_absorbance(
            absorbance=absorb,
            wavelengths=domain,
            domain=domain,
            illum_sd=illum_sd,
            whitepoint_xy=whitepoint_xy,
            Y_max=Y_max,
        )

        self.assertTrue(np.isfinite(XYZ).all())
        self.assertTrue(np.isfinite(Lab).all())
        self.assertTrue(0.0 <= float(Lab[0]) <= 5.0)  # should be near black

    def test_delta_e_symmetry(self):
        lab1 = np.array([50.0, 2.0, -30.0], dtype=float)
        lab2 = np.array([51.0, 3.0, -29.0], dtype=float)

        d12 = delta_e2000(lab1, lab2)
        d21 = delta_e2000(lab2, lab1)

        self.assertAlmostEqual(d12, d21, places=6)

    def test_small_noise_stability(self):
        # Small noise in absorbance should not cause wild ΔE jumps
        wavelengths, domain, illum_sd, whitepoint_xy, Y_max = self._setup()

        base_absorb = np.zeros(len(domain), dtype=float)
        XYZ0, Lab0 = compute_xyz_lab_from_absorbance(
            absorbance=base_absorb,
            wavelengths=domain,
            domain=domain,
            illum_sd=illum_sd,
            whitepoint_xy=whitepoint_xy,
            Y_max=Y_max,
        )

        rng = np.random.default_rng(123)
        # 200 trials of tiny absorbance noise
        deltas = []
        for _ in range(200):
            noise = rng.normal(loc=0.0, scale=0.002, size=len(domain))
            test_absorb = np.clip(base_absorb + noise, 0.0, None)

            _, Lab1 = compute_xyz_lab_from_absorbance(
                absorbance=test_absorb,
                wavelengths=domain,
                domain=domain,
                illum_sd=illum_sd,
                whitepoint_xy=whitepoint_xy,
                Y_max=Y_max,
            )
            deltas.append(delta_e2000(Lab0, Lab1))

        deltas = np.array(deltas, dtype=float)

        self.assertTrue(np.isfinite(deltas).all())
