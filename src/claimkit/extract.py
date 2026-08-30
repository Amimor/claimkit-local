from __future__ import annotations

import re
from datetime import datetime

from .models import EvidenceFile, ExtractedField

LABEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "manufacturer": (r"(?:manufacturer|brand|производитель|бренд)\s*[:№-]?\s*([\w .-]{2,40})",),
    "model": (r"(?:model|модель)\s*(?:no\.?|№)?\s*[:№-]?\s*([A-ZА-Я0-9][\w./-]{2,30})",),
    "serial_number": (r"(?:serial(?:\s+number)?|s/n|серийный\s+номер)\s*[:№-]?\s*([A-ZА-Я0-9-]{4,40})",),
    "seller": (r"(?:seller|продавец)\s*[:№-]?\s*([^\n\r]{2,60})",),
    "warranty_months": (r"(?:warranty|гарантия|срок гарантии)\s*[:№-]?\s*(\d{1,3})\s*(?:months?|мес)",),
}

DATE_PATTERN = re.compile(
    r"(?:purchase date|date|дата покупки|дата)\s*[:№-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(
    r"(?:total|price|итого|стоимость)\s*[:№-]?\s*([\d\s.,]+)\s*(RUB|USD|EUR|₽|\$|€|руб\.?)",
    re.IGNORECASE,
)


def normalize_date(value: str) -> str:
    cleaned = value.replace("/", ".").replace("-", ".")
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%m.%d.%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return value.strip()


def normalize_price(amount: str, currency: str) -> str:
    compact = amount.replace(" ", "").replace(",", ".")
    try:
        numeric = f"{float(compact):.2f}"
    except ValueError:
        numeric = compact
    currency_map = {"₽": "RUB", "РУБ": "RUB", "РУБ.": "RUB", "$": "USD", "€": "EUR"}
    return f"{numeric} {currency_map.get(currency.upper(), currency.upper())}"


def extract_fields(evidence: EvidenceFile) -> list[ExtractedField]:
    text = evidence.ocr_text
    fields: list[ExtractedField] = []
    for name, patterns in LABEL_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip().rstrip(".;")
                fields.append(
                    ExtractedField(
                        name=name,
                        original_value=value,
                        normalized_value=value.upper() if name in {"model", "serial_number"} else value,
                        source_file_id=evidence.id,
                        confidence=0.9,
                    )
                )
                break
    if match := DATE_PATTERN.search(text):
        fields.append(
            ExtractedField(
                name="purchase_date",
                original_value=match.group(1),
                normalized_value=normalize_date(match.group(1)),
                source_file_id=evidence.id,
                confidence=0.9,
            )
        )
    if match := PRICE_PATTERN.search(text):
        fields.append(
            ExtractedField(
                name="price",
                original_value=f"{match.group(1)} {match.group(2)}",
                normalized_value=normalize_price(match.group(1), match.group(2)),
                source_file_id=evidence.id,
                confidence=0.9,
            )
        )
    return fields
