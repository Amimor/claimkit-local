from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class FileType(StrEnum):
    RECEIPT = "receipt"
    WARRANTY_CARD = "warranty_card"
    SERIAL_LABEL = "serial_label"
    PRODUCT_OVERVIEW = "product_overview"
    DAMAGE_PHOTO = "damage_photo"
    UNKNOWN = "unknown"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.x1, self.y1, self.x2, self.y2


class OCRToken(BaseModel):
    text: str
    bounding_box: BoundingBox
    confidence: float = Field(ge=0, le=1)


class EvidenceFile(BaseModel):
    id: str
    file_type: FileType
    path: Path
    sha256: str
    quality_warnings: list[str] = Field(default_factory=list)
    ocr_text: str = ""


class ExtractedField(BaseModel):
    name: str
    normalized_value: str
    original_value: str
    source_file_id: str
    bounding_box: BoundingBox | None = None
    confidence: float = Field(default=0.8, ge=0, le=1)


class EvidenceConflict(BaseModel):
    field_name: str
    competing_values: list[str]
    source_file_ids: list[str]
    severity: str = "high"


class DamageSuggestion(BaseModel):
    image_id: str
    label: str
    bounding_box: BoundingBox
    user_status: ReviewStatus = ReviewStatus.PENDING
    model_note: str = "Uncalibrated suggestion; user confirmation required."


class Appliance(BaseModel):
    category: str = "household_appliance"
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None


class ClaimPackage(BaseModel):
    appliance: Appliance
    extracted_fields: list[ExtractedField]
    conflicts: list[EvidenceConflict]
    confirmed_damage: list[DamageSuggestion]
    missing_evidence: list[str]
    output_files: list[str] = Field(default_factory=list)
    problem_description: str = ""
