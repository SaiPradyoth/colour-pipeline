import numpy as np
import colour


def _xy_to_XYZ_100(whitepoint_xy):
    """
    Convert xy whitepoint to XYZ with Y=100 (scale expected by XYZ_to_Lab when XYZ is scaled to 100).
    """
    x, y = float(whitepoint_xy[0]), float(whitepoint_xy[1]); return np.array([100.0 * x / y, 100.0, 100.0 * (1.0 - x - y) / y], dtype=float)


def compute_xyz_lab_from_absorbance(
    absorbance,
    wavelengths,
    domain,
    illum_sd,
    whitepoint=None,
    Y_max=1.0,
    whitepoint_xy=None,
):
    """
    absorbance A(λ) -> transmittance T(λ)=10^(-A(λ)) -> SpectralDistribution -> XYZ -> Lab.

    Accepts whitepoint either as:
    - whitepoint_xy (xy chromaticity), OR
    - whitepoint (xy chromaticity)  [pipeline passes this]
    """
    absorbance = np.asarray(absorbance, dtype=float)
    if absorbance.size == 0:
        raise ValueError("absorbance is empty.")
    
    if not np.isfinite(absorbance).any():
        raise ValueError("absorbance contains no finite values.")
    
    if np.isnan(absorbance).any():
        raise ValueError("absorbance contains NaN values.")
    
    wavelengths = np.asarray(wavelengths, dtype=float)

    # Choose whitepoint source
    if whitepoint_xy is None:
        whitepoint_xy = whitepoint
    if whitepoint_xy is None:
        raise ValueError("whitepoint (xy) must be provided.")

    wp_XYZ_100 = _xy_to_XYZ_100(whitepoint_xy)

    # Absorbance -> Transmittance
    trans = 10 ** (-absorbance)

    # Align input spectrum to the illuminant domain if needed
    if not np.allclose(wavelengths, domain):
        trans = np.interp(domain, wavelengths, trans)

    sd = colour.SpectralDistribution(trans, domain)

    # XYZ under illuminant
    XYZ = colour.sd_to_XYZ(sd, illuminant=illum_sd)

    # Normalize so that perfect transmittance gives Y=100
    XYZ_norm = (XYZ / float(Y_max)) * 100.0

    # Lab using matching-scaled whitepoint
    Lab = colour.XYZ_to_Lab(XYZ_norm, whitepoint_xy)

    return XYZ_norm, Lab


def delta_e2000(lab1, lab2) -> float:
    return float(colour.delta_E(lab1, lab2, method="CIE 2000"))
