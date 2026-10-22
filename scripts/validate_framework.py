#!/usr/bin/env python3
"""Validate framework.json files against the blocking gate in the extraction skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
TIMESTAMP = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
OPERATORS = {"<", "<=", ">", ">=", "==", "between", "in", "trend"}
SEVERITIES = {"fatal", "serious", "caution"}
KINDS = {"screen", "judgment"}
STATUSES = {"draft", "validated", "retired"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot read JSON: {exc}"]

    if not isinstance(data, dict):
        return ["top level must be an object"]

    for key in ("id", "name", "creator", "version", "status", "extracted_at", "sources", "criteria"):
        if key not in data:
            errors.append(f"missing required key: {key}")
    if errors:
        return errors

    if not KEBAB.match(data["id"]):
        errors.append(f"id is not kebab-case: {data['id']}")
    if not SEMVER.match(data["version"]):
        errors.append(f"version is not semver: {data['version']}")
    if data["status"] not in STATUSES:
        errors.append(f"invalid status: {data['status']}")

    sources = data.get("sources") or []
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        sid = source.get("source_id")
        if not sid:
            errors.append(f"sources[{index}] missing source_id")
            continue
        if sid in source_ids:
            errors.append(f"duplicate source_id: {sid}")
        source_ids.add(sid)
        if not source.get("url"):
            errors.append(f"sources[{index}] ({sid}) missing url")
        if not source.get("title"):
            errors.append(f"sources[{index}] ({sid}) missing title")

    seen_ids: dict[str, str] = {}

    def check_evidence(items, label: str, owner: str) -> None:
        if not items:
            errors.append(f"{label} '{owner}' has no evidence")
            return
        for position, item in enumerate(items):
            quote = (item.get("quote") or "").strip()
            if not quote:
                errors.append(f"{label} '{owner}' evidence[{position}] has an empty quote")
            timestamp = item.get("timestamp") or ""
            if not TIMESTAMP.match(timestamp):
                errors.append(f"{label} '{owner}' evidence[{position}] bad timestamp: {timestamp!r}")
            sid = item.get("source_id")
            if sid not in source_ids:
                errors.append(f"{label} '{owner}' evidence[{position}] unknown source_id: {sid!r}")

    def register(kind: str, item: dict) -> None:
        identifier = item.get("id") or ""
        if not KEBAB.match(identifier):
            errors.append(f"{kind} id is not kebab-case: {identifier!r}")
        if identifier in seen_ids:
            errors.append(f"duplicate id {identifier!r} in {kind} and {seen_ids[identifier]}")
        seen_ids[identifier] = kind

    for criterion in data.get("criteria") or []:
        cid = criterion.get("id", "<missing>")
        register("criterion", criterion)
        if not criterion.get("question"):
            errors.append(f"criterion '{cid}' missing question")
        kind = criterion.get("kind")
        if kind not in KINDS:
            errors.append(f"criterion '{cid}' has invalid kind: {kind!r}")
        if "disqualifying" not in criterion:
            errors.append(f"criterion '{cid}' must set disqualifying")
        check_evidence(criterion.get("evidence"), "criterion", cid)

        if kind == "screen":
            threshold = criterion.get("threshold")
            if not isinstance(threshold, dict):
                errors.append(f"screen criterion '{cid}' needs a threshold object")
            else:
                for key in ("metric", "operator", "value", "unit"):
                    if threshold.get(key) in (None, ""):
                        errors.append(f"screen criterion '{cid}' threshold missing {key}")
                if threshold.get("operator") not in OPERATORS:
                    errors.append(f"screen criterion '{cid}' invalid operator: {threshold.get('operator')!r}")
                if threshold.get("operator") == "between":
                    value = threshold.get("value")
                    if not (isinstance(value, list) and len(value) == 2):
                        errors.append(f"screen criterion '{cid}' 'between' needs a two-item value array")
        if kind == "judgment":
            scale = criterion.get("verdict_scale")
            if not (isinstance(scale, list) and scale):
                errors.append(f"judgment criterion '{cid}' needs a non-empty verdict_scale")

    for flag in data.get("red_flags") or []:
        fid = flag.get("id", "<missing>")
        register("red_flag", flag)
        if not flag.get("flag"):
            errors.append(f"red_flag '{fid}' missing flag text")
        if flag.get("severity") not in SEVERITIES:
            errors.append(f"red_flag '{fid}' invalid severity: {flag.get('severity')!r}")
        check_evidence(flag.get("evidence"), "red_flag", fid)

    for heuristic in data.get("heuristics") or []:
        hid = heuristic.get("id", "<missing>")
        register("heuristic", heuristic)
        if not heuristic.get("heuristic"):
            errors.append(f"heuristic '{hid}' missing text")
        if not heuristic.get("why_not_testable"):
            errors.append(f"heuristic '{hid}' missing why_not_testable")
        check_evidence(heuristic.get("evidence"), "heuristic", hid)

    for rule in data.get("sell_rules") or []:
        rid = rule.get("id", "<missing>")
        register("sell_rule", rule)
        if not rule.get("rule"):
            errors.append(f"sell_rule '{rid}' missing rule text")
        check_evidence(rule.get("evidence"), "sell_rule", rid)

    for index, tension in enumerate(data.get("tensions") or []):
        for key in ("topic", "statement", "counter_evidence"):
            if not tension.get(key):
                errors.append(f"tensions[{index}] missing {key}")

    return errors


def discover(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(
        path
        for path in target.rglob("framework.json")
        if "_template" not in path.parts
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check framework.json against the extraction gate.")
    parser.add_argument("target", nargs="?", default=str(ROOT / "skills" / "frameworks"))
    args = parser.parse_args()

    paths = discover(Path(args.target).resolve())
    if not paths:
        print(f"No framework.json found under {args.target}", file=sys.stderr)
        return 2

    failed = 0
    for path in paths:
        errors = validate(path)
        if errors:
            failed += 1
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK   {path}")

    print(f"\n{len(paths) - failed}/{len(paths)} frameworks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
