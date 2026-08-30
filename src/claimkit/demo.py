from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _document(path: Path, title: str, lines: list[str], tint: str = "white") -> None:
    image = Image.new("RGB", (1200, 800), tint)
    draw = ImageDraw.Draw(image)
    draw.text((55, 45), title, fill="black", font=_font(36))
    y = 125
    for line in lines:
        draw.text((55, y), line, fill="black", font=_font(25))
        y += 52
    image.save(path)
    path.with_suffix(path.suffix + ".txt").write_text("\n".join(lines), encoding="utf-8")


def generate_demo(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    _document(
        folder / "01_receipt_en.png",
        "RECEIPT",
        [
            "Seller: North Home Store",
            "Manufacturer: NordHome",
            "Model: WM-420",
            "Serial Number: NH420-77881",
            "Purchase Date: 18.08.2026",
            "Total: 549.90 EUR",
        ],
    )
    _document(
        folder / "02_warranty_ru.png",
        "ГАРАНТИЙНЫЙ ТАЛОН",
        [
            "Продавец: North Home Store",
            "Производитель: NordHome",
            "Модель: WM-421",
            "Серийный номер: NH420-77881",
            "Дата покупки: 18.08.2026",
            "Гарантия: 24 мес",
        ],
        "#f8f5ea",
    )
    _document(
        folder / "03_serial_label.png",
        "PRODUCT LABEL",
        ["Manufacturer: NordHome", "Model: WM-420", "S/N: NH420-77881"],
        "#e8eef2",
    )
    _document(
        folder / "04_product_overview.png",
        "APPLIANCE OVERVIEW",
        ["Front view of washing machine"],
        "#dce7ea",
    )
    image = Image.new("RGB", (1200, 800), "#d7d9d8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((250, 80, 950, 730), radius=30, fill="#f3f4f4", outline="#48535a", width=8)
    draw.ellipse((425, 250, 775, 600), outline="#48535a", width=18)
    draw.line((610, 270, 550, 390, 640, 470, 585, 555), fill="#aa2020", width=12)
    draw.text((65, 715), "Damage photo: reported crack on the door", fill="black", font=_font(25))
    damage_path = folder / "05_damage_photo.png"
    image.save(damage_path)
    damage_path.with_suffix(damage_path.suffix + ".txt").write_text(
        "Damage photo\nCrack on washing machine door", encoding="utf-8"
    )
    ground_truth = {
        "expected_model_conflict": ["WM-420", "WM-421"],
        "serial_number": "NH420-77881",
        "purchase_date": "2026-08-18",
        "files": 5,
        "expected_fields": [
            ["manufacturer", "NordHome"],
            ["model", "WM-420"],
            ["model", "WM-421"],
            ["serial_number", "NH420-77881"],
            ["seller", "North Home Store"],
            ["purchase_date", "2026-08-18"],
            ["price", "549.90 EUR"],
            ["warranty_months", "24"],
        ],
    }
    (folder / "ground-truth.json").write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    return folder
