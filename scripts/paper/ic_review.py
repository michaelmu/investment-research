#!/usr/bin/env python3
"""Weekly Investment Committee (IC) review memo generator.

This is the bot's self-reflection mechanism.

Outputs a markdown memo under paper/notes/ and suggests (but does not force)
process/rule changes.

Not financial advice.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

NAV = Path("paper/nav.csv")
RULES = Path("paper/rules.json")
PENDING = Path("paper/orders_pending.json")
OUT_DIR = Path("paper/notes")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_nav() -> list[dict]:
    if not NAV.exists():
        return []
    with NAV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def pct(a: float, b: float) -> float:
    return (a / b - 1.0) if b else 0.0


def pick_point(rows: list[dict], target: date) -> tuple[date, float, float] | None:
    # pick last point on/before target
    best = None
    for r in rows:
        d = parse_date(r["date"])
        if d <= target:
            best = (d, float(r["nav"]), float(r.get("benchmark_close") or 0))
        else:
            break
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-ending", default=date.today().isoformat())
    args = ap.parse_args()

    end = parse_date(args.week_ending)
    start = end - timedelta(days=7)
    start_4w = end - timedelta(days=28)

    rows = load_nav()
    if len(rows) < 2:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"ic-week-ending-{end.isoformat()}.md"
        out.write_text(
            "---\n"
            "layout: page\n"
            f"title: Paper bot IC review (week ending {end.isoformat()})\n"
            f"permalink: /paper/ic/{end.isoformat()}/\n"
            "---\n\n"
            f"## Paper bot — weekly IC review (week ending {end.isoformat()})\n\n"
            "**Not financial advice.**\n\n"
            "Insufficient NAV history yet to compute weekly endpoints. Keep running daily marks.\n\n"
            "### Process audit\n"
            "- Did we follow the rules?\n"
            "- Any data/execution weirdness?\n",
            encoding="utf-8",
        )
        print(f"ok: true\nfile: {out}\nnote: insufficient nav history")
        return

    rows.sort(key=lambda r: r["date"])

    p1 = pick_point(rows, end)
    p0 = pick_point(rows, start)
    p4 = pick_point(rows, start_4w)

    if not p1 or not p0:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"ic-week-ending-{end.isoformat()}.md"
        out.write_text(
            "---\n"
            "layout: page\n"
            f"title: Paper bot IC review (week ending {end.isoformat()})\n"
            f"permalink: /paper/ic/{end.isoformat()}/\n"
            "---\n\n"
            f"## Paper bot — weekly IC review (week ending {end.isoformat()})\n\n"
            "**Not financial advice.**\n\n"
            "Insufficient NAV history to compute weekly return endpoints for this week ending.\n\n"
            "### Process audit\n"
            "- Did we follow the rules?\n"
            "- Any data/execution weirdness?\n"
            "- Improvements to queue for next week:\n",
            encoding="utf-8",
        )
        print(f"ok: true\nfile: {out}\nnote: missing weekly endpoints")
        return

    _, nav1, b1 = p1
    _, nav0, b0 = p0

    w_ret = pct(nav1, nav0)
    w_bret = pct(b1, b0) if b0 and b1 else 0.0

    four_ret = None
    four_bret = None
    if p4 and p4[1] != 0:
        _, nav4, b4 = p4
        four_ret = pct(nav1, nav4)
        four_bret = pct(b1, b4) if b4 and b1 else None

    rules = load_rules()
    bench = rules.get("benchmark", "SPY")

    pending_txt = "none"
    if PENDING.exists():
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
        pending_txt = f"exec_date={pending.get('exec_date')} orders={len(pending.get('orders', []))}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"ic-week-ending-{end.isoformat()}.md"

    four_line = "- 4w: (insufficient history)\n"
    if four_ret is not None:
        four_line = f"- 4w: portfolio {four_ret*100:.2f}% vs {bench} {((four_bret or 0)*100):.2f}%\n"

    content = (
        "---\n"
        "layout: page\n"
        f"title: Paper bot IC review (week ending {end.isoformat()})\n"
        f"permalink: /paper/ic/{end.isoformat()}/\n"
        "---\n\n"
        f"## Paper bot — weekly IC review (week ending {end.isoformat()})\n\n"
        "**Not financial advice.**\n\n"
        "### Scoreboard\n"
        f"- 1w: portfolio {w_ret*100:.2f}% vs {bench} {w_bret*100:.2f}%\n"
        f"{four_line}"
        f"- End NAV: {nav1:,.2f}\n"
        f"- Pending: {pending_txt}\n\n"
        "### Process audit (answer honestly)\n"
        "- Did we follow the rules?\n"
        "- Any data/execution weirdness?\n"
        "- Were changes made too quickly?\n\n"
        "### Mistakes (process, not outcome)\n"
        "- (fill)\n\n"
        "### Improvements\n"
        "- Candidate hypothesis to test next week:\n"
        "- One change (max 1) OR explicitly 'no change':\n\n"
        "### Next week’s focus\n"
        "- (fill)\n"
    )

    out.write_text(content, encoding="utf-8")

    print(f"ok: true\nfile: {out}")


if __name__ == "__main__":
    main()
