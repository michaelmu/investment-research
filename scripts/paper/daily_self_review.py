#!/usr/bin/env python3
"""Daily self-review loop for the paper bot.

Goal: improve returns without thrashing the rules.
- Reviews recent performance + analytics + data quality
- Writes a daily memo under paper/notes/
- Proposes at most one concrete improvement candidate
- Can auto-execute high-severity operational fixes
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

NAV = Path("paper/nav_clean.csv")
PERF = Path("paper/performance_summary.json")
ANALYTICS = Path("paper/analytics_summary.json")
LEDGER = Path("paper/ledger.csv")
BACKLOG = Path("paper/improvements/backlog.md")
RULES = Path("paper/rules.json")
CHANGELOG = Path("paper/improvements/CHANGELOG.md")
OUT_DIR = Path("paper/notes")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pick_nav_point(rows: list[dict], d: date) -> dict | None:
    best = None
    for r in rows:
        rd = parse_date(r["date"])
        if rd <= d:
            best = r
        else:
            break
    return best


def pct(a: float, b: float) -> float:
    return (a / b - 1.0) if b else 0.0


def recent_fill_stats(ledger_rows: list[dict], asof: date, window_days: int = 14) -> dict:
    start = asof - timedelta(days=window_days)
    counts = {"exact": 0, "latest_available": 0, "stale_fallback": 0, "unknown": 0}
    total = 0
    for r in ledger_rows:
        ts = r.get("timestamp_et") or ""
        if not ts or (r.get("action") or "").upper() not in ("BUY", "SELL"):
            continue
        d = parse_date(ts.split("T", 1)[0])
        if d < start or d > asof:
            continue
        q = (r.get("fill_quality") or "unknown").strip() or "unknown"
        counts[q] = counts.get(q, 0) + 1
        total += 1
    counts["total"] = total
    return counts


def propose_improvement(perf: dict, analytics: dict, fill_stats: dict) -> dict:
    rel = perf.get("relativeReturnPct")
    turnover = ((analytics.get("turnover") or {}).get("turnoverPct"))
    stale = fill_stats.get("stale_fallback", 0)
    total_fills = fill_stats.get("total", 0)
    hit_rate = ((analytics.get("tradeStats") or {}).get("hitRatePct"))

    if stale and total_fills and stale / max(total_fills, 1) >= 0.25:
        return {
            "title": "Reduce stale-fill risk in execution path",
            "hypothesis": "If stale fills remain a meaningful share of trades, execution quality will distort the learning loop and hurt returns.",
            "change": "Tighten execution to require provider freshness on trading days or defer fills instead of using stale fallback when lag exceeds threshold.",
            "metric": "stale_fallback share of fills < 10% over rolling 2 weeks",
            "risk": "More deferred orders / lower responsiveness.",
            "severity": 9,
            "confidence": 8,
            "autoExecutable": True,
            "actionKey": "tighten_stale_fill_lag",
        }

    if rel is not None and rel < -5 and turnover is not None and turnover < 60:
        return {
            "title": "Increase selectivity before increasing aggression",
            "hypothesis": "The current signal mix may be too permissive; improving ranking/selectivity should help returns more than simply increasing exposure.",
            "change": "Raise composite-score threshold and require stronger trend confirmation before new positions.",
            "metric": "relative return improves over next 2-4 weeks without turnover spike > 25%",
            "risk": "May reduce exposure too much and miss rebounds.",
            "severity": 6,
            "confidence": 5,
            "autoExecutable": False,
            "actionKey": "increase_selectivity",
        }

    if hit_rate is not None and hit_rate >= 70 and rel is not None and rel < 0:
        return {
            "title": "Improve winner sizing",
            "hypothesis": "If hit rate is decent but relative returns still lag, position sizing / exposure may be the bottleneck.",
            "change": "Test slightly larger starter positions or faster scaling for high-score names.",
            "metric": "portfolio return improves without drawdown worsening materially",
            "risk": "Bigger sizing magnifies signal errors.",
            "severity": 5,
            "confidence": 4,
            "autoExecutable": False,
            "actionKey": "improve_winner_sizing",
        }

    return {
        "title": "No high-confidence daily rule change",
        "hypothesis": "Daily review is mainly for surfacing evidence, not changing rules every day.",
        "change": "Carry current rules forward and revisit in weekly IC review.",
        "metric": "n/a",
        "risk": "Slow response to genuine regime change.",
        "severity": 1,
        "confidence": 1,
        "autoExecutable": False,
        "actionKey": "none",
    }


def maybe_execute(proposal: dict, asof: date) -> dict:
    decision = {"executed": False, "reason": "not eligible", "changes": []}
    if not proposal.get("autoExecutable"):
        decision["reason"] = "proposal not auto-executable"
        return decision
    if proposal.get("severity", 0) < 8 or proposal.get("confidence", 0) < 7:
        decision["reason"] = "severity/confidence below auto-execute threshold"
        return decision

    rules = load_json(RULES)
    changed = False
    if proposal.get("actionKey") == "tighten_stale_fill_lag":
        execution = rules.setdefault("execution", {})
        current = execution.get("maxStaleLagDays")
        target = 1
        if current != target:
            execution["maxStaleLagDays"] = target
            rules["version"] = int(rules.get("version", 0)) + 1
            rules["updatedAt"] = asof.isoformat()
            save_json(RULES, rules)
            changed = True
            decision["changes"].append("execution.maxStaleLagDays=1")
            with CHANGELOG.open("a", encoding="utf-8") as f:
                f.write(
                    f"\n- **{asof.isoformat()} (daily self-review auto-execution)** — Tighten stale-fill policy.\n"
                    f"  - Hypothesis: stale fallback fills are degrading execution quality and contaminating the learning loop.\n"
                    f"  - Change: `execution.maxStaleLagDays` = `1`.\n"
                    f"  - Metric: stale_fallback share of fills < 10% over rolling 2 weeks.\n"
                    f"  - Risk: more deferred orders / lower responsiveness.\n"
                    f"  - Evaluation date: **{(asof + timedelta(days=7)).isoformat()}**.\n"
                )
    decision["executed"] = changed
    decision["reason"] = "applied" if changed else "already at desired setting"
    return decision


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--append-backlog", action="store_true", help="append proposed improvement to backlog when confidence is high")
    args = ap.parse_args()

    asof = parse_date(args.asof)
    nav_rows = load_csv(NAV)
    perf = load_json(PERF)
    analytics = load_json(ANALYTICS)
    ledger_rows = load_csv(LEDGER)

    p1 = pick_nav_point(nav_rows, asof)
    p5 = pick_nav_point(nav_rows, asof - timedelta(days=5))
    one_week = None
    if p1 and p5:
        one_week = pct(float(p1["nav"]), float(p5["nav"])) * 100.0

    fill_stats = recent_fill_stats(ledger_rows, asof)
    proposal = propose_improvement(perf, analytics, fill_stats)
    decision = maybe_execute(proposal, asof)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"daily-self-review-{asof.isoformat()}.md"

    content = (
        "---\n"
        "layout: page\n"
        f"title: Daily self review ({asof.isoformat()})\n"
        f"permalink: /paper/daily-review/{asof.isoformat()}/\n"
        "---\n\n"
        f"## Paper bot — daily self review ({asof.isoformat()})\n\n"
        "**Not financial advice.**\n\n"
        "### Quick scoreboard\n"
        f"- Portfolio return since inception: {(perf.get('portfolioReturnPct')) if perf else None}\n"
        f"- Relative return vs benchmark: {(perf.get('relativeReturnPct')) if perf else None}\n"
        f"- Last ~5 trading days return: {one_week}\n"
        f"- Turnover (% avg NAV): {((analytics.get('turnover') or {}).get('turnoverPct')) if analytics else None}\n"
        f"- Closed trades / hit rate: {((analytics.get('tradeStats') or {}).get('closedTrades')) if analytics else None} / {((analytics.get('tradeStats') or {}).get('hitRatePct')) if analytics else None}\n\n"
        "### Execution quality\n"
        f"- Fills in last 14 days: {fill_stats.get('total', 0)}\n"
        f"- exact: {fill_stats.get('exact', 0)}\n"
        f"- latest_available: {fill_stats.get('latest_available', 0)}\n"
        f"- stale_fallback: {fill_stats.get('stale_fallback', 0)}\n"
        f"- unknown: {fill_stats.get('unknown', 0)}\n\n"
        "### Proposed next improvement\n"
        f"- Title: {proposal['title']}\n"
        f"- Hypothesis: {proposal['hypothesis']}\n"
        f"- Change: {proposal['change']}\n"
        f"- Metric: {proposal['metric']}\n"
        f"- Risk: {proposal['risk']}\n"
        f"- Severity / confidence: {proposal.get('severity')} / {proposal.get('confidence')}\n"
        f"- Auto-executable: {proposal.get('autoExecutable')}\n\n"
        "### Daily decision\n"
        f"- Executed: {decision['executed']}\n"
        f"- Reason: {decision['reason']}\n"
        f"- Changes: {', '.join(decision['changes']) if decision['changes'] else 'none'}\n\n"
        "### Daily discipline\n"
        "- Daily self-review may auto-execute only high-severity, high-confidence operational fixes. Strategy preference changes still defer to the weekly IC loop.\n"
    )
    out.write_text(content, encoding="utf-8")

    if args.append_backlog and proposal["title"] != "No high-confidence daily rule change":
        BACKLOG.parent.mkdir(parents=True, exist_ok=True)
        with BACKLOG.open("a", encoding="utf-8") as f:
            f.write(
                f"\n- **{asof.isoformat()}** — {proposal['title']}\n"
                f"  - Hypothesis: {proposal['hypothesis']}\n"
                f"  - Change: {proposal['change']}\n"
                f"  - Metric: {proposal['metric']}\n"
                f"  - Risk / failure mode: {proposal['risk']}\n"
                f"  - Decision date: {(asof + timedelta(days=7)).isoformat()}\n"
            )

    print("ok: true")
    print(f"file: {out}")
    print(f"proposal: {proposal['title']}")
    print(f"executed: {decision['executed']}")
    print(f"decision_reason: {decision['reason']}")


if __name__ == "__main__":
    main()
