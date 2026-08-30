from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .demo import generate_demo
from .pipeline import create_claim_package


def evaluate_demo() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="claimkit-eval-") as temp:
        evidence_dir = generate_demo(Path(temp) / "evidence")
        truth = json.loads((evidence_dir / "ground-truth.json").read_text(encoding="utf-8"))
        package, evidence = create_claim_package(evidence_dir, description="Crack on the appliance door")
        expected = {tuple(item) for item in truth["expected_fields"]}
        predicted = {(field.name, field.normalized_value) for field in package.extracted_fields}
        model_conflicts = [item for item in package.conflicts if item.field_name == "model"]
        conflict_found = bool(
            model_conflicts and model_conflicts[0].competing_values == truth["expected_model_conflict"]
        )
        return {
            "fixture": "synthetic-en-ru-v1",
            "evidence_files": len(evidence),
            "expected_field_values": len(expected),
            "matched_field_values": len(expected & predicted),
            "normalized_field_recall": round(len(expected & predicted) / len(expected), 4),
            "seeded_conflicts": 1,
            "detected_seeded_conflicts": int(conflict_found),
            "conflict_recall": 1.0 if conflict_found else 0.0,
            "network_required": False,
        }
