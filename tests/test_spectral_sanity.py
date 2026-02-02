import unittest
import numpy as np
import colour

from colorimetry import compute_xyz_lab_from_absorbance


class TestSpectralToLabSanity(unittest.TestCase):
    def test_zero_absorbance_is_whiteish(self):
        # Build a domain/illuminant similar to the pipeline approach
        wavelengths = np.arange(360, 781, 1, dtype=float)
        interval = wavelengths[1] - wavelengths[0]
        shape = colour.SpectralShape(wavelengths.min(), wavelengths.max(), interval)

        illum_key = "D65"
        illum_sd = colour.SDS_ILLUMINANTS[illum_key].copy().align(shape)
        domain = illum_sd.domain

        # Whitepoint as xy (what colour.CCS_ILLUMINANTS provides)
        observer = "CIE 1931 2 Degree Standard Observer"
        whitepoint_xy = colour.CCS_ILLUMINANTS[observer][illum_key]

        # Define Y_max self-consistently using a flat transmittance spectrum under the same illuminant
        ones = np.ones(len(domain), dtype=float)
        sd_ones = colour.SpectralDistribution(ones, domain)
        XYZ_white = colour.sd_to_XYZ(sd_ones, illuminant=illum_sd)
        Y_max = float(XYZ_white[1])

        # Absorbance 0 => transmittance 1
        absorb = np.zeros(len(domain), dtype=float)

        XYZ, Lab = compute_xyz_lab_from_absorbance(
            absorbance=absorb,
            wavelengths=domain,
            domain=domain,
            illum_sd=illum_sd,
            whitepoint_xy=whitepoint_xy,
            Y_max=Y_max,
        )

        # Sanity: finite outputs
        self.assertTrue(np.isfinite(XYZ).all())
        self.assertTrue(np.isfinite(Lab).all())

        # "White-ish": L* high, a*/b* near 0
        self.assertAlmostEqual(float(XYZ[1]), 100.0, places=3)
        xy = colour.XYZ_to_xy(XYZ)
        self.assertAlmostEqual(float(xy[0]), float(whitepoint_xy[0]), places=3)
        self.assertAlmostEqual(float(xy[1]), float(whitepoint_xy[1]), places=3)
        self.assertAlmostEqual(float(Lab[1]), 0.0, places=1)
        self.assertAlmostEqual(float(Lab[2]), 0.0, places=0)


if __name__ == "__main__":
    unittest.main()
