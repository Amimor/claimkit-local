from __future__ import annotations

from typing import Any, Protocol

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

    MODEL_REVISION = "5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac"

    def __init__(
        self,
        model_name: str = "microsoft/Florence-2-base",
        revision: str = MODEL_REVISION,
    ) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as exc:  # pragma: no cover - optional integration
            raise RuntimeError("Install claimkit-local[vlm] to enable Florence-2") from exc
        self._torch = torch
        self._processor = AutoProcessor.from_pretrained(
            model_name,
            revision=revision,
            trust_remote_code=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            model_name,
            revision=revision,
            trust_remote_code=True,
        )
        self._model.eval()

    def _predict(self, image: Image.Image, prompt: str, task: str) -> Any:
        inputs = self._processor(text=prompt, images=image, return_tensors="pt")
        with self._torch.inference_mode():
            generated = self._model.generate(**inputs, max_new_tokens=256, num_beams=3)
        decoded = self._processor.batch_decode(generated, skip_special_tokens=False)[0]
        return self._processor.post_process_generation(decoded, task=task, image_size=image.size)

    @staticmethod
    def _caption(parsed: Any, task: str) -> str:
        if not isinstance(parsed, dict):
            return ""
        value = parsed.get(task, "")
        return value.strip() if isinstance(value, str) else ""

    def suggest(self, evidence: EvidenceFile, description: str) -> list[DamageSuggestion]:
        if evidence.file_type != FileType.DAMAGE_PHOTO:
            return []
        with Image.open(evidence.path) as source:
            image = source.convert("RGB")
        width, height = image.size
        caption_task = "<DETAILED_CAPTION>"
        caption = self._caption(self._predict(image, caption_task, caption_task), caption_task)
        phrase = description.strip() or caption
        grounding_task = "<CAPTION_TO_PHRASE_GROUNDING>"
        grounded = self._predict(image, f"{grounding_task}{phrase}", grounding_task)
        payload = grounded.get(grounding_task, {}) if isinstance(grounded, dict) else {}
        boxes = payload.get("bboxes", []) if isinstance(payload, dict) else []
        raw_labels = (
            payload.get("labels", payload.get("bboxes_labels", [])) if isinstance(payload, dict) else []
        )
        labels = raw_labels if isinstance(raw_labels, list) else []
        suggestions: list[DamageSuggestion] = []
        for index, raw_box in enumerate(boxes):
            if not isinstance(raw_box, (list, tuple)) or len(raw_box) != 4:
                continue
            x1, y1, x2, y2 = (int(round(float(value))) for value in raw_box)
            box = BoundingBox(
                x1=max(0, min(width - 1, x1)),
                y1=max(0, min(height - 1, y1)),
                x2=max(1, min(width, x2)),
                y2=max(1, min(height, y2)),
            )
            if box.x2 <= box.x1 or box.y2 <= box.y1:
                continue
            label = str(labels[index]) if index < len(labels) else phrase
            suggestions.append(
                DamageSuggestion(
                    image_id=evidence.id,
                    label=label,
                    bounding_box=box,
                    model_note=f"Florence-2 grounded suggestion; caption: {caption or 'unavailable'}",
                )
            )
        if suggestions:
            return suggestions
        return [
            DamageSuggestion(
                image_id=evidence.id,
                label=phrase or "reported damage",
                bounding_box=BoundingBox(x1=0, y1=0, x2=width, y2=height),
                model_note=(
                    "Florence-2 produced no grounded region; full-image review fallback. "
                    f"Caption: {caption or 'unavailable'}"
                ),
            )
        ]
