from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from claimkit.demo import generate_demo
from claimkit.pipeline import create_claim_package


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _frame(image: Image.Image, heading: str, details: list[str]) -> Image.Image:
    canvas = Image.new("RGB", (1000, 620), "#f6f8fa")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1000, 70), fill="#17212b")
    draw.text((30, 18), heading, fill="white", font=_font(30))
    preview = image.convert("RGB")
    preview.thumbnail((620, 500))
    canvas.paste(preview, (30, 95))
    y = 120
    for detail in details:
        draw.text((680, y), detail, fill="#1f2328", font=_font(22))
        y += 52
    return canvas


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "docs" / "demo.gif"
    with tempfile.TemporaryDirectory(prefix="claimkit-assets-") as temp:
        evidence_dir = generate_demo(Path(temp) / "evidence")
        package, _ = create_claim_package(evidence_dir, description="Crack on the appliance door")
        receipt = Image.open(evidence_dir / "01_receipt_en.png")
        warranty = Image.open(evidence_dir / "02_warranty_ru.png")
        damage = Image.open(evidence_dir / "05_damage_photo.png")
        conflict = package.conflicts[0]
        frames = [
            _frame(receipt, "1. Extract traceable fields", ["Receipt", "Model: WM-420", "Date: 2026-08-18"]),
            _frame(warranty, "2. Compare documents", ["Warranty card", "Model: WM-421", "Conflict detected"]),
            _frame(
                damage,
                "3. Build a reviewable package",
                [
                    f"{conflict.field_name}: {' / '.join(conflict.competing_values)}",
                    "PDF + manifest",
                    "Originals preserved",
                ],
            ),
        ]
        frames[0].save(output, save_all=True, append_images=frames[1:], duration=1500, loop=0, optimize=True)


if __name__ == "__main__":
    main()
