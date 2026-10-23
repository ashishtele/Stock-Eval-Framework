#!/usr/bin/env python3
"""Snapshot a Screener.in company page: raw HTML plus parsed annual tables."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "screener"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
SECTIONS = ["profit-loss", "balance-sheet", "cash-flow", "quarters", "ratios", "shareholding"]


def clean_number(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-", "--"}:
        return None
    text = text.replace(",", "").replace("%", "").replace("₹", "").strip()
    text = re.sub(r"\s*Cr\.?$", "", text, flags=re.IGNORECASE)
    text = text.strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def parse_ratios(html: str) -> dict:
    block = re.search(r'(?s)<ul id="top-ratios".*?</ul>', html)
    if not block:
        return {}
    ratios: dict[str, object] = {}
    for item in re.findall(r"(?s)<li.*?</li>", block.group(0)):
        name = re.search(r'(?s)<span class="name">(.*?)</span>', item)
        if not name:
            continue
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", name.group(1))).strip()
        values = re.findall(r'(?s)<span class="nowrap value">(.*?)</span>', item)
        text = " ".join(
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip() for value in values
        )
        ratios[label] = text or None
    return ratios


def parse_section(html: str, section: str) -> list[dict]:
    block = re.search(rf'(?s)<section id="{re.escape(section)}".*?</section>', html)
    if not block:
        return []
    try:
        frames = pd.read_html(StringIO(block.group(0)))
    except ValueError:
        return []
    if not frames:
        return []
    frame = frames[0]
    frame = frame.dropna(axis=1, how="all").dropna(axis=0, how="all")
    header = [str(column).strip() for column in frame.columns]
    rows = []
    for _, row in frame.iterrows():
        label = str(row.iloc[0]).strip()
        if not label or label.lower() == "nan":
            continue
        values = {}
        for column, value in zip(header[1:], row.iloc[1:]):
            values[column] = clean_number(value)
        rows.append({"label": label, "values": values})
    return rows


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Snapshot a Screener.in company page.")
    parser.add_argument("slug", help="Screener company slug, e.g. APOLLOPIPE")
    parser.add_argument(
        "--variant",
        choices=["consolidated", "standalone"],
        default="consolidated",
        help="Which statement set to fetch",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--as-of", dest="as_of", default=None, help="Evaluation date (YYYY-MM-DD)")
    args = parser.parse_args()

    variant = "" if args.variant == "standalone" else f"{args.variant}/"
    url = f"https://www.screener.in/company/{args.slug}/{variant}"
    response = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    response.raise_for_status()

    as_of = args.as_of or datetime.now(timezone.utc).date().isoformat()
    out_dir = Path(args.out).resolve() / args.slug.upper() / as_of
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = out_dir / f"page-{args.variant}.html"
    html_path.write_text(response.text, encoding="utf-8")

    payload = {
        "slug": args.slug.upper(),
        "variant": args.variant,
        "url": url,
        "as_of": as_of,
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ratios": parse_ratios(response.text),
        "tables": {section: parse_section(response.text, section) for section in SECTIONS},
    }
    json_path = out_dir / f"screener-{args.variant}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"html:  {html_path}")
    print(f"json:  {json_path}")
    print(f"as_of: {as_of}  variant: {args.variant}")
    for label, value in payload["ratios"].items():
        print(f"  {label}: {value}")
    for section, rows in payload["tables"].items():
        print(f"  {section}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
