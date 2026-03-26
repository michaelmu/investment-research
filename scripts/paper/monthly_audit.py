#!/usr/bin/env python3
"""Monthly strategy audit.

Produces a markdown memo with higher-level metrics and prompts for strategy changes.

Not financial advice.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

NAV = Path("paper/nav.csv")
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


def max_drawdown(series: list[float]) -> float:
    peak = -1e18
    mdd = 0.0
    for x in series:
        peak = max(peak, x)
        if peak > 0:
            dd = x / peak - 1.0
            mdd = min(mdd, dd)
    return float(mdd)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=date.today().isoformat())
    args = ap.parse_args()

    asof = parse_date(args.asof)
    start = asof - timedelta(days=365)

    rows = load_nav()
    if len(rows) < 5:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"monthly-audit-{asof.isoformat()}.md"
        out.write_text(
            "---\n"
            "layout: page\n"
            f"title: Paper bot monthly audit ({asof.isoformat()})\n"
            f"permalink: /paper/audit/{asof.isoformat()}/\n"
            "---\n\n"
            f"## Paper bot — monthly audit (as of {asof.isoformat()})\n\n"
            "**Not financial advice.**\n\n"
            "Insufficient NAV history yet to run a meaningful monthly audit.\n",
            encoding="utf-8",
        )
        print(f"ok: true\nfile: {out}\nnote: insufficient nav history")
        return

    rows.sort(key=lambda r: r["date"])

    pts = []
    for r in rows:
        d = parse_date(r["date"])
        if start <= d <= asof:
            pts.append((d, float(r["nav"]), float(r.get("benchmark_close") or 0)))

    if len(pts) < 5:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"monthly-audit-{asof.isoformat()}.md"
        out.write_text(
            "---\n"
            "layout: page\n"
            f"title: Paper bot monthly audit ({asof.isoformat()})\n"
            f"permalink: /paper/audit/{asof.isoformat()}/\n"
            "---\n\n"
            f"## Paper bot — monthly audit (as of {asof.isoformat()})\n\n"
            "**Not financial advice.**\n\n"
            "Insufficient points in the selected window to compute audit metrics.\n",
            encoding="utf-8",
        )
        print(f"ok: true\nfile: {out}\nnote: insufficient points window")
        return

    d0, nav0, b0 = pts[0]
    d1, nav1, b1 = pts[-1]

    ret = pct(nav1, nav0)
    bret = pct(b1, b0) if b0 and b1 else 0.0

    nav_series = [p[1] for p in pts]
    mdd = max_drawdown(nav_series)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"monthly-audit-{asof.isoformat()}.md"

    out.write_text(
        "---\n"
        "layout: page\n"
        f"title: Paper bot monthly audit ({asof.isoformat()})\n"
        f"permalink: /paper/audit/{asof.isoformat()}/\n"
        "---\n\n"
        f"## Paper bot — monthly audit (as of {asof.isoformat()})\n\n"
        "**Not financial advice.**\n\n"
        "### Scoreboard (last ~12 months or since inception)\n"
        f"- Portfolio: {ret*100:.2f}%\n"
        f"- Benchmark (SPY close proxy): {bret*100:.2f}%\n"
        f"- Max drawdown (NAV-based): {mdd*100:.2f}%\n\n"
        "### Strategy health checks\n"
        "- Is performance coming from a repeatable edge or one regime?\n"
        "- Is turnover too high for the edge?\n"
        "- Did we overfit rules to recent noise?\n\n"
        "### Proposed experiments (next month)\n"
        "- Experiment A (hypothesis/change/metric/stop condition):\n"
        "- Experiment B (optional):\n\n"
        "### Rule changes (if any)\n"
        "- (remember: slow changes; record in CHANGELOG)\n",
        encoding="utf-8",
    )

    print(f"ok: true\nfile: {out}")


if __name__ == "__main__":
    main()
