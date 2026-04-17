#!/usr/bin/env python3
"""Clean NAV history + summarize portfolio performance/P&L.

Outputs:
- paper/nav_clean.csv
- paper/performance_summary.json
- paper/position_pnl.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

NAV = Path("paper/nav.csv")
LEDGER = Path("paper/ledger.csv")
OUT_NAV = Path("paper/nav_clean.csv")
OUT_SUMMARY = Path("paper/performance_summary.json")
OUT_PNL = Path("paper/position_pnl.csv")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def pct(a: float, b: float) -> float:
    return (a / b - 1.0) if b else 0.0


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def clean_nav_rows(rows: list[dict]) -> list[dict]:
    # Keep the last row for each date, preserving input order semantics.
    by_date: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        d = r["date"]
        if d not in by_date:
            order.append(d)
        by_date[d] = r
    cleaned = [by_date[d] for d in order]
    cleaned.sort(key=lambda r: r["date"])
    return cleaned


def write_clean_nav(rows: list[dict]) -> None:
    if not rows:
        return
    with OUT_NAV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def summarize_nav(rows: list[dict]) -> dict:
    if not rows:
        return {}
    first = rows[0]
    last = rows[-1]
    nav0 = float(first["nav"])
    nav1 = float(last["nav"])
    b0 = float(first.get("benchmark_close") or 0)
    b1 = float(last.get("benchmark_close") or 0)

    # Daily returns on cleaned series
    daily = []
    prev = None
    for r in rows:
        nav = float(r["nav"])
        if prev is None:
            daily.append({"date": r["date"], "nav": nav, "return": 0.0})
        else:
            daily.append({"date": r["date"], "nav": nav, "return": pct(nav, prev)})
        prev = nav

    # Max drawdown from cleaned NAV
    peak = -1e18
    mdd = 0.0
    for r in rows:
        nav = float(r["nav"])
        peak = max(peak, nav)
        if peak > 0:
            mdd = min(mdd, nav / peak - 1.0)

    return {
        "startDate": first["date"],
        "endDate": last["date"],
        "startNav": nav0,
        "endNav": nav1,
        "portfolioReturnPct": pct(nav1, nav0) * 100.0,
        "benchmarkTicker": last.get("benchmark_ticker") or first.get("benchmark_ticker") or "",
        "benchmarkStart": b0,
        "benchmarkEnd": b1,
        "benchmarkReturnPct": (pct(b1, b0) * 100.0) if b0 and b1 else None,
        "relativeReturnPct": ((pct(nav1, nav0) - pct(b1, b0)) * 100.0) if b0 and b1 else None,
        "maxDrawdownPct": mdd * 100.0,
        "rows": len(rows),
        "dailyReturns": daily,
    }


def compute_position_pnl(rows: list[dict]) -> list[dict]:
    pos = defaultdict(lambda: {"qty": 0.0, "cost": 0.0, "realized": 0.0, "last_price": None})

    for r in rows:
        action = (r.get("action") or "").upper()
        ticker = (r.get("ticker") or "").upper()
        if action not in ("BUY", "SELL"):
            continue
        qty = float(r.get("qty") or 0)
        price = float(r.get("price") or 0)
        fees = float(r.get("fees") or 0)
        slip_bps = float(r.get("slippage_bps") or 0)
        notional = qty * price
        slip = abs(notional) * (slip_bps / 10000.0)
        total_cost = notional + fees + slip

        p = pos[ticker]
        p["last_price"] = price

        if action == "BUY":
            p["qty"] += qty
            p["cost"] += total_cost
        else:
            if p["qty"] > 0:
                avg_cost = p["cost"] / p["qty"]
            else:
                avg_cost = 0.0
            realized = (qty * price) - fees - slip - (qty * avg_cost)
            p["realized"] += realized
            p["qty"] -= qty
            p["cost"] -= qty * avg_cost

    out = []
    for ticker, p in sorted(pos.items()):
        qty = p["qty"]
        avg_cost = (p["cost"] / qty) if qty else 0.0
        last_price = p["last_price"] or 0.0
        market_value = qty * last_price
        unrealized = market_value - p["cost"]
        out.append(
            {
                "ticker": ticker,
                "qty": f"{qty:.6f}",
                "avg_cost": f"{avg_cost:.4f}",
                "last_price": f"{last_price:.4f}",
                "market_value": f"{market_value:.2f}",
                "cost_basis": f"{p['cost']:.2f}",
                "unrealized_pnl": f"{unrealized:.2f}",
                "realized_pnl": f"{p['realized']:.2f}",
            }
        )
    return out


def write_position_pnl(rows: list[dict]) -> None:
    if not rows:
        return
    with OUT_PNL.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()

    nav_rows = load_csv(NAV)
    clean = clean_nav_rows(nav_rows)
    write_clean_nav(clean)
    summary = summarize_nav(clean)
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    ledger_rows = load_csv(LEDGER)
    pnl_rows = compute_position_pnl(ledger_rows)
    write_position_pnl(pnl_rows)

    print("ok: true")
    print(f"nav_clean_rows: {len(clean)}")
    print(f"position_pnl_rows: {len(pnl_rows)}")
    if summary:
        print(f"portfolio_return_pct: {summary['portfolioReturnPct']:.4f}")
        if summary.get("relativeReturnPct") is not None:
            print(f"relative_return_pct: {summary['relativeReturnPct']:.4f}")


if __name__ == "__main__":
    main()
