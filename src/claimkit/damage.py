from __future__ import annotations

from typing import Protocol

from PIL import Image

from .models import BoundingBox, DamageSuggestion, EvidenceFile, FileType


class DamageBackend(Protocol):
    def suggest(self, evidence: EvidenceFile, description: str) -> list[DamageSuggestion]: ...


class ReviewOnlyDamageBackend:
    """Create an explicitly unconfirmed review region for damage photographs."""

    def suggest(self, evidence: EvidenceFile, description: str) -> list[DamageSuggestion]:
        if evidence.file_type != FileType.DAMAGE_PHOTO:
            return []
        try:
            with Image.open(evidence.path) as image:
                width, height = image.size
        except OSError:
            return []
        label = description.strip() or "reported damage"
        return [
            DamageSuggestion(
                image_id=evidence.id,
                label=label,
                bounding_box=BoundingBox(
                    x1=width // 4, y1=height // 4, x2=3 * width // 4, y2=3 * height // 4
                ),
                model_note="Fallback review region; manually adjust before confirmation.",
            )
        ]


class FlorenceDamageBackend:
    """Optional local Florence-2 adapter for captions and phrase grounding."""

    def __init__(self, model_name: str = "microsoft/Florence-2-base") -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install claimkit-local[vlm] to enable Florence-2") from exc
        self._processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)

    def suggest(self, evidence: EvidenceFile, description: str) -> list[DamageSuggestion]:
        if evidence.file_type != FileType.DAMAGE_PHOTO:
            return []
        image = Image.open(evidence.path).convert("RGB")
        task = "<CAPTION>"
        inputs = self._processor(text=task, images=image, return_tensors="pt")
        generated = self._model.generate(**inputs, max_new_tokens=128, num_beams=3)
        caption = self._processor.batch_decode(generated, skip_special_tokens=False)[0]
        width, height = image.size
        return [
            DamageSuggestion(
                image_id=evidence.id,
                label=description.strip() or caption,
                bounding_box=BoundingBox(x1=0, y1=0, x2=width, y2=height),
                model_note="Florence-2 caption; region requires manual confirmation.",
            )
        ]
