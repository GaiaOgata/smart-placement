"""
heatmap.py — Converts an RGB heatmap image into a float32 intensity matrix.

Convention:
  - "hot" colours (red, ~hue 0°)   → intensity ≈ 1.0
  - "cold" colours (blue, ~hue 240°) → intensity ≈ 0.0
  - Black, white, and transparent pixels → intensity 0.0

Algorithm:
  1. Convert image to RGBA so we can detect transparency.
  2. Convert RGB channels to HSV with Pillow.
  3. Extract the Hue channel (0–255 in Pillow, representing 0°–360°).
  4. Map hue to intensity: intensity = 1.0 - (hue_degrees / 240.0), clamped to [0, 1].
     Hues above 240° (magentas/pinks) are also treated as hot (clamped to 1).
  5. Zero-out pixels that are transparent, black, or white (achromatic).
"""

from __future__ import annotations

import numpy as np
from PIL import Image


# Saturation and value thresholds (Pillow uses 0–255 scale for S and V)
_SATURATION_THRESHOLD = 30   # pixels with S < threshold are achromatic (grey/white)
_VALUE_THRESHOLD_LOW  = 20   # very dark → black
_ALPHA_THRESHOLD      = 10   # pixels with alpha < threshold are transparent


def rgb_to_intensity(image: Image.Image) -> np.ndarray:
    """Convert a PIL heatmap image to a 2-D float32 intensity matrix (H × W).

    Parameters
    ----------
    image:
        Any PIL image (RGB, RGBA, L, P …).  It is converted internally.

    Returns
    -------
    np.ndarray
        float32 array with shape (height, width), values in [0.0, 1.0].
        0.0 = cold / transparent / achromatic, 1.0 = hot.
    """
    # --- 1. Ensure we have an RGBA image so we can read alpha ---
    rgba = image.convert("RGBA")
    alpha_arr = np.array(rgba)[:, :, 3]  # shape (H, W), uint8

    # --- 2. Convert to HSV ---
    rgb = rgba.convert("RGB")
    hsv = rgb.convert("HSV")          # Pillow HSV: H in [0,255], S in [0,255], V in [0,255]
    hsv_arr = np.array(hsv, dtype=np.float32)  # (H, W, 3)

    hue_raw = hsv_arr[:, :, 0]   # 0–255 → represents 0°–360°
    sat     = hsv_arr[:, :, 1]   # 0–255
    val     = hsv_arr[:, :, 2]   # 0–255

    # --- 3. Convert Pillow hue (0–255) to degrees (0°–360°) ---
    hue_degrees = hue_raw * (360.0 / 255.0)

    # --- 4. Compute intensity: intensity = 1 - hue / 240, clamped [0, 1] ---
    intensity = 1.0 - (hue_degrees / 240.0)
    intensity = np.clip(intensity, 0.0, 1.0)

    # --- 5. Zero-out achromatic and transparent pixels ---
    # "White" is low-saturation AND high-value; "black" is low-value.
    # A highly saturated pixel (e.g. pure red) should NOT be zeroed even if V=255.
    achromatic  = (sat < _SATURATION_THRESHOLD)
    dark        = (val < _VALUE_THRESHOLD_LOW)
    transparent = (alpha_arr < _ALPHA_THRESHOLD)

    mask_zero = achromatic | dark | transparent
    intensity[mask_zero] = 0.0

    return intensity.astype(np.float32)
