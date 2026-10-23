#!/usr/bin/env python3
"""Validate evaluation.json files against schema/evaluation.schema.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate recorded evaluations.")
    parser.add_argument("paths", nargs="*", help="Files or directories; defaults to evals/")
    args = parser.parse_args()

    schema = json.loads((ROOT / "schema" / "evaluation.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())

    targets: list[Path] = []
    for raw in args.paths or [str(ROOT / "evals")]:
        path = Path(raw)
        if path.is_dir():
            targets.extend(sorted(path.rglob("*.json")))
        elif path.exists():
            targets.append(path)
        else:
            print(f"missing: {path}", file=sys.stderr)
            return 1

    failures = 0
    for path in targets:
        try:
            validator.validate(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(f"FAIL {path}: invalid JSON: {exc}")
            failures += 1
        except jsonschema.ValidationError as exc:
            location = "/".join(str(part) for part in exc.absolute_path)
            print(f"FAIL {path}: {exc.message} at {location or '<root>'}")
            failures += 1
        else:
            print(f"OK   {path}")

    print(f"\n{len(targets) - failures}/{len(targets)} evaluations passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
