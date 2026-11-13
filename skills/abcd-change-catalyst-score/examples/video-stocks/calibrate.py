#!/usr/bin/env python3
"""Verify the ACS on the stocks named in the episode.

Usage: python calibrate.py   (reads files next to this script)
Scores each stock at a point-in-time date and today, prints the forward price multiple,
then checks the classifier/gates against the labels the guest himself gave.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
import score  # noqa: E402

# label, point-in-time files, today files
CASES = [
    ("taril", ["taril-2023-04.fetched.json", "taril.analyst.json", "taril-2023-04.analyst.json"], ["taril.fetched.json", "taril.analyst.json"]),
    ("frontsp", ["frontsp-2023-04.fetched.json", "frontsp.analyst.json"], ["frontsp.fetched.json", "frontsp.analyst.json"]),
    ("jyotires", ["jyotires-2023-04.fetched.json", "jyotires.analyst.json"], ["jyotires.fetched.json", "jyotires.analyst.json"]),
    ("galaxybearings", ["galaxybearings-2023-04.fetched.json", "galaxybearings.analyst.json"], ["galaxybearings.fetched.json", "galaxybearings.analyst.json"]),
    ("balamines", ["balamines-2023-04.fetched.json", "balamines.analyst.json"], ["balamines.fetched.json", "balamines.analyst.json"]),
    ("renuka", ["renuka-2023-04.fetched.json", "renuka.analyst.json"], ["renuka.fetched.json", "renuka.analyst.json"]),
    ("yesbank", ["yesbank-2023-04.fetched.json", "yesbank.analyst.json"], ["yesbank.fetched.json", "yesbank.analyst.json"]),
    ("lt", ["lt-2023-04.fetched.json", "lt.analyst.json"], ["lt.fetched.json", "lt.analyst.json"]),
    ("manpasand", ["manpasand-2018-06.fetched.json", "manpasand.analyst.json"],
     ["manpasand-2018-06.fetched.json", "manpasand.analyst.json", "manpasand-2019-hindsight.analyst.json"]),
    ("panyamcem", None, ["panyamcem.fetched.json", "panyamcem.analyst.json"]),
]

# what the guest said, as checks on the point-in-time ("then") or today ("now") run
EXPECT = [
    ("lt", "then", "category", "A", "8:35-9:10, 14:15-14:52 L&T is the tracked, no-surprise A example"),
    ("yesbank", "then", "category", "D", "17:12-17:29 fallen glory available at Rs 10-15 = D"),
    ("renuka", "then", "category", "D", "18:21-18:44 Renuka at Rs 8 after promoter exit = D"),
    ("balamines", "then", "category", "B", "19:21-19:30 Balaji Amines had moved from C towards B"),
    ("taril", "then", "category", "C", "40:52 old company out of a bad phase with a Rs 1,500 cr order book (C by the rules)"),
    ("manpasand", "now", "verdict", "REJECT", "42:21-42:44 failure; auditor exit + promoter arrests (hindsight overlay)"),
    ("panyamcem", "now", "verdict", "REJECT", "58:35-58:59 funds moved to promoters' private concern"),
]


def load(names):
    data = {"inputs": {}}
    for n in names:
        part = json.loads((HERE / n).read_text(encoding="utf-8"))
        data["inputs"].update({k: v for k, v in part.pop("inputs", {}).items()
                               if isinstance(v, dict) and v.get("value") is not None})
        data.update({k: v for k, v in part.items() if v not in (None, "") and not k.startswith("_")})
    return data


def price(data):
    return (data["inputs"].get("current_price") or {}).get("value")


results = {}
print(f"{'stock':<15} {'date':<10} {'score':>5} {'cat':<10} {'cov':>4} {'P1/P2/P3/P4/P5/P6':<17} {'today':>5} {'cat now':<10} {'fwd x':>6}  verdict now")
for label, then_files, now_files in CASES:
    now = load(now_files)
    r1 = score.run(now)
    then = load(then_files) if then_files else None
    r0 = score.run(then) if then else None
    results[label] = {"then": r0, "now": r1}
    p0, p1 = (price(then) if then else None), price(now)
    fwd = f"{p1 / p0:.2f}" if p0 and p1 and now_files[0] != then_files[0] else "n/a"
    if r0:
        pil = "/".join(f"{v['score']:g}" for v in r0["pillars"].values())
        head = f"{label:<15} {r0['as_of']:<10} {r0['total']:>5g} {r0['category']:<10} {r0['evidence_coverage']:>4.0%} {pil:<17}"
    else:
        head = f"{label:<15} {'-':<10} {'':>5} {'':<10} {'':>4} {'':<17}"
    print(f"{head} {r1['total']:>5g} {r1['category']:<10} {fwd:>6}  {r1['verdict']}")

print("\nCHECKS AGAINST THE GUEST'S OWN LABELS")
fails = 0
for label, when, field, want, why in EXPECT:
    got = results[label][when][field]
    ok = got.startswith(want)
    fails += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:<10} {when:<4} {field}={got!r:<28} expected {want!r:<8} ({why})")
sys.exit(1 if fails else 0)
