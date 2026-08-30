from __future__ import annotations

import argparse
import json
from pathlib import Path

from .demo import generate_demo
from .evaluate import evaluate_demo
from .export import export_package
from .pipeline import create_claim_package, inspect_folder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claimkit", description="Local warranty evidence organizer")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect evidence without writing output")
    inspect.add_argument("folder", type=Path)
    inspect.add_argument("--lang", choices=["en", "ru"], default="en")
    build = commands.add_parser("build", help="Create a reviewable evidence package")
    build.add_argument("folder", type=Path)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--lang", choices=["en", "ru"], default="en")
    build.add_argument("--description", default="")
    demo = commands.add_parser("demo", help="Generate and process synthetic evidence")
    demo.add_argument("--output", type=Path, default=Path("demo/generated"))
    evaluate = commands.add_parser("evaluate", help="Evaluate the deterministic synthetic fixture")
    evaluate.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "evaluate":
        evaluation_json = json.dumps(evaluate_demo(), indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(evaluation_json + "\n", encoding="utf-8")
        print(evaluation_json)
        return 0
    if args.command == "demo":
        evidence_dir = generate_demo(args.output / "evidence")
        package, evidence = create_claim_package(
            evidence_dir, "en", "A crack appeared on the washing machine door."
        )
        zip_path = export_package(args.output / "claim-package", package, evidence, "en")
        print(zip_path)
        return 0
    if args.command == "inspect":
        evidence, fields = inspect_folder(args.folder, args.lang)
        inspection_payload = {
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "fields": [field.model_dump(mode="json") for field in fields],
        }
        print(json.dumps(inspection_payload, ensure_ascii=False, indent=2))
        return 0
    package, evidence = create_claim_package(args.folder, args.lang, args.description)
    zip_path = export_package(args.output, package, evidence, args.lang)
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
