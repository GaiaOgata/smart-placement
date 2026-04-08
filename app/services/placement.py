"""
placement.py — Finds the optimal (lowest heat) position for a rectangular overlay
               on an intensity map using a quadrant-based strategy.

Algorithm:
  1. Divide the intensity map into 4 equal quadrants (top-left, top-right,
     bottom-left, bottom-right).
  2. Compute the total heat sum of each quadrant and select the one with the
     lowest sum.
  3. Within the selected quadrant, use FFT convolution to build a cost map
     where each cell equals the sum of intensity values under the overlay when
     its top-left corner is placed at that position.
  4. The optimal position is the argmin of that cost map, converted back to
     global image coordinates.

Edge cases:
  - If the overlay is larger than the heatmap in either dimension a ValueError
    is raised (the caller should convert this to an HTTP 422).
  - If the overlay is larger than the selected quadrant in either dimension a
    ValueError is raised.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve


def find_optimal_position(
    intensity: np.ndarray,
    overlay_width: int,
    overlay_height: int,
    origin_x: int = 0,
    origin_y: int = 0,
    distance_weight: float = 0.0,
) -> tuple[int, int, float]:
    """Return the top-left (x, y) and heat sum for the optimal overlay position.

    The heatmap is divided into 4 equal quadrants.  The quadrant with the
    lowest total heat is selected, and within it the position that minimises
    the heat sum under the overlay is returned.

    Parameters
    ----------
    intensity:
        2-D float32 array (H × W) produced by heatmap.rgb_to_intensity.
    overlay_width:
        Width of the overlay in pixels.
    overlay_height:
        Height of the overlay in pixels.
    origin_x, origin_y:
        Kept for API compatibility; not used in this algorithm.
    distance_weight:
        Kept for API compatibility; not used in this algorithm.

    Returns
    -------
    (x, y, heat_sum)
        x, y     — top-left pixel coordinates (column, row) of the best position.
        heat_sum — raw sum of intensity values under the overlay at that position.

    Raises
    ------
    ValueError
        If the overlay is larger than the intensity map or the selected quadrant.
    """
    map_h, map_w = intensity.shape

    if overlay_height > map_h or overlay_width > map_w:
        raise ValueError(
            f"Overlay ({overlay_width}×{overlay_height}) is larger than the "
            f"heatmap ({map_w}×{map_h})."
        )

    # --- Step 1: divide the map into 4 equal quadrants ---
    mid_h = map_h // 2
    mid_w = map_w // 2

    # Each entry: (row_start, col_start, row_end, col_end)
    quadrants = [
        (0,     0,     mid_h,  mid_w),   # top-left
        (0,     mid_w, mid_h,  map_w),   # top-right
        (mid_h, 0,     map_h,  mid_w),   # bottom-left
        (mid_h, mid_w, map_h,  map_w),   # bottom-right
    ]

    # --- Step 2: pick the quadrant with the lowest total heat ---
    quad_sums = [
        float(intensity[r0:r1, c0:c1].sum())
        for (r0, c0, r1, c1) in quadrants
    ]
    best_idx = int(np.argmin(quad_sums))
    r0, c0, r1, c1 = quadrants[best_idx]

    quad_intensity = intensity[r0:r1, c0:c1]
    quad_h, quad_w = quad_intensity.shape

    if overlay_height > quad_h or overlay_width > quad_w:
        raise ValueError(
            f"Overlay ({overlay_width}×{overlay_height}) is larger than the "
            f"selected quadrant ({quad_w}×{quad_h})."
        )

    # --- Step 3: find the best position inside the quadrant via FFT convolution ---
    kernel = np.ones((overlay_height, overlay_width), dtype=np.float32)
    heat_map = np.clip(fftconvolve(quad_intensity, kernel, mode="valid"), 0.0, None)

    # --- Step 4: argmin → global coordinates ---
    flat_idx = np.argmin(heat_map)
    local_y, local_x = np.unravel_index(flat_idx, heat_map.shape)

    # Clamp to ensure the overlay never exceeds image boundaries.
    best_x = int(np.clip(local_x + c0, 0, map_w - overlay_width))
    best_y = int(np.clip(local_y + r0, 0, map_h - overlay_height))
    heat_sum = float(heat_map[local_y, local_x])

    return best_x, best_y, heat_sum


def compute_heat_sum_at(
    intensity: np.ndarray,
    x: int,
    y: int,
    overlay_width: int,
    overlay_height: int,
) -> float:
    """Compute the heat sum under an overlay placed at (x, y).

    Clamps the region to the intensity map boundaries, so partial overlaps are
    handled gracefully.

    Parameters
    ----------
    intensity:
        2-D float32 array (H × W).
    x, y:
        Top-left pixel coordinates.
    overlay_width, overlay_height:
        Size of the overlay.

    Returns
    -------
    float
        Sum of intensity values in the covered region.
    """
    map_h, map_w = intensity.shape
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(map_w, x + overlay_width)
    y1 = min(map_h, y + overlay_height)

    if x0 >= x1 or y0 >= y1:
        return 0.0

    return float(intensity[y0:y1, x0:x1].sum())
