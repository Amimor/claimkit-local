from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from .models import ClaimPackage, EvidenceFile


def _safe_name(index: int, evidence: EvidenceFile) -> str:
    return f"{index:02d}_{evidence.file_type.value}{evidence.path.suffix.lower()}"


def _letter(package: ClaimPackage, language: str) -> str:
    appliance = package.appliance
    if language == "ru":
        return (
            "Тема: Обращение по качеству бытовой техники\n\n"
            f"Производитель: {appliance.manufacturer or 'требует уточнения'}\n"
            f"Модель: {appliance.model or 'требует уточнения'}\n"
            f"Серийный номер: {appliance.serial_number or 'требует уточнения'}\n\n"
            f"Описание проблемы:\n{package.problem_description or 'Не указано'}\n\n"
            "К письму приложен структурированный пакет доказательств. "
            "Пожалуйста, сообщите дальнейший порядок проверки товара.\n"
        )
    return (
        "Subject: Household appliance quality claim\n\n"
        f"Manufacturer: {appliance.manufacturer or 'needs review'}\n"
        f"Model: {appliance.model or 'needs review'}\n"
        f"Serial number: {appliance.serial_number or 'needs review'}\n\n"
        f"Problem description:\n{package.problem_description or 'Not provided'}\n\n"
        "A structured evidence package is attached. Please advise on the next inspection steps.\n"
    )


def _write_pdf(path: Path, package: ClaimPackage, evidence: list[EvidenceFile]) -> None:
    canvas = Canvas(str(path), pagesize=A4)
    width, height = A4
    canvas.setTitle("ClaimKit evidence summary")
    navy = colors.HexColor("#17212B")
    blue = colors.HexColor("#276EF1")
    light_blue = colors.HexColor("#EEF4FF")
    light_gray = colors.HexColor("#F6F8FA")
    border = colors.HexColor("#D0D7DE")
    warning = colors.HexColor("#FFF4CE")
    danger = colors.HexColor("#FDEBEC")
    text = colors.HexColor("#1F2328")
    muted = colors.HexColor("#59636E")
    margin = 42
    content_width = width - margin * 2

    canvas.setFillColor(navy)
    canvas.rect(0, height - 94, width, 94, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 22)
    canvas.drawString(margin, height - 45, "ClaimKit evidence summary")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(margin, height - 67, "Local, review-first warranty evidence package")
    canvas.setFillColor(blue)
    canvas.roundRect(width - 142, height - 66, 100, 28, 6, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(width - 92, height - 56, "REVIEW REQUIRED")

    y = height - 116
    canvas.setFillColor(warning)
    canvas.roundRect(margin, y - 35, content_width, 35, 6, fill=1, stroke=0)
    canvas.setFillColor(text)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        margin + 12,
        y - 21,
        "This report organizes evidence. It does not determine warranty eligibility or fault.",
    )

    y -= 57
    canvas.setFillColor(text)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(margin, y, "Appliance")
    y -= 16
    canvas.setFillColor(light_blue)
    canvas.roundRect(margin, y - 74, content_width, 74, 7, fill=1, stroke=0)
    product_rows = [
        ("Manufacturer", package.appliance.manufacturer or "Needs review"),
        ("Model", package.appliance.model or "Needs review"),
        ("Serial number", package.appliance.serial_number or "Needs review"),
    ]
    column_width = content_width / 3
    for index, (label, value) in enumerate(product_rows):
        x = margin + index * column_width + 12
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(x, y - 22, label.upper())
        canvas.setFillColor(text)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(x, y - 45, value[:24])

    y -= 100
    canvas.setFillColor(text)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(margin, y, "Evidence inventory")
    canvas.setFillColor(muted)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - margin, y, f"{len(evidence)} local files")
    y -= 18
    table_header = y
    canvas.setFillColor(navy)
    canvas.rect(margin, table_header - 22, content_width, 22, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(margin + 10, table_header - 15, "FILE")
    canvas.drawString(margin + 270, table_header - 15, "TYPE")
    canvas.drawString(margin + 405, table_header - 15, "QUALITY")
    y = table_header - 22
    for index, item in enumerate(evidence[:7]):
        canvas.setFillColor(light_gray if index % 2 == 0 else colors.white)
        canvas.rect(margin, y - 24, content_width, 24, fill=1, stroke=0)
        canvas.setFillColor(text)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(margin + 10, y - 16, item.path.name[:30])
        canvas.drawString(margin + 270, y - 16, item.file_type.value[:20])
        quality = f"{len(item.quality_warnings)} warning(s)" if item.quality_warnings else "OK"
        canvas.drawString(margin + 405, y - 16, quality)
        y -= 24
    if len(evidence) > 7:
        canvas.setFillColor(muted)
        canvas.drawString(margin + 10, y - 14, f"+ {len(evidence) - 7} additional files in manifest.json")
        y -= 22

    y -= 18
    canvas.setFillColor(text)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(margin, y, "Reported problem")
    y -= 14
    canvas.setFillColor(light_gray)
    canvas.roundRect(margin, y - 44, content_width, 44, 6, fill=1, stroke=0)
    canvas.setFillColor(text)
    canvas.setFont("Helvetica", 9)
    description = package.problem_description or "Not provided"
    canvas.drawString(margin + 12, y - 26, description[:90])

    y -= 70
    canvas.setFillColor(text)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(margin, y, "Review findings")
    y -= 14
    findings_height = max(50, 24 + 18 * max(1, len(package.conflicts)))
    canvas.setFillColor(danger if package.conflicts else light_blue)
    canvas.roundRect(margin, y - findings_height, content_width, findings_height, 6, fill=1, stroke=0)
    canvas.setFillColor(text)
    canvas.setFont("Helvetica", 9)
    if package.conflicts:
        for index, conflict in enumerate(package.conflicts[:4]):
            finding = f"{conflict.field_name}: {' / '.join(conflict.competing_values)}"
            canvas.drawString(margin + 12, y - 22 - index * 18, finding[:92])
    else:
        canvas.drawString(margin + 12, y - 24, "No cross-document conflicts detected.")

    canvas.setStrokeColor(border)
    canvas.line(margin, 34, width - margin, 34)
    canvas.setFillColor(muted)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(margin, 21, "Generated locally by ClaimKit Local - verify every field before sending.")
    canvas.drawRightString(width - margin, 21, "Page 1 of 1")
    canvas.save()


def export_package(
    output_dir: Path,
    package: ClaimPackage,
    evidence: list[EvidenceFile],
    language: str = "en",
) -> Path:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    originals = output_dir / "originals"
    copies = output_dir / "evidence"
    originals.mkdir(parents=True, exist_ok=True)
    copies.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(evidence, start=1):
        shutil.copy2(item.path, originals / item.path.name)
        shutil.copy2(item.path, copies / _safe_name(index, item))

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "package": package.model_dump(mode="json"),
                "evidence": [item.model_dump(mode="json") for item in evidence],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    letter_path = output_dir / f"claim-letter-{language}.txt"
    letter_path.write_text(_letter(package, language), encoding="utf-8")
    _write_pdf(output_dir / "claim-summary.pdf", package, evidence)
    (output_dir / "missing-evidence.txt").write_text(
        "\n".join(package.missing_evidence) or "No required evidence types are missing.", encoding="utf-8"
    )
    package.output_files = [
        str(path.relative_to(output_dir)) for path in output_dir.rglob("*") if path.is_file()
    ]
    zip_path = output_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in output_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir))
    return zip_path
