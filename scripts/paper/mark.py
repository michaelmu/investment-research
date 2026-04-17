#!/usr/bin/env python3
"""Mark paper portfolio to market: compute positions + NAV vs benchmark.

Inputs:
- paper/ledger.csv
- paper/rules.json

Outputs (overwritten each run):
- paper/positions.csv
- paper/cash.csv (append)
- paper/nav.csv (append)

Prices: configured market data provider daily close.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from market_data import last_close_on_or_before

LEDGER = Path("paper/ledger.csv")
RULES = Path("paper/rules.json")

OUT_POS = Path("paper/positions.csv")
OUT_CASH = Path("paper/cash.csv")
OUT_NAV = Path("paper/nav.csv")
OUT_SLEEVE_NAV = Path("paper/sleeve_nav.csv")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def ensure_csv(path: Path, header: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)


def read_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def provider_from_rules(rules: dict) -> tuple[str, str | None]:
    md = rules.get("marketData", {})
    return md.get("provider", "yahoo"), md.get("fallbackProvider", "stooq")


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        raise SystemExit("paper/ledger.csv not found; run ledger.py init")
    with LEDGER.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_positions(rows: list[dict]) -> tuple[dict[str, float], float]:
    qty = defaultdict(float)
    cash = 0.0

    for r in rows:
        action = (r.get("action") or "").upper()
        ticker = (r.get("ticker") or "").upper()

        if action == "CASH" and ticker == "USD":
            cash += float(r.get("qty") or 0)
            continue

        if action == "DIVIDEND":
            cash += float(r.get("notional") or 0)
            continue

        if action in ("BUY", "SELL"):
            q = float(r.get("qty") or 0)
            price = float(r.get("price") or 0)
            fees = float(r.get("fees") or 0)
            slippage_bps = float(r.get("slippage_bps") or 0)
            notional = q * price
            slip = abs(notional) * (slippage_bps / 10000.0)

            if action == "BUY":
                qty[ticker] += q
                cash -= notional
                cash -= fees
                cash -= slip
            else:
                qty[ticker] -= q
                cash += notional
                cash -= fees
                cash -= slip
            continue

        if action == "SPLIT":
            # ratio in qty field: A:B
            ratio = (r.get("qty") or "").strip()
            if ":" in ratio and ticker:
                a, b = ratio.split(":", 1)
                a, b = float(a), float(b)
                if b != 0:
                    qty[ticker] *= (a / b)
            continue

    # remove near-zero
    qty2 = {t: q for t, q in qty.items() if abs(q) > 1e-9}
    return qty2, cash


def compute_sleeve_state(rows: list[dict]) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    sleeve_qty: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    sleeve_cash: dict[str, float] = defaultdict(float)

    for r in rows:
        action = (r.get("action") or "").upper()
        ticker = (r.get("ticker") or "").upper()
        sid = (r.get("strategy_id") or "UNASSIGNED").strip() or "UNASSIGNED"

        if action == "CASH" and ticker == "USD":
            sleeve_cash["CASH"] += float(r.get("qty") or 0)
            continue

        if action == "DIVIDEND":
            sleeve_cash["CASH"] += float(r.get("notional") or 0)
            continue

        if action in ("BUY", "SELL"):
            q = float(r.get("qty") or 0)
            price = float(r.get("price") or 0)
            fees = float(r.get("fees") or 0)
            slippage_bps = float(r.get("slippage_bps") or 0)
            notional = q * price
            slip = abs(notional) * (slippage_bps / 10000.0)

            if action == "BUY":
                sleeve_qty[sid][ticker] += q
                sleeve_cash[sid] -= notional + fees + slip
            else:
                sleeve_qty[sid][ticker] -= q
                sleeve_cash[sid] += notional - fees - slip
            continue

    clean_qty = {sid: {t: q for t, q in tq.items() if abs(q) > 1e-9} for sid, tq in sleeve_qty.items()}
    return clean_qty, dict(sleeve_cash)


def write_positions(d: date, positions: dict[str, float], provider: str, fallback_provider: str | None) -> None:
    with OUT_POS.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["asof", "ticker", "qty", "close", "market_value"])
        for t, q in sorted(positions.items()):
            px = last_close_on_or_before(t, d, provider=provider, fallback_provider=fallback_provider)
            mv = (px or 0.0) * q
            w.writerow([d.isoformat(), t, f"{q:.6f}", f"{px:.4f}" if px else "", f"{mv:.2f}"])


def append_cash(d: date, cash: float) -> None:
    ensure_csv(OUT_CASH, ["date", "cash"])
    with OUT_CASH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([d.isoformat(), f"{cash:.2f}"])


def append_nav(d: date, nav: float, bench: float, bench_ticker: str) -> None:
    ensure_csv(OUT_NAV, ["date", "nav", "benchmark_ticker", "benchmark_close", "nav_rel_benchmark"])
    rel = nav / bench if bench else ""
    with OUT_NAV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([d.isoformat(), f"{nav:.2f}", bench_ticker, f"{bench:.4f}" if bench else "", f"{rel:.6f}" if rel else ""])


def append_sleeve_nav(d: date, rows: list[dict], provider: str, fallback_provider: str | None) -> None:
    sleeve_qty, sleeve_cash = compute_sleeve_state(rows)
    # Add unassigned positions to CASH sleeve cash if missing.
    fieldnames = ["date", "sleeve", "cash", "market_value", "nav"]
    ensure_csv(OUT_SLEEVE_NAV, fieldnames)
    with OUT_SLEEVE_NAV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # write CASH sleeve first if present
        all_sleeves = sorted(set(sleeve_qty.keys()) | set(sleeve_cash.keys()))
        for sid in all_sleeves:
            cash = float(sleeve_cash.get(sid, 0.0))
            mv = 0.0
            for t, q in sleeve_qty.get(sid, {}).items():
                px = last_close_on_or_before(t, d, provider=provider, fallback_provider=fallback_provider)
                if px is None:
                    continue
                mv += px * q
            nav = cash + mv
            w.writerow([d.isoformat(), sid, f"{cash:.2f}", f"{mv:.2f}", f"{nav:.2f}"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat(), help="mark date YYYY-MM-DD")
    args = ap.parse_args()

    d = parse_date(args.date)
    rules = read_rules()
    bench = rules.get("benchmark", "SPY")
    provider, fallback_provider = provider_from_rules(rules)

    rows = read_ledger()
    positions, cash = compute_positions(rows)

    write_positions(d, positions, provider, fallback_provider)
    append_cash(d, cash)
    append_sleeve_nav(d, rows, provider, fallback_provider)

    nav = cash
    for t, q in positions.items():
        px = last_close_on_or_before(t, d, provider=provider, fallback_provider=fallback_provider)
        if px is None:
            continue
        nav += px * q

    bpx = last_close_on_or_before(bench, d, provider=provider, fallback_provider=fallback_provider)
    append_nav(d, nav, bpx or 0.0, bench)

    print("ok: true")
    print(f"date: {d.isoformat()}")
    print(f"nav: {nav:.2f}")
    print(f"cash: {cash:.2f}")


if __name__ == "__main__":
    main()
