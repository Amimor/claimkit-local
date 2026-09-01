from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image, ImageDraw

from claimkit.damage import FlorenceDamageBackend
from claimkit.export import export_package
from claimkit.models import BoundingBox, DamageSuggestion, ReviewStatus
from claimkit.ocr import AutoOCRBackend
from claimkit.pipeline import create_claim_package


@st.cache_resource(show_spinner=False)
def _ocr_backend() -> AutoOCRBackend:
    return AutoOCRBackend()


@st.cache_resource(show_spinner="Loading Florence-2 on CPU. The first run may take several minutes.")
def _florence_backend() -> FlorenceDamageBackend:
    return FlorenceDamageBackend()


def _workspace() -> Path:
    current = st.session_state.get("workspace")
    if current:
        return Path(current)
    path = Path(tempfile.mkdtemp(prefix="claimkit-local-"))
    st.session_state.workspace = str(path)
    return path


def _save_uploads(uploads: list[Any]) -> Path:
    evidence_dir = _workspace() / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for old_file in evidence_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()
    for index, upload in enumerate(uploads, start=1):
        safe_name = Path(upload.name).name
        (evidence_dir / f"{index:02d}_{safe_name}").write_bytes(upload.getvalue())
    return evidence_dir


def _overlay(image_path: Path, suggestions: list[DamageSuggestion]) -> Image.Image:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = {
        ReviewStatus.PENDING: "#f59e0b",
        ReviewStatus.CONFIRMED: "#16a34a",
        ReviewStatus.REJECTED: "#64748b",
    }
    for index, suggestion in enumerate(suggestions, start=1):
        color = colors[suggestion.user_status]
        draw.rectangle(suggestion.bounding_box.as_tuple(), outline=color, width=4)
        draw.text((suggestion.bounding_box.x1 + 4, suggestion.bounding_box.y1 + 4), str(index), fill=color)
    return image


def _review_fields() -> None:
    package = st.session_state.package
    st.subheader("Extracted fields")
    st.caption("Every value remains linked to its source file and OCR coordinates.")
    rows = [
        {
            "name": field.name,
            "normalized_value": field.normalized_value,
            "original_value": field.original_value,
            "confidence": field.confidence,
            "source_file_id": field.source_file_id,
        }
        for field in package.extracted_fields
    ]
    edited = st.data_editor(
        rows,
        disabled=["name", "confidence", "source_file_id"],
        hide_index=True,
        use_container_width=True,
        key="field_editor",
    )
    edited_rows = edited.to_dict("records") if hasattr(edited, "to_dict") else edited
    for field, row in zip(package.extracted_fields, edited_rows, strict=True):
        field.normalized_value = str(row["normalized_value"]).strip()
        field.original_value = str(row["original_value"]).strip()
    for field_name in ("manufacturer", "model", "serial_number"):
        reviewed = next(
            (
                field.normalized_value
                for field in package.extracted_fields
                if field.name == field_name and field.normalized_value
            ),
            None,
        )
        if reviewed:
            setattr(package.appliance, field_name, reviewed)

    st.subheader("Evidence inventory")
    evidence_by_id = {item.id: item for item in st.session_state.evidence}
    st.dataframe(
        [
            {
                "file": item.path.name,
                "type": item.file_type.value,
                "quality": ", ".join(item.quality_warnings) or "OK",
                "sha256": item.sha256[:12],
            }
            for item in evidence_by_id.values()
        ],
        hide_index=True,
        use_container_width=True,
    )


def _resolve_conflicts() -> None:
    package = st.session_state.package
    st.subheader("Conflicts")
    if not package.conflicts:
        st.success("No cross-document conflicts found.")
        return
    st.warning(
        "ClaimKit never chooses the correct value automatically. "
        "Review each source and select a value."
    )
    for conflict in package.conflicts:
        chosen = st.selectbox(
            f"Resolve {conflict.field_name.replace('_', ' ')}",
            conflict.competing_values,
            key=f"resolution-{conflict.field_name}",
        )
        if conflict.field_name in {"manufacturer", "model", "serial_number"}:
            setattr(package.appliance, conflict.field_name, chosen)


def _valid_box(box: BoundingBox) -> bool:
    return box.x2 > box.x1 and box.y2 > box.y1


def _review_damage() -> None:
    package = st.session_state.package
    evidence_by_id = {item.id: item for item in st.session_state.evidence}
    st.subheader("Damage regions")
    st.caption(
        "Model suggestions are untrusted until you confirm them. "
        "Coordinates can be corrected manually."
    )
    if not package.damage_suggestions:
        st.info("No damage photo was classified. You can still add a manual region below.")
    grouped: dict[str, list[DamageSuggestion]] = {}
    for suggestion in package.damage_suggestions:
        grouped.setdefault(suggestion.image_id, []).append(suggestion)
    for image_id, suggestions in grouped.items():
        evidence = evidence_by_id.get(image_id)
        if evidence is None:
            continue
        st.markdown(f"**{evidence.path.name}**")
        left, right = st.columns([1.2, 1])
        left.image(_overlay(evidence.path, suggestions), use_container_width=True)
        for index, suggestion in enumerate(suggestions):
            key = f"damage-{image_id}-{index}"
            with right.container(border=True):
                suggestion.label = st.text_input("Label", suggestion.label, key=f"{key}-label")
                coordinates = st.columns(4)
                values = [
                    coordinates[0].number_input(
                        "x1", min_value=0, value=suggestion.bounding_box.x1, key=f"{key}-x1"
                    ),
                    coordinates[1].number_input(
                        "y1", min_value=0, value=suggestion.bounding_box.y1, key=f"{key}-y1"
                    ),
                    coordinates[2].number_input(
                        "x2", min_value=1, value=suggestion.bounding_box.x2, key=f"{key}-x2"
                    ),
                    coordinates[3].number_input(
                        "y2", min_value=1, value=suggestion.bounding_box.y2, key=f"{key}-y2"
                    ),
                ]
                candidate = BoundingBox(x1=values[0], y1=values[1], x2=values[2], y2=values[3])
                if _valid_box(candidate):
                    suggestion.bounding_box = candidate
                else:
                    st.error("x2 and y2 must be greater than x1 and y1.")
                status = st.radio(
                    "Decision",
                    [item.value for item in ReviewStatus],
                    index=list(ReviewStatus).index(suggestion.user_status),
                    horizontal=True,
                    key=f"{key}-status",
                )
                suggestion.user_status = ReviewStatus(status)
                st.caption(suggestion.model_note)

    image_options = {
        item.path.name: item
        for item in st.session_state.evidence
        if item.path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    }
    if image_options:
        with st.expander("Add a manual damage region"):
            with st.form("manual-region"):
                selected_name = st.selectbox("Image", list(image_options))
                label = st.text_input("Label", "reported damage")
                columns = st.columns(4)
                x1 = columns[0].number_input("x1", min_value=0, value=0)
                y1 = columns[1].number_input("y1", min_value=0, value=0)
                x2 = columns[2].number_input("x2", min_value=1, value=100)
                y2 = columns[3].number_input("y2", min_value=1, value=100)
                if st.form_submit_button("Add confirmed region"):
                    box = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                    if not _valid_box(box):
                        st.error("x2 and y2 must be greater than x1 and y1.")
                    else:
                        selected = image_options[selected_name]
                        package.damage_suggestions.append(
                            DamageSuggestion(
                                image_id=selected.id,
                                label=label.strip() or "reported damage",
                                bounding_box=box,
                                user_status=ReviewStatus.CONFIRMED,
                                model_note="Region added and confirmed manually.",
                            )
                        )
                        st.rerun()
    package.confirmed_damage = [
        suggestion
        for suggestion in package.damage_suggestions
        if suggestion.user_status == ReviewStatus.CONFIRMED and _valid_box(suggestion.bounding_box)
    ]


def _export() -> None:
    package = st.session_state.package
    evidence = st.session_state.evidence
    st.subheader("Package preview")
    metrics = st.columns(4)
    metrics[0].metric("Evidence files", len(evidence))
    metrics[1].metric("Extracted fields", len(package.extracted_fields))
    metrics[2].metric("Conflicts", len(package.conflicts))
    metrics[3].metric("Confirmed regions", len(package.confirmed_damage))
    if package.missing_evidence:
        st.warning("Missing evidence: " + ", ".join(package.missing_evidence))
    st.info("The generated letter organizes evidence and makes no legal warranty determination.")
    if st.button("Build claim package", type="primary"):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output = _workspace() / f"claim-package-{stamp}"
        try:
            archive = export_package(output, package, evidence, st.session_state.language)
        except (OSError, ValueError) as exc:
            st.error(f"Could not build package: {exc}")
        else:
            st.session_state.archive_path = str(archive)
    archive_path = st.session_state.get("archive_path")
    if archive_path and Path(archive_path).is_file():
        archive = Path(archive_path)
        st.success("The package is ready. Originals in the upload folder were not modified.")
        st.download_button("Download ZIP", archive.read_bytes(), archive.name, "application/zip")


def main() -> None:
    st.set_page_config(page_title="ClaimKit Local", page_icon="🧰", layout="wide")
    st.title("ClaimKit Local")
    st.caption("Build a reviewable warranty evidence package. Files stay on this device.")
    language = st.selectbox("Document language", ["en", "ru"], format_func=lambda value: value.upper())
    description = st.text_area("Describe the reported problem")
    use_florence = st.checkbox(
        "Use Florence-2 damage suggestions",
        help="Optional local CPU inference. Suggestions still require confirmation.",
    )
    uploads = st.file_uploader(
        "Receipt, warranty card, serial label, overview and damage photos",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )
    if uploads and st.button("Inspect evidence", type="primary"):
        folder = _save_uploads(uploads)
        try:
            damage_backend = _florence_backend() if use_florence else None
            with st.spinner("Running local OCR and evidence checks..."):
                package, evidence = create_claim_package(
                    folder,
                    language,
                    description,
                    ocr=_ocr_backend(),
                    damage_backend=damage_backend,
                )
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state.package = package
            st.session_state.evidence = evidence
            st.session_state.language = language
            st.session_state.archive_path = None

    if "package" not in st.session_state:
        st.info("Try `claimkit demo` for a model-free synthetic walkthrough.")
        return

    tabs = st.tabs(["1 · Upload", "2 · Review fields", "3 · Resolve & confirm", "4 · Export"])
    with tabs[0]:
        st.success(
            f"Loaded {len(st.session_state.evidence)} evidence files. "
            "Upload again to start a new review."
        )
    with tabs[1]:
        _review_fields()
    with tabs[2]:
        _resolve_conflicts()
        st.divider()
        _review_damage()
    with tabs[3]:
        _export()


if __name__ == "__main__":
    main()
