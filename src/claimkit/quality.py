from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_quality_warnings(path: Path) -> list[str]:
    try:
        with Image.open(path) as image:
            gray = np.asarray(image.convert("L"), dtype=np.float32)
            width, height = image.size
    except (UnidentifiedImageError, OSError):
        return []

    warnings: list[str] = []
    if width < 640 or height < 480:
        warnings.append("low_resolution")
    if gray.size:
        horizontal = np.abs(np.diff(gray, axis=1)).mean() if gray.shape[1] > 1 else 0
        vertical = np.abs(np.diff(gray, axis=0)).mean() if gray.shape[0] > 1 else 0
        if float(horizontal + vertical) < 7.0:
            warnings.append("possibly_blurred")
        if float((gray > 245).mean()) > 0.80:
            warnings.append("overexposed")
        if float((gray < 10).mean()) > 0.80:
            warnings.append("underexposed")
    return warnings
