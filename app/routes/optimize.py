"""
optimize.py — POST /api/optimize endpoint.

Accepts multipart/form-data with:
  - heatmap   : one image file (PNG/JPG/…)
  - overlays  : 1–10 image files
  - metadata  : JSON string — list of {"id": str, "x": int, "y": int}

Returns JSON:
  {
    "results": [
      {
        "id": "img1",
        "original":  {"x": 100, "y": 200},
        "optimized": {"x": 42,  "y": 315},
        "original_heat_sum":  185432.0,
        "optimized_heat_sum": 2104.0
      },
      ...
    ]
  }
"""

from __future__ import annotations

import json

from flask import Blueprint, current_app, jsonify, request

from app.services.heatmap import rgb_to_intensity
from app.services.placement import compute_heat_sum_at, find_optimal_position
from app.utils.image_utils import image_size, load_image

optimize_bp = Blueprint("optimize", __name__)


@optimize_bp.route("/optimize", methods=["POST"])
def optimize():
    # ------------------------------------------------------------------
    # 1. Parse and validate inputs
    # ------------------------------------------------------------------

    # --- heatmap ---
    if "heatmap" not in request.files:
        return jsonify({"error": "Missing field: heatmap"}), 400

    try:
        heatmap_img = load_image(request.files["heatmap"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    heatmap_w, heatmap_h = image_size(heatmap_img)

    # --- overlays ---
    overlay_files = request.files.getlist("overlays")
    max_overlays = current_app.config.get("MAX_OVERLAYS", 10)
    min_overlays = current_app.config.get("MIN_OVERLAYS", 1)

    if len(overlay_files) < min_overlays:
        return jsonify({"error": f"At least {min_overlays} overlay image is required."}), 400

    if len(overlay_files) > max_overlays:
        return jsonify(
            {"error": f"Too many overlays. Maximum allowed: {max_overlays}."}
        ), 400

    # --- metadata ---
    metadata_raw = request.form.get("metadata", "")
    if not metadata_raw:
        return jsonify({"error": "Missing field: metadata"}), 400

    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Invalid JSON in metadata: {exc}"}), 400

    if not isinstance(metadata, list):
        return jsonify({"error": "metadata must be a JSON array"}), 400

    if len(metadata) != len(overlay_files):
        return jsonify(
            {
                "error": (
                    f"Number of metadata entries ({len(metadata)}) must match "
                    f"number of overlay files ({len(overlay_files)})."
                )
            }
        ), 400

    # Validate each metadata entry
    for i, entry in enumerate(metadata):
        for field in ("id", "x", "y"):
            if field not in entry:
                return jsonify(
                    {"error": f"metadata[{i}] is missing field '{field}'"}
                ), 400

    # ------------------------------------------------------------------
    # 2. Build the intensity matrix once for all overlays
    # ------------------------------------------------------------------
    try:
        intensity = rgb_to_intensity(heatmap_img)
    except Exception as exc:
        return jsonify({"error": f"Failed to process heatmap: {exc}"}), 500

    # ------------------------------------------------------------------
    # 3. Process each overlay
    # ------------------------------------------------------------------
    results = []

    for file_storage, meta in zip(overlay_files, metadata):
        overlay_id = meta["id"]
        orig_x = int(meta["x"])
        orig_y = int(meta["y"])

        # Load overlay image
        try:
            overlay_img = load_image(file_storage)
        except ValueError as exc:
            return jsonify({"error": f"Overlay '{overlay_id}': {exc}"}), 400

        ov_w, ov_h = image_size(overlay_img)

        # Check overlay fits inside heatmap
        if ov_w > heatmap_w or ov_h > heatmap_h:
            return jsonify(
                {
                    "error": (
                        f"Overlay '{overlay_id}' ({ov_w}×{ov_h}) is larger than "
                        f"the heatmap ({heatmap_w}×{heatmap_h})."
                    )
                }
            ), 422

        # Original heat sum (clamped to valid region)
        original_heat_sum = compute_heat_sum_at(intensity, orig_x, orig_y, ov_w, ov_h)

        # Find optimal position
        distance_weight = float(request.form.get("distance_weight", 0.3))
        try:
            opt_x, opt_y, optimized_heat_sum = find_optimal_position(
                intensity, ov_w, ov_h,
                origin_x=orig_x, origin_y=orig_y,
                distance_weight=distance_weight,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 422

        results.append(
            {
                "id": overlay_id,
                "original": {"x": orig_x, "y": orig_y},
                "optimized": {"x": opt_x, "y": opt_y},
                "original_heat_sum": original_heat_sum,
                "optimized_heat_sum": optimized_heat_sum,
            }
        )

    return jsonify({"results": results}), 200
