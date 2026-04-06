"""
image_utils.py — Helpers for loading and validating images from Flask request files.
"""

from __future__ import annotations

from typing import Set

from flask import current_app
from PIL import Image
from werkzeug.datastructures import FileStorage


def allowed_extension(filename: str, allowed: Set[str] | None = None) -> bool:
    """Return True if *filename* has an allowed image extension.

    Uses ``current_app.config['ALLOWED_EXTENSIONS']`` when *allowed* is None.
    Falls back to a hard-coded set when called outside an app context.
    """
    if allowed is None:
        try:
            allowed = current_app.config.get(
                "ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
            )
        except RuntimeError:
            allowed = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}

    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed


def load_image(file_storage: FileStorage) -> Image.Image:
    """Load a PIL Image from a Werkzeug FileStorage object.

    Parameters
    ----------
    file_storage:
        A file uploaded via Flask's ``request.files``.

    Returns
    -------
    PIL.Image.Image

    Raises
    ------
    ValueError
        If the file cannot be opened as an image or has a disallowed extension.
    """
    filename = file_storage.filename or ""

    if not allowed_extension(filename):
        raise ValueError(
            f"File '{filename}' has an unsupported extension. "
            "Allowed: png, jpg, jpeg, gif, bmp, webp."
        )

    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        img.load()  # force decode so we catch corrupt files early
        return img
    except Exception as exc:
        raise ValueError(f"Cannot open image '{filename}': {exc}") from exc


def image_size(image: Image.Image) -> tuple[int, int]:
    """Return (width, height) of a PIL image."""
    return image.size  # PIL: (width, height)
