from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import BoundingBox, OCRToken


class OCRBackend(Protocol):
    def read(self, path: Path, language: str = "en") -> list[OCRToken]: ...


class SidecarOCRBackend:
    """Deterministic OCR backend for demos and tests.

    A JSON sidecar may contain tokens with bounding boxes. A plain .txt sidecar
    is accepted as a single token. This keeps CI model-free without pretending
    that the text was inferred from pixels.
    """

    def read(self, path: Path, language: str = "en") -> list[OCRToken]:
        json_path = path.with_suffix(path.suffix + ".ocr.json")
        if json_path.exists():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            return [OCRToken.model_validate(item) for item in payload]
        text_path = path.with_suffix(path.suffix + ".txt")
        if text_path.exists():
            return [
                OCRToken(
                    text=text_path.read_text(encoding="utf-8"),
                    bounding_box=BoundingBox(x1=0, y1=0, x2=1000, y2=1000),
                    confidence=1.0,
                )
            ]
        return []


class PaddleOCRBackend:
    """Lazy PaddleOCR adapter; importing ClaimKit never downloads a model."""

    def __init__(self, language: str = "en") -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install claimkit-local[ocr] to process real images") from exc
        self._engine = PaddleOCR(lang=language, use_doc_orientation_classify=True)

    def read(self, path: Path, language: str = "en") -> list[OCRToken]:
        results = self._engine.predict(str(path))
        tokens: list[OCRToken] = []
        for page in results:
            data = getattr(page, "json", page)
            if callable(data):
                data = data()
            data = data.get("res", data) if isinstance(data, dict) else {}
            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            boxes = data.get("rec_boxes", [])
            for text, score, box in zip(texts, scores, boxes, strict=False):
                x1, y1, x2, y2 = [int(v) for v in box]
                tokens.append(
                    OCRToken(
                        text=str(text),
                        confidence=float(score),
                        bounding_box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    )
                )
        return tokens


class AutoOCRBackend:
    """Use explicit sidecars when present, otherwise try local PaddleOCR."""

    def read(self, path: Path, language: str = "en") -> list[OCRToken]:
        sidecar = SidecarOCRBackend().read(path, language)
        if sidecar:
            return sidecar
        return PaddleOCRBackend(language).read(path, language)
