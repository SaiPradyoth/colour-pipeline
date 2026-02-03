"""
image_analysis.py
-----------------
High-level image analysis for plate-based color data.

Responsibilities:
- Validate well IDs for a plate type (48/96/384)
- Extract HSV or HSL channel means from per-well images (via color_extract.py)
- Optionally compute deltas vs a reference well
"""

from typing import Dict, List, Optional, Union
from pathlib import Path

from .color_extract import extract_hsv_hsl


# -------------------------
# Plate utilities
# -------------------------

def generate_plate_wells(plate_type: str = "96") -> List[str]:
    """
    Generate ordered well IDs for a plate.
    """
    plate_type = str(plate_type or "96").strip()
    if plate_type == "48":
        rows, cols = "ABCDEF", range(1, 9)
    elif plate_type == "384":
        rows, cols = "ABCDEFGHIJKLMNOP", range(1, 25)
    else:  # default 96
        rows, cols = "ABCDEFGH", range(1, 13)

    return [f"{r}{c}" for r in rows for c in cols]


# -------------------------
# Core analysis
# -------------------------

def analyze_plate_images(
    images: Dict[str, Union[str, Path]],
    plate_type: str = "96",
    color_space: str = "HSV",
    reference_well: Optional[str] = None,
) -> Dict[str, Dict]:
    """
    Analyze a set of per-well images.

    Parameters
    ----------
    images : dict
        Mapping of well_id -> image_path (e.g., {"A1": "tmp/A1.jpg", ...})
    plate_type : str
        48 | 96 | 384
    color_space : str
        "HSV" or "HSL"
    reference_well : str, optional
        Well ID to use as color reference (computes ΔH/ΔS/ΔV or ΔL)

    Returns
    -------
    dict
        { well_id : {H, S, V/L, ΔH, ΔS, ΔV/L (if reference provided)} }
    """
    wells_allowed = set(generate_plate_wells(plate_type))
    results: Dict[str, Dict] = {}
    mode = (color_space or "HSV").upper()

    # Extract per-well mean channels
    for well, img_path in (images or {}).items():
        if not well:
            continue
        well = str(well).strip()
        if well not in wells_allowed:
            continue

        stats = extract_hsv_hsl(str(img_path))

        if mode == "HSL":
            results[well] = {
                "H": float(stats["HSL_H_mean"]),
                "S": float(stats["HSL_S_mean"]),
                "L": float(stats["HSL_L_mean"]),
            }
        else:  # HSV default
            results[well] = {
                "H": float(stats["HSV_H_mean"]),
                "S": float(stats["HSV_S_mean"]),
                "V": float(stats["HSV_V_mean"]),
            }

    # Reference deltas
    if reference_well:
        ref_well = str(reference_well).strip()
        if ref_well in results:
            ref = results[ref_well]
            for well, vals in results.items():
                if mode == "HSL":
                    vals["ΔH"] = vals["H"] - ref["H"]
                    vals["ΔS"] = vals["S"] - ref["S"]
                    vals["ΔL"] = vals["L"] - ref["L"]
                else:
                    vals["ΔH"] = vals["H"] - ref["H"]
                    vals["ΔS"] = vals["S"] - ref["S"]
                    vals["ΔV"] = vals["V"] - ref["V"]

    return results


# -------------------------
# Convenience wrapper
# -------------------------

def analyze_single_image(
    image_path: Union[str, Path],
    color_space: str = "HSV",
) -> Dict[str, float]:
    """
    Analyze a single image (no plate context). Returns channel means.
    """
    stats = extract_hsv_hsl(str(image_path))
    mode = (color_space or "HSV").upper()

    if mode == "HSL":
        return {
            "H": float(stats["HSL_H_mean"]),
            "S": float(stats["HSL_S_mean"]),
            "L": float(stats["HSL_L_mean"]),
        }

    return {
        "H": float(stats["HSV_H_mean"]),
        "S": float(stats["HSV_S_mean"]),
        "V": float(stats["HSV_V_mean"]),
    }
