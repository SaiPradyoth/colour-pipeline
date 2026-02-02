import numpy as np
from colorimetry import compute_xyz_lab_from_absorbance, delta_e2000


def estimate_lab_uncertainty(
    absorbance,
    wavelengths,
    domain,
    illum_sd,
    whitepoint_xy,
    Y_max,
    noise_sigma=0.002,
    n=200,
    seed=123,
):
    """
    Returns (Lab_mean, Lab_std, deltaE_std_vs_mean)
    """
    absorbance = np.asarray(absorbance, dtype=float)
    rng = np.random.default_rng(seed)

    labs = []
    for _ in range(n):
        noise = rng.normal(0.0, noise_sigma, size=absorbance.size)
        a = np.clip(absorbance + noise, 0.0, None)
        _, Lab = compute_xyz_lab_from_absorbance(
            absorbance=a,
            wavelengths=wavelengths,
            domain=domain,
            illum_sd=illum_sd,
            whitepoint_xy=whitepoint_xy,
            Y_max=Y_max,
        )
        labs.append(Lab)

    labs = np.asarray(labs, dtype=float)
    lab_mean = np.mean(labs, axis=0)
    lab_std = np.std(labs, axis=0)

    # ΔE variability around the mean (single number)
    deltas = np.array([delta_e2000(lab_mean, lab_i) for lab_i in labs], dtype=float)
    de_std = float(np.std(deltas))

    return lab_mean, lab_std, de_std
