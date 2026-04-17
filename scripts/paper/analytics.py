#!/usr/bin/env python3
"""Portfolio analytics for the paper bot.

Outputs:
- paper/analytics_summary.json
- paper/sleeve_pnl.csv
- paper/exposure_history.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

LEDGER = Path("paper/ledger.csv")
NAV_CLEAN = Path("paper/nav_clean.csv")
OUT_SUMMARY = Path("paper/analytics_summary.json")
OUT_SLEEVE = Path("paper/sleeve_pnl.csv")
OUT_EXPOSURE = Path("paper/exposure_history.csv")
SLEEVE_NAV = Path("paper/sleeve_nav.csv")


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def group_trades_by_ticker(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if (r.get("action") or "").upper() in ("BUY", "SELL"):
            out[(r.get("ticker") or "").upper()].append(r)
    for t in out:
        out[t].sort(key=lambda r: r.get("timestamp_et") or "")
    return out


def compute_round_trip_stats(rows: list[dict]) -> dict:
    groups = group_trades_by_ticker(rows)
    closed = []

    for ticker, trades in groups.items():
        qty = 0.0
        cost = 0.0
        strategy_hint = ""
        entry_ts = None
        for r in trades:
            action = (r.get("action") or "").upper()
            q = float(r.get("qty") or 0)
            price = float(r.get("price") or 0)
            fees = float(r.get("fees") or 0)
            slip = abs(q * price) * (float(r.get("slippage_bps") or 0) / 10000.0)
            strategy_hint = strategy_hint or (r.get("strategy_id") or "")
            if action == "BUY":
                if qty == 0:
                    entry_ts = r.get("timestamp_et")
                qty += q
                cost += q * price + fees + slip
            elif action == "SELL" and qty > 0:
                avg = cost / qty if qty else 0.0
                realized = (q * price) - fees - slip - (q * avg)
                qty -= q
                cost -= q * avg
                if qty <= 1e-9:
                    closed.append(
                        {
                            "ticker": ticker,
                            "strategy_id": strategy_hint,
                            "entry_ts": entry_ts or r.get("timestamp_et") or "",
                            "exit_ts": r.get("timestamp_et") or "",
                            "realized_pnl": realized,
                        }
                    )
                    qty = 0.0
                    cost = 0.0
                    entry_ts = None
                    strategy_hint = ""

    wins = [x for x in closed if x["realized_pnl"] > 0]
    losses = [x for x in closed if x["realized_pnl"] < 0]
    return {
        "closedTrades": len(closed),
        "hitRatePct": (len(wins) / len(closed) * 100.0) if closed else None,
        "avgWin": (sum(x["realized_pnl"] for x in wins) / len(wins)) if wins else None,
        "avgLoss": (sum(x["realized_pnl"] for x in losses) / len(losses)) if losses else None,
        "trades": closed,
    }


def compute_turnover(rows: list[dict], nav_rows: list[dict]) -> dict:
    notional = 0.0
    for r in rows:
        if (r.get("action") or "").upper() in ("BUY", "SELL"):
            notional += abs(float(r.get("notional") or 0))
    avg_nav = None
    if nav_rows:
        vals = [float(r.get("nav") or 0) for r in nav_rows if (r.get("nav") or "")]
        if vals:
            avg_nav = sum(vals) / len(vals)
    return {
        "grossTradedNotional": notional,
        "averageNav": avg_nav,
        "turnoverPct": (notional / avg_nav * 100.0) if avg_nav else None,
    }


def compute_sleeve_pnl(rows: list[dict]) -> list[dict]:
    sleeve = defaultdict(lambda: {"buy_notional": 0.0, "sell_notional": 0.0, "realized_pnl": 0.0})
    positions = defaultdict(lambda: {"qty": 0.0, "cost": 0.0, "strategy_id": ""})

    for r in rows:
        action = (r.get("action") or "").upper()
        ticker = (r.get("ticker") or "").upper()
        sid = (r.get("strategy_id") or positions[ticker]["strategy_id"] or "UNASSIGNED")
        if action not in ("BUY", "SELL"):
            continue
        q = float(r.get("qty") or 0)
        price = float(r.get("price") or 0)
        fees = float(r.get("fees") or 0)
        slip = abs(q * price) * (float(r.get("slippage_bps") or 0) / 10000.0)
        p = positions[ticker]
        if action == "BUY":
            p["strategy_id"] = sid
            p["qty"] += q
            p["cost"] += q * price + fees + slip
            sleeve[sid]["buy_notional"] += q * price
        else:
            use_sid = p["strategy_id"] or sid
            avg = p["cost"] / p["qty"] if p["qty"] else 0.0
            realized = (q * price) - fees - slip - (q * avg)
            p["qty"] -= q
            p["cost"] -= q * avg
            sleeve[use_sid]["sell_notional"] += q * price
            sleeve[use_sid]["realized_pnl"] += realized

    out = []
    for sid, vals in sorted(sleeve.items()):
        out.append(
            {
                "strategy_id": sid,
                "buy_notional": f"{vals['buy_notional']:.2f}",
                "sell_notional": f"{vals['sell_notional']:.2f}",
                "realized_pnl": f"{vals['realized_pnl']:.2f}",
            }
        )
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fieldnames = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def compute_exposure_history(rows: list[dict], nav_rows: list[dict]) -> list[dict]:
    sleeve_rows = load_csv(SLEEVE_NAV)
    by_date = defaultdict(list)
    for r in sleeve_rows:
        by_date[r.get("date") or ""].append(r)

    exposures = []
    for nav in nav_rows:
        d = nav["date"]
        nav_value = float(nav.get("nav") or 0)
        row = {"date": d, "nav": f"{nav_value:.2f}"}
        for sr in by_date.get(d, []):
            sid = (sr.get("sleeve") or "").strip() or "UNASSIGNED"
            if sid == "CASH":
                continue
            mv = float(sr.get("market_value") or 0)
            row[f"{sid}_mv"] = f"{mv:.2f}"
            row[f"{sid}_pct"] = f"{(mv / nav_value * 100.0):.2f}" if nav_value else ""
        exposures.append(row)
    return exposures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()

    ledger = load_csv(LEDGER)
    nav = load_csv(NAV_CLEAN)

    rt = compute_round_trip_stats(ledger)
    turnover = compute_turnover(ledger, nav)
    sleeve = compute_sleeve_pnl(ledger)
    exposure = compute_exposure_history(ledger, nav)

    write_csv(OUT_SLEEVE, sleeve)
    write_csv(OUT_EXPOSURE, exposure)

    latest_sleeve_nav = {}
    sleeve_rows = load_csv(SLEEVE_NAV)
    if sleeve_rows:
        latest_date = max(r.get("date") or "" for r in sleeve_rows)
        portfolio_nav = None
        if nav:
            portfolio_nav = float(nav[-1].get("nav") or 0)
        for r in sleeve_rows:
            if r.get("date") == latest_date:
                mv = float(r.get("market_value") or 0)
                latest_sleeve_nav[r.get("sleeve") or "UNASSIGNED"] = {
                    "cash": float(r.get("cash") or 0),
                    "marketValue": mv,
                    "nav": float(r.get("nav") or 0),
                    "exposurePct": (mv / portfolio_nav * 100.0) if portfolio_nav else None,
                }

    summary = {
        "turnover": turnover,
        "tradeStats": {
            "closedTrades": rt["closedTrades"],
            "hitRatePct": rt["hitRatePct"],
            "avgWin": rt["avgWin"],
            "avgLoss": rt["avgLoss"],
        },
        "sleeves": sleeve,
        "latestSleeveNav": latest_sleeve_nav,
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("ok: true")
    print(f"sleeves: {len(sleeve)}")
    print(f"closed_trades: {rt['closedTrades']}")
    if turnover.get('turnoverPct') is not None:
        print(f"turnover_pct: {turnover['turnoverPct']:.2f}")


if __name__ == "__main__":
    main()
