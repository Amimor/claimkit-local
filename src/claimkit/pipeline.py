from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .classify import classify_file
from .damage import DamageBackend, ReviewOnlyDamageBackend
from .extract import extract_fields
from .models import (
    Appliance,
    ClaimPackage,
    EvidenceConflict,
    EvidenceFile,
    ExtractedField,
    FileType,
    ReviewStatus,
)
from .ocr import AutoOCRBackend, OCRBackend
from .quality import image_quality_warnings, sha256_file

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
IMPORTANT_TYPES = {FileType.RECEIPT, FileType.WARRANTY_CARD, FileType.SERIAL_LABEL, FileType.DAMAGE_PHOTO}


def _file_id(path: Path) -> str:
    return str(uuid5(NAMESPACE_URL, str(path.resolve())))


def inspect_folder(
    folder: Path,
    language: str = "en",
    ocr: OCRBackend | None = None,
) -> tuple[list[EvidenceFile], list[ExtractedField]]:
    backend = ocr or AutoOCRBackend()
    evidence: list[EvidenceFile] = []
    fields: list[ExtractedField] = []
    seen_hashes: dict[str, str] = {}
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        tokens = backend.read(path, language)
        ocr_text = "\n".join(token.text for token in tokens)
        digest = sha256_file(path)
        warnings = image_quality_warnings(path)
        if digest in seen_hashes:
            warnings.append(f"duplicate_of:{seen_hashes[digest]}")
        else:
            seen_hashes[digest] = path.name
        item = EvidenceFile(
            id=_file_id(path),
            file_type=classify_file(path, ocr_text),
            path=path,
            sha256=digest,
            quality_warnings=warnings,
            ocr_text=ocr_text,
        )
        evidence.append(item)
        fields.extend(extract_fields(item))
    return evidence, fields


def find_conflicts(fields: list[ExtractedField]) -> list[EvidenceConflict]:
    by_name: dict[str, list[ExtractedField]] = defaultdict(list)
    for field in fields:
        if field.name in {"model", "serial_number", "purchase_date"}:
            by_name[field.name].append(field)
    conflicts: list[EvidenceConflict] = []
    for name, candidates in by_name.items():
        values = sorted({field.normalized_value for field in candidates})
        if len(values) > 1:
            conflicts.append(
                EvidenceConflict(
                    field_name=name,
                    competing_values=values,
                    source_file_ids=sorted({field.source_file_id for field in candidates}),
                )
            )
    return conflicts


def create_claim_package(
    folder: Path,
    language: str = "en",
    description: str = "",
    ocr: OCRBackend | None = None,
    damage_backend: DamageBackend | None = None,
) -> tuple[ClaimPackage, list[EvidenceFile]]:
    evidence, fields = inspect_folder(folder, language, ocr)
    by_name: dict[str, list[str]] = defaultdict(list)
    for field in fields:
        by_name[field.name].append(field.normalized_value)

    def first_value(name: str) -> str | None:
        values = by_name.get(name)
        return values[0] if values else None

    damage_model = damage_backend or ReviewOnlyDamageBackend()
    suggestions = [s for item in evidence for s in damage_model.suggest(item, description)]
    confirmed = [suggestion for suggestion in suggestions if suggestion.user_status == ReviewStatus.CONFIRMED]
    present = {item.file_type for item in evidence}
    missing = [kind.value for kind in sorted(IMPORTANT_TYPES - present, key=lambda x: x.value)]
    package = ClaimPackage(
        appliance=Appliance(
            manufacturer=first_value("manufacturer"),
            model=first_value("model"),
            serial_number=first_value("serial_number"),
        ),
        extracted_fields=fields,
        conflicts=find_conflicts(fields),
        damage_suggestions=suggestions,
        confirmed_damage=confirmed,
        missing_evidence=missing,
        problem_description=description,
    )
    return package, evidence
