#!/usr/bin/env python3
"""Backfill sleeve_nav.csv from ledger + nav_clean with one market-data fetch per ticker."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from market_data import get_bars

LEDGER = Path("paper/ledger.csv")
NAV_CLEAN = Path("paper/nav_clean.csv")
RULES = Path("paper/rules.json")
OUT = Path("paper/sleeve_nav.csv")


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def provider_from_rules(rules: dict) -> tuple[str, str | None]:
    md = rules.get("marketData", {})
    return md.get("provider", "tiingo"), md.get("fallbackProvider", "yahoo")


def main() -> None:
    ledger = load_csv(LEDGER)
    nav_rows = load_csv(NAV_CLEAN)
    rules = read_rules()
    provider, fallback = provider_from_rules(rules)

    dates = sorted([r["date"] for r in nav_rows])
    tickers = sorted({(r.get("ticker") or "").upper() for r in ledger if (r.get("action") or "").upper() in ("BUY", "SELL") and (r.get("ticker") or "").upper() != "USD"})

    price_map = {}
    if dates:
        max_date = datetime.strptime(dates[-1], "%Y-%m-%d").date()
        for t in tickers:
            bars, _ = get_bars(t, min_date=max_date, provider=provider, fallback_provider=fallback)
            px_by_date = {}
            last = None
            for b in bars:
                last = b.close
                px_by_date[b.d.isoformat()] = b.close
            # carry-forward accessor later
            price_map[t] = bars

    trades_by_date = defaultdict(list)
    for r in ledger:
        ts = r.get("timestamp_et") or ""
        if ts:
            trades_by_date[ts.split("T", 1)[0]].append(r)

    sleeve_qty = defaultdict(lambda: defaultdict(float))
    sleeve_cash = defaultdict(float)

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "sleeve", "cash", "market_value", "nav"])

        for d in dates:
            for r in trades_by_date.get(d, []):
                action = (r.get("action") or "").upper()
                ticker = (r.get("ticker") or "").upper()
                sid = (r.get("strategy_id") or "UNASSIGNED").strip() or "UNASSIGNED"

                if action == "CASH" and ticker == "USD":
                    sleeve_cash["CASH"] += float(r.get("qty") or 0)
                    continue
                if action == "DIVIDEND":
                    sleeve_cash["CASH"] += float(r.get("notional") or 0)
                    continue
                if action not in ("BUY", "SELL"):
                    continue

                q = float(r.get("qty") or 0)
                price = float(r.get("price") or 0)
                fees = float(r.get("fees") or 0)
                slip = abs(q * price) * (float(r.get("slippage_bps") or 0) / 10000.0)
                if action == "BUY":
                    sleeve_qty[sid][ticker] += q
                    sleeve_cash[sid] -= q * price + fees + slip
                else:
                    sleeve_qty[sid][ticker] -= q
                    sleeve_cash[sid] += q * price - fees - slip

            all_sleeves = sorted(set(sleeve_qty.keys()) | set(sleeve_cash.keys()))
            for sid in all_sleeves:
                cash = float(sleeve_cash.get(sid, 0.0))
                mv = 0.0
                for t, q in sleeve_qty.get(sid, {}).items():
                    if abs(q) <= 1e-9:
                        continue
                    last_px = None
                    for b in price_map.get(t, []):
                        if b.d.isoformat() <= d:
                            last_px = b.close
                        else:
                            break
                    if last_px is not None:
                        mv += q * last_px
                w.writerow([d, sid, f"{cash:.2f}", f"{mv:.2f}", f"{cash + mv:.2f}"])

    print("ok: true")
    print(f"dates: {len(dates)}")
    print(f"tickers: {len(tickers)}")


if __name__ == "__main__":
    main()
