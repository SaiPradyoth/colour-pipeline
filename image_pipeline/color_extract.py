import cv2
import numpy as np
from typing import Dict


def extract_hsv_hsl(image_path: str) -> Dict[str, float]:
    """
    Extract mean HSV and HSL values from an image.

    Parameters
    ----------
    image_path : str
        Path to image file

    Returns
    -------
    dict
        {
          "H_mean": float,
          "S_mean": float,
          "V_mean": float,
          "HSL_H_mean": float,
          "HSL_S_mean": float,
          "HSL_L_mean": float
        }
    """

    # Load image (BGR)
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")

    # Convert to RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Convert to HSV
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    # Convert to HSL (OpenCV uses HLS ordering)
    hls = cv2.cvtColor(rgb, cv2.COLOR_RGB2HLS)

    # Flatten pixels
    hsv_pixels = hsv.reshape(-1, 3)
    hls_pixels = hls.reshape(-1, 3)

    # Compute robust means (float)
    hsv_mean = np.mean(hsv_pixels, axis=0)
    hls_mean = np.mean(hls_pixels, axis=0)

    return {
        "HSV_H_mean": float(hsv_mean[0]),
        "HSV_S_mean": float(hsv_mean[1]),
        "HSV_V_mean": float(hsv_mean[2]),
        "HSL_H_mean": float(hls_mean[0]),
        "HSL_L_mean": float(hls_mean[1]),
        "HSL_S_mean": float(hls_mean[2]),
    }
