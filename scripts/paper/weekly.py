#!/usr/bin/env python3
"""Generate a weekly public review note from nav.csv.

This is a lightweight first pass: performance vs benchmark + basic stats.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

NAV = Path("paper/nav_clean.csv")
OUT_DIR = Path("paper/notes")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_nav() -> list[dict]:
    if not NAV.exists():
        return []
    with NAV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(a: float, b: float) -> float:
    return (a / b - 1.0) if b else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-ending", default=date.today().isoformat(), help="YYYY-MM-DD")
    args = ap.parse_args()

    end = parse_date(args.week_ending)
    start = end - timedelta(days=7)

    rows = load_nav()
    pts = []
    for r in rows:
        d = parse_date(r["date"])
        if start <= d <= end:
            pts.append((d, float(r["nav"]), float(r.get("benchmark_close") or 0)))

    if len(pts) < 2:
        raise SystemExit("Not enough nav points for weekly review. Run mark.py daily.")

    pts.sort(key=lambda x: x[0])
    d0, nav0, b0 = pts[0]
    d1, nav1, b1 = pts[-1]

    ret = pct(nav1, nav0)
    bret = pct(b1, b0) if b0 and b1 else 0.0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"week-ending-{end.isoformat()}.md"

    out.write_text(
        "---\n"
        "layout: page\n"
        f"title: Weekly paper review ({end.isoformat()})\n"
        f"permalink: /paper/weekly/{end.isoformat()}/\n"
        "---\n\n"
        f"## Weekly paper trading review (week ending {end.isoformat()})\n\n"
        "**Not financial advice.**\n\n"
        "### Performance\n"
        f"- Portfolio NAV: {nav0:,.2f} → {nav1:,.2f} (**{ret*100:.2f}%**)\n"
        f"- Benchmark close: {b0:,.2f} → {b1:,.2f} (**{bret*100:.2f}%**)\n\n"
        "### Process notes (fill in weekly)\n"
        "- What worked:\n"
        "- What didn’t:\n"
        "- One rule/process change to test next week:\n",
        encoding="utf-8",
    )

    print(f"ok: true\nfile: {out}")


if __name__ == "__main__":
    main()
