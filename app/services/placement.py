"""
placement.py — Finds the optimal (lowest heat) position for a rectangular overlay
               on an intensity map using FFT-based convolution.

Algorithm (O(H·W·log(H·W)) per overlay):
  1. Build a kernel of ones with the same shape as the overlay (oh × ow).
  2. Compute cost_map = fftconvolve(intensity, kernel, mode='valid').
     Each cell (r, c) of cost_map equals the sum of intensity values under the
     overlay if its top-left corner is placed at (c, r).
  3. Optionally add a distance penalty: positions far from the original (origin_x,
     origin_y) are penalised proportionally. Both heat and distance maps are
     normalised to [0, 1] before being combined via distance_weight ∈ [0, 1].
       total_cost = (1 - w) * norm_heat + w * norm_dist
     w=0 → pure heat optimisation (original behaviour).
     w=1 → stay as close to the origin as possible, ignoring heat.
  4. The optimal position is the argmin of total_cost.

Edge case:
  - If the overlay is larger than the heatmap in either dimension a ValueError
    is raised (the caller should convert this to an HTTP 422).
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

    Parameters
    ----------
    intensity:
        2-D float32 array (H × W) produced by heatmap.rgb_to_intensity.
    overlay_width:
        Width of the overlay in pixels.
    overlay_height:
        Height of the overlay in pixels.
    origin_x, origin_y:
        Top-left coordinates of the overlay's original position.  Used as the
        reference point for the distance penalty.  Ignored when distance_weight=0.
    distance_weight:
        Float in [0.0, 1.0] controlling the trade-off between heat avoidance and
        proximity to the original position.
          0.0 → optimise heat only (default, original behaviour).
          1.0 → stay as close to origin as possible, ignoring heat.
        Both cost components are normalised to [0, 1] before combining.

    Returns
    -------
    (x, y, heat_sum)
        x, y     — top-left pixel coordinates (column, row) of the best position.
        heat_sum — raw sum of intensity values under the overlay at that position.

    Raises
    ------
    ValueError
        If the overlay is larger than the intensity map in either dimension.
    """
    map_h, map_w = intensity.shape

    if overlay_height > map_h or overlay_width > map_w:
        raise ValueError(
            f"Overlay ({overlay_width}×{overlay_height}) is larger than the "
            f"heatmap ({map_w}×{map_h})."
        )

    # Kernel: rectangle of ones matching the overlay size
    kernel = np.ones((overlay_height, overlay_width), dtype=np.float32)

    # FFT convolution — mode='valid' gives shape (map_h - oh + 1, map_w - ow + 1)
    # Clip small negative values produced by floating-point noise in FFT.
    heat_map = np.clip(fftconvolve(intensity, kernel, mode="valid"), 0.0, None)

    if distance_weight > 0.0:
        rows, cols = heat_map.shape

        # Normalise heat to [0, 1]
        heat_max = heat_map.max()
        norm_heat = heat_map / heat_max if heat_max > 0.0 else np.zeros_like(heat_map)

        # Build distance map: each cell (r, c) → Euclidean distance to origin
        r_idx = np.arange(rows, dtype=np.float32)
        c_idx = np.arange(cols, dtype=np.float32)
        dist_map = np.sqrt(
            (c_idx[None, :] - origin_x) ** 2 + (r_idx[:, None] - origin_y) ** 2
        )

        # Normalise distance to [0, 1]
        dist_max = dist_map.max()
        norm_dist = dist_map / dist_max if dist_max > 0.0 else np.zeros_like(dist_map)

        # Weighted combination
        total_cost = (1.0 - distance_weight) * norm_heat + distance_weight * norm_dist
    else:
        total_cost = heat_map

    # Find position with minimum total cost
    flat_idx = np.argmin(total_cost)
    min_y, min_x = np.unravel_index(flat_idx, total_cost.shape)

    # Report the raw heat sum at the chosen position (not the combined cost)
    heat_sum = float(heat_map[min_y, min_x])

    return int(min_x), int(min_y), heat_sum


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
