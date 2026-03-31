#!/usr/bin/env python3
"""Autonomous paper-trading bot (v1).

Design goals:
- Auditable: all actions recorded in paper/ledger.csv
- Conservative execution: fills assumed at next open (recorded after data is available)
- Improvable: rules live in paper/rules.json and can version over time

v1 strategy (price-only, ETF rotation):
- Two sleeves (strategy_id tags): QC and AI23
- Weekly rebalance on Fridays after market close
- Momentum filter: 12m momentum; if negative, allocate to cash

This is intentionally simple: it gives the bot something real to do while we
layer in thesis-driven single-name ideas later.

Not financial advice.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from stooq import fetch_daily_csv, load_bars
from signals import momentum_close_to_close

ROOT = Path(".")
PAPER = Path("paper")
RULES = PAPER / "rules.json"
LEDGER = PAPER / "ledger.csv"
PENDING = PAPER / "orders_pending.json"


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def is_friday(d: date) -> bool:
    return d.weekday() == 4


def last_bar_on_or_before(ticker: str, d: date):
    p = fetch_daily_csv(ticker)
    bars = load_bars(Path(p))
    last = None
    for b in bars:
        if b.d <= d:
            last = b
        else:
            break
    return last


def open_on(ticker: str, d: date):
    p = fetch_daily_csv(ticker)
    bars = load_bars(Path(p))
    for b in bars:
        if b.d == d:
            return b.open
    return None


def load_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    with LEDGER.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_positions_and_cash(rows: list[dict]) -> tuple[dict[str, float], float]:
    from mark import compute_positions  # reuse logic

    return compute_positions(rows)


def portfolio_value(positions: dict[str, float], cash: float, d: date) -> float:
    nav = cash
    for t, q in positions.items():
        b = last_bar_on_or_before(t, d)
        if b:
            nav += b.close * q
    return float(nav)


def write_pending(obj: dict) -> None:
    PENDING.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def load_pending() -> dict | None:
    if not PENDING.exists():
        return None
    return json.loads(PENDING.read_text(encoding="utf-8"))


def append_ledger(row: dict) -> None:
    # minimal append; ledger.py is nicer but we keep this self-contained
    if not LEDGER.exists() or LEDGER.stat().st_size == 0:
        raise RuntimeError("ledger missing header; run ./scripts/paper/ledger.py init")
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp_et",
                "action",
                "ticker",
                "qty",
                "price",
                "fees",
                "slippage_bps",
                "notional",
                "strategy_id",
                "reason_code",
                "note",
                "source_doc",
            ],
        )
        w.writerow(row)


def execute_pending_if_possible(asof: date, slippage_bps: float) -> tuple[list[str], int, int]:
    """Try to execute pending orders scheduled for `asof` at that day's open.

    Returns: (msgs, filled_count, remaining_count)

    IMPORTANT: if price data is missing for any order, we keep the order pending.
    """
    msgs: list[str] = []
    pending = load_pending()
    if not pending:
        return msgs, 0, 0

    exec_date = parse_date(pending["exec_date"])
    if exec_date != asof:
        return msgs, 0, 0

    orders = pending.get("orders", [])
    if not orders:
        PENDING.unlink(missing_ok=True)
        return msgs, 0, 0

    ts = datetime.now().isoformat(timespec="seconds")

    filled = 0
    remaining: list[dict] = []

    for o in orders:
        ticker = o["ticker"].upper()
        qty = float(o["qty"])
        if qty == 0:
            continue
        px = open_on(ticker, asof)
        if px is None:
            msgs.append(f"WARN: no open price for {ticker} on {asof}; keeping pending")
            remaining.append(o)
            continue

        action = "BUY" if qty > 0 else "SELL"
        qabs = abs(qty)
        notional = qabs * float(px)

        append_ledger(
            {
                "timestamp_et": ts,
                "action": action,
                "ticker": ticker,
                "qty": f"{qabs:.6f}",
                "price": f"{float(px):.4f}",
                "fees": "0",
                "slippage_bps": f"{slippage_bps:.2f}",
                "notional": f"{notional:.2f}",
                "strategy_id": o.get("strategy_id", ""),
                "reason_code": "rebalance",
                "note": o.get("note", ""),
                "source_doc": "",
            }
        )
        filled += 1

    if remaining:
        pending["orders"] = remaining
        # keep same exec_date; the fill-checker will retry later when data appears
        write_pending(pending)
        msgs.append(f"Executed {filled} order(s); {len(remaining)} still pending.")
    else:
        PENDING.unlink(missing_ok=True)
        msgs.append(f"Executed {filled} pending order(s) for {asof} (filled at open).")

    return msgs, filled, len(remaining)


def build_targets(asof: date, rules: dict) -> dict:
    # Two sleeves with distinct ETF universes.
    sleeve_weights = {"QC": 0.5, "AI23": 0.5}

    universes = {
        "QC": ["SPY", "QQQ", "DIA", "IWM", "IEF", "TLT", "SHY"],
        "AI23": ["XLK", "XLI", "XLV", "XLE", "XLF", "XLU", "XLP", "XLY"],
    }

    # Compute 12m momentum and pick top 2 per sleeve if positive.
    lookback = 252
    targets: dict[str, dict] = {}

    for sid, tickers in universes.items():
        moms = []
        for t in tickers:
            m = momentum_close_to_close(t, asof, lookback_days=lookback)
            if m:
                moms.append(m)
        moms.sort(key=lambda x: x.return_pct, reverse=True)

        picks = [m for m in moms[:2] if m.return_pct > 0]
        if not picks:
            targets[sid] = {"cash": 1.0, "picks": []}
            continue

        w_each = 1.0 / len(picks)
        targets[sid] = {
            "cash": 0.0,
            "picks": [{"ticker": p.ticker, "weight": w_each, "mom": p.return_pct} for p in picks],
        }

    # Scale to portfolio weights
    out = {"asof": asof.isoformat(), "sleeves": {}}
    for sid, t in targets.items():
        out["sleeves"][sid] = {
            "sleeve_weight": sleeve_weights[sid],
            "targets": t,
        }
    return out


def compute_rebalance_orders(asof: date, rules: dict, targets: dict) -> list[dict]:
    rows = read_ledger()
    positions, cash = compute_positions_and_cash(rows)
    nav = portfolio_value(positions, cash, asof)

    # Current market values by ticker
    mv = {}
    for t, q in positions.items():
        b = last_bar_on_or_before(t, asof)
        mv[t] = (b.close * q) if b else 0.0

    desired_mv = defaultdict_float()

    # Build desired market value per ticker
    for sid, sleeve in targets["sleeves"].items():
        sleeve_nav = nav * float(sleeve["sleeve_weight"])
        picks = sleeve["targets"].get("picks", [])
        for p in picks:
            desired_mv[p["ticker"].upper()] += sleeve_nav * float(p["weight"])

    # Convert to orders in shares using close price (execution is next open, but sizing via close)
    orders = []
    max_pos_pct = float(rules["portfolio"]["maxPositionPct"])
    starter_pct = float(rules["portfolio"]["starterPositionPct"])

    for t, target_val in desired_mv.items():
        b = last_bar_on_or_before(t, asof)
        if not b or b.close <= 0:
            continue
        # cap per-position
        cap = nav * max_pos_pct
        target_val = min(target_val, cap)

        cur_val = float(mv.get(t, 0.0))
        diff = target_val - cur_val

        # ignore small diffs (<0.5% NAV)
        if abs(diff) < nav * 0.005:
            continue

        shares = diff / b.close

        # If opening a new position, don't exceed starter size
        if t not in positions and target_val > nav * starter_pct:
            shares = (nav * starter_pct) / b.close

        # round shares to 3 decimals (allows fractional ETF shares in paper)
        shares = float(round(shares, 3))
        if shares == 0:
            continue

        # pick strategy_id based on which sleeve contains it
        sid = "QC" if t in [p["ticker"].upper() for p in targets["sleeves"]["QC"]["targets"].get("picks", [])] else "AI23"

        orders.append(
            {
                "ticker": t,
                "qty": shares,
                "strategy_id": sid,
                "note": f"target_rebalance asof={asof}",
            }
        )

    # Also sell tickers that are held but not desired anymore (full exit)
    desired_set = set(desired_mv.keys())
    for t, q in positions.items():
        if t == "USD":
            continue
        if t not in desired_set and abs(q) > 1e-9:
            orders.append({"ticker": t, "qty": -float(round(q, 3)), "strategy_id": "", "note": "exit_not_in_targets"})

    return orders


def defaultdict_float():
    from collections import defaultdict

    return defaultdict(float)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=date.today().isoformat(), help="YYYY-MM-DD")
    ap.add_argument(
        "--mode",
        choices=["close", "fills"],
        default="close",
        help="close: after-close full run (fills if possible + mark close + maybe rebalance). fills: only try to record open fills for pending orders.",
    )
    args = ap.parse_args()

    asof = parse_date(args.asof)
    rules = load_rules()
    slip = float(rules["execution"].get("slippageBps", 10))

    msgs: list[str] = []

    # 1) Execute pending orders scheduled for today (fills at today's open)
    fill_msgs, filled, remaining = execute_pending_if_possible(asof, slippage_bps=slip)
    msgs += fill_msgs

    if args.mode == "fills":
        # In fills mode we do NOT mark close or generate new orders.
        print("\n".join(msgs) if msgs else "No pending fills due today.")
        return

    # 2) Mark-to-market (close). Note: Stooq daily bars typically appear after close.
    from subprocess import check_call

    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(Path.cwd() / "scripts" / "paper")
    check_call(["./scripts/paper/mark.py", "--date", asof.isoformat()], env=env)
    msgs.append(f"Marked NAV for {asof}.")

    # 3) If Friday, generate targets + pending orders for next trading day
    if is_friday(asof):
        targets = build_targets(asof, rules)
        orders = compute_rebalance_orders(asof, rules, targets)

        # schedule for next weekday (skip Sat/Sun)
        exec_date = asof + timedelta(days=1)
        while exec_date.weekday() >= 5:
            exec_date += timedelta(days=1)

        write_pending({"created_asof": asof.isoformat(), "exec_date": exec_date.isoformat(), "targets": targets, "orders": orders})
        msgs.append(f"Created {len(orders)} order(s) for execution at {exec_date} open (recorded after close when data available).")
    else:
        msgs.append("No rebalance today (weekly rebalance runs Fridays).")

    print("\n".join(msgs))


if __name__ == "__main__":
    main()
