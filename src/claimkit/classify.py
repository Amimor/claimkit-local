from __future__ import annotations

from pathlib import Path

from .models import FileType

KEYWORDS: dict[FileType, tuple[str, ...]] = {
    FileType.RECEIPT: ("receipt", "invoice", "кассовый чек", "итого", "total", "seller"),
    FileType.WARRANTY_CARD: ("warranty", "guarantee", "гарантийн", "срок гарантии"),
    FileType.SERIAL_LABEL: ("serial", "s/n", "серийн", "model no", "модель"),
    FileType.DAMAGE_PHOTO: ("damage", "crack", "dent", "повреж", "трещин", "вмятин"),
    FileType.PRODUCT_OVERVIEW: ("overview", "appliance", "product", "общий вид"),
}


def classify_file(path: Path, ocr_text: str) -> FileType:
    normalized_name = path.stem.lower()
    filename_hints = {
        "warranty": FileType.WARRANTY_CARD,
        "гарант": FileType.WARRANTY_CARD,
        "receipt": FileType.RECEIPT,
        "invoice": FileType.RECEIPT,
        "serial_label": FileType.SERIAL_LABEL,
        "damage": FileType.DAMAGE_PHOTO,
        "overview": FileType.PRODUCT_OVERVIEW,
    }
    for hint, kind in filename_hints.items():
        if hint in normalized_name:
            return kind
    haystack = f"{path.stem} {ocr_text}".lower()
    scores = {
        kind: sum(1 for keyword in keywords if keyword in haystack) for kind, keywords in KEYWORDS.items()
    }
    best = max(scores, key=lambda kind: scores[kind])
    return best if scores[best] else FileType.UNKNOWN
