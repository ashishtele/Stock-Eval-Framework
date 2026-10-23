#!/usr/bin/env python3
"""Check the metric registry against the frameworks it claims to cover."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASES = {"creator_stated", "derived", "proxy"}


def main() -> int:
    registry = json.loads((ROOT / "metrics" / "registry.json").read_text(encoding="utf-8"))
    metrics = registry.get("metrics") or []
    errors: list[str] = []
    seen: set[str] = set()

    for metric in metrics:
        identifier = metric.get("id", "<missing>")
        for key in ("id", "criterion_id", "formula", "unit", "basis", "anchors"):
            if key not in metric:
                errors.append(f"metric '{identifier}' missing {key}")
        if identifier in seen:
            errors.append(f"duplicate metric id: {identifier}")
        seen.add(identifier)
        if metric.get("basis") not in BASES:
            errors.append(f"metric '{identifier}' has invalid basis: {metric.get('basis')!r}")
        if metric.get("available", True) is False and not metric.get("reason"):
            errors.append(f"metric '{identifier}' is unavailable but has no reason")
        anchors = metric.get("anchors") or []
        if len(anchors) < 2:
            errors.append(f"metric '{identifier}' needs at least two anchors")
        if any("value" not in anchor or "score" not in anchor for anchor in anchors):
            errors.append(f"metric '{identifier}' has an anchor without value/score")

    by_criterion = {metric.get("criterion_id"): metric for metric in metrics}
    for framework_id in registry.get("frameworks") or []:
        path = ROOT / "skills" / "frameworks" / framework_id / "framework.json"
        if not path.exists():
            errors.append(f"framework not found: {framework_id}")
            continue
        framework = json.loads(path.read_text(encoding="utf-8"))
        for criterion in framework.get("criteria") or []:
            if criterion["id"] not in by_criterion:
                errors.append(f"{framework_id}: no metric for criterion '{criterion['id']}'")
        known = {criterion["id"] for criterion in framework.get("criteria") or []}
        for metric in metrics:
            if metric.get("criterion_id") not in known:
                errors.append(
                    f"metric '{metric.get('id')}' points at unknown criterion "
                    f"'{metric.get('criterion_id')}' in {framework_id}"
                )

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        print(f"\n{len(errors)} problem(s)")
        return 1

    available = sum(metric.get("available", True) for metric in metrics)
    print(f"OK   {len(metrics)} metrics registered, {available} available now")
    print(f"OK   frameworks covered: {', '.join(registry.get('frameworks') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
