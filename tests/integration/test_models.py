from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import pytest

from claimkit.demo import generate_demo
from claimkit.models import EvidenceFile, FileType, ReviewStatus

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_MODEL_INTEGRATION") != "1",
        reason="Set RUN_MODEL_INTEGRATION=1 to run downloaded local models.",
    ),
]


def test_real_paddleocr_english_and_russian() -> None:
    from claimkit.ocr import PaddleOCRBackend

    with tempfile.TemporaryDirectory() as temp:
        evidence = generate_demo(Path(temp))
        receipt = evidence / "01_receipt_en.png"
        warranty = evidence / "02_warranty_ru.png"
        english = "\n".join(token.text for token in PaddleOCRBackend("en").read(receipt, "en"))
        russian = "\n".join(token.text for token in PaddleOCRBackend("ru").read(warranty, "ru"))
        assert "WM-420" in english
        assert "18.08.2026" in english
        assert "24" in russian
        assert "18.08.2026" in russian


@pytest.mark.skipif(
    os.environ.get("RUN_FLORENCE_INTEGRATION") != "1",
    reason="Set RUN_FLORENCE_INTEGRATION=1 for the larger Florence-2 smoke test.",
)
def test_real_florence_returns_unconfirmed_valid_regions() -> None:
    from claimkit.damage import FlorenceDamageBackend

    with tempfile.TemporaryDirectory() as temp:
        evidence = generate_demo(Path(temp))
        path = evidence / "05_damage_photo.png"
        item = EvidenceFile(
            id="damage",
            file_type=FileType.DAMAGE_PHOTO,
            path=path,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        suggestions = FlorenceDamageBackend().suggest(item, "crack on the appliance door")
        assert suggestions
        assert all(item.user_status == ReviewStatus.PENDING for item in suggestions)
        assert all(item.bounding_box.x2 > item.bounding_box.x1 for item in suggestions)
        assert all(item.bounding_box.y2 > item.bounding_box.y1 for item in suggestions)
