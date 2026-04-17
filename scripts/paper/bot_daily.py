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

from market_data import get_bars, last_bar_on_or_before as md_last_bar_on_or_before
from signals import signal_snapshot

ROOT = Path(".")
PAPER = Path("paper")
RULES = PAPER / "rules.json"
LEDGER = PAPER / "ledger.csv"
PENDING = PAPER / "orders_pending.json"


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def is_friday(d: date) -> bool:
    return d.weekday() == 4


def last_bar_on_or_before(ticker: str, d: date, provider: str = "yahoo", fallback_provider: str | None = "stooq"):
    return md_last_bar_on_or_before(ticker, d, provider=provider, fallback_provider=fallback_provider)


def close_on(ticker: str, d: date, provider: str = "yahoo", fallback_provider: str | None = "stooq"):
    b = last_bar_on_or_before(ticker, d, provider=provider, fallback_provider=fallback_provider)
    if b and b.d == d:
        return b.close
    return None


def last_bar_between(ticker: str, start_d: date, end_d: date, provider: str = "yahoo", fallback_provider: str | None = "stooq"):
    try:
        bars, _ = get_bars(ticker, min_date=end_d, provider=provider, fallback_provider=fallback_provider)
    except Exception:
        return None
    last = None
    for b in bars:
        if start_d <= b.d <= end_d:
            last = b
        elif b.d > end_d:
            break
    return last


def load_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def provider_from_rules(rules: dict) -> tuple[str, str | None]:
    md = rules.get("marketData", {})
    return md.get("provider", "yahoo"), md.get("fallbackProvider", "stooq")


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    with LEDGER.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_positions_and_cash(rows: list[dict]) -> tuple[dict[str, float], float]:
    from mark import compute_positions  # reuse logic

    return compute_positions(rows)


def portfolio_value(positions: dict[str, float], cash: float, d: date, provider: str, fallback_provider: str | None) -> float:
    nav = cash
    for t, q in positions.items():
        b = last_bar_on_or_before(t, d, provider=provider, fallback_provider=fallback_provider)
        if b:
            nav += b.close * q
    return float(nav)


def write_pending(obj: dict) -> None:
    PENDING.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def load_pending() -> dict | None:
    if not PENDING.exists():
        return None
    try:
        return json.loads(PENDING.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        # Preserve the bad file for inspection, but get it out of the way so the bot can run.
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bad = PAPER / f"orders_pending.badjson.{ts}.json"
        bad.write_text(PENDING.read_text(encoding="utf-8"), encoding="utf-8")
        raise RuntimeError(f"orders_pending.json is invalid JSON; copied to {bad}: {e}")


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


def execute_pending_if_possible(asof: date, slippage_bps: float, provider: str, fallback_provider: str | None, max_stale_lag_days: int | None = None) -> tuple[list[str], int, int]:
    """Try to execute pending orders scheduled for `asof` at that day's close.

    Returns: (msgs, filled_count, remaining_count)

    IMPORTANT: if price data is missing for any order, we keep the order pending.
    Past-due orders are retried on later dates until they fill.
    """
    msgs: list[str] = []
    pending = load_pending()
    if not pending:
        return msgs, 0, 0

    exec_date = parse_date(pending["exec_date"])
    if exec_date > asof:
        return msgs, 0, 0
    if exec_date < asof:
        age = (asof - exec_date).days
        msgs.append(f"ALERT: pending orders are past due by {age} day(s) (exec_date={exec_date}); retrying at {asof} close.")

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

        bar = last_bar_between(ticker, exec_date, asof, provider=provider, fallback_provider=fallback_provider)
        stale_fill = False
        if bar is None:
            bar = last_bar_on_or_before(ticker, asof, provider=provider, fallback_provider=fallback_provider)
            if bar is None:
                msgs.append(f"WARN: no close price for {ticker} on or before {asof}; keeping pending")
                remaining.append(o)
                continue
            stale_fill = True

        fill_date = bar.d
        lag_days = (asof - fill_date).days
        if max_stale_lag_days is not None and stale_fill and lag_days > max_stale_lag_days:
            msgs.append(f"ALERT: stale fill for {ticker} rejected; lag {lag_days}d exceeds maxStaleLagDays={max_stale_lag_days}. Keeping pending.")
            remaining.append(o)
            continue

        px = bar.close
        fill_date = bar.d
        fill_source = getattr(bar, "provider", provider) or provider
        fill_quality = "exact"
        if stale_fill:
            fill_quality = "stale_fallback"
            msgs.append(f"ALERT: stale fill for {ticker}: using last available close before exec window ({fill_date} @ {px:.4f})")
        elif fill_date < asof:
            fill_quality = "latest_available"
            msgs.append(f"INFO: using latest available close for {ticker}: {fill_date} @ {px:.4f}")

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
                "fill_source": fill_source,
                "fill_quality": fill_quality,
                "price_date_used": str(fill_date),
                "note": f"{o.get('note', '')}; fill_date={fill_date}; stale_fill={stale_fill}",
                "source_doc": "",
            }
        )
        filled += 1

    if remaining:
        pending["orders"] = remaining
        # keep same exec_date; retry later when close prints
        write_pending(pending)
        msgs.append(f"Executed {filled} order(s); {len(remaining)} still pending.")
    else:
        PENDING.unlink(missing_ok=True)
        msgs.append(f"Executed {filled} pending order(s) for {asof} (filled at close).")

    return msgs, filled, len(remaining)


def build_targets(asof: date, rules: dict) -> dict:
    engine = rules.get("strategyEngine", {})
    sleeves_cfg = engine.get("sleeves", {})
    top_n = int(engine.get("selection", {}).get("topNPerSleeve", 2))
    use_trend = bool(engine.get("selection", {}).get("useTrendFilter", True))
    abs_gate = bool(engine.get("selection", {}).get("absoluteMomentumGate", True))

    targets: dict[str, dict] = {}

    for sid, cfg in sleeves_cfg.items():
        tickers = cfg.get("universe", [])
        risk_off = cfg.get("riskOff", [])
        snaps = []
        for t in tickers:
            s = signal_snapshot(t, asof)
            if s and s.composite is not None:
                snaps.append(s)

        ranked = sorted(snaps, key=lambda x: x.composite if x.composite is not None else -999, reverse=True)
        eligible = []
        for s in ranked:
            if use_trend and not s.trend_ok:
                continue
            if abs_gate and (s.composite is None or s.composite <= 0):
                continue
            eligible.append(s)

        picks = eligible[:top_n]
        if not picks:
            ro_snaps = [signal_snapshot(t, asof) for t in risk_off]
            ro_snaps = [s for s in ro_snaps if s and s.composite is not None]
            ro_snaps.sort(key=lambda x: x.composite if x.composite is not None else -999, reverse=True)
            if ro_snaps:
                p = ro_snaps[0]
                targets[sid] = {
                    "cash": 0.0,
                    "picks": [{"ticker": p.ticker, "weight": 1.0, "score": p.composite, "trend_ok": p.trend_ok}],
                }
            else:
                targets[sid] = {"cash": 1.0, "picks": []}
            continue

        w_each = 1.0 / len(picks)
        targets[sid] = {
            "cash": 0.0,
            "picks": [
                {
                    "ticker": p.ticker,
                    "weight": w_each,
                    "score": p.composite,
                    "trend_ok": p.trend_ok,
                    "mom_12m": p.mom_12m,
                }
                for p in picks
            ],
        }

    out = {"asof": asof.isoformat(), "sleeves": {}}
    for sid, t in targets.items():
        out["sleeves"][sid] = {
            "sleeve_weight": float(sleeves_cfg.get(sid, {}).get("weight", 0.5)),
            "targets": t,
        }
    return out


def compute_rebalance_orders(asof: date, rules: dict, targets: dict) -> list[dict]:
    provider, fallback_provider = provider_from_rules(rules)
    rows = read_ledger()
    positions, cash = compute_positions_and_cash(rows)
    nav = portfolio_value(positions, cash, asof, provider, fallback_provider)

    # Current market values by ticker
    mv = {}
    for t, q in positions.items():
        b = last_bar_on_or_before(t, asof, provider=provider, fallback_provider=fallback_provider)
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
        b = last_bar_on_or_before(t, asof, provider=provider, fallback_provider=fallback_provider)
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
        help="close: after-close full run (fills if possible + mark close + maybe rebalance). fills: only try to record close fills for pending orders.",
    )
    args = ap.parse_args()

    asof = parse_date(args.asof)
    rules = load_rules()
    slip = float(rules["execution"].get("slippageBps", 10))
    max_stale_lag_days = rules.get("execution", {}).get("maxStaleLagDays")
    provider, fallback_provider = provider_from_rules(rules)

    msgs: list[str] = []

    # 1) Execute pending orders scheduled for today (fills at today's close)
    fill_msgs, filled, remaining = execute_pending_if_possible(asof, slippage_bps=slip, provider=provider, fallback_provider=fallback_provider, max_stale_lag_days=max_stale_lag_days)
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
        msgs.append(f"Created {len(orders)} order(s) for execution at {exec_date} close.")
    else:
        msgs.append("No rebalance today (weekly rebalance runs Fridays).")

    print("\n".join(msgs))


if __name__ == "__main__":
    main()
