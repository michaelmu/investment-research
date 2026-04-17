#!/usr/bin/env python3
"""Backfill missing strategy_id values for SELL rows using prior BUY lineage.

This keeps attribution cleaner for historical trades where exits were recorded
without a sleeve tag.
"""

from __future__ import annotations

import csv
from pathlib import Path

LEDGER = Path("paper/ledger.csv")


def load_rows() -> list[dict]:
    with LEDGER.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(rows: list[dict], fieldnames: list[str]) -> None:
    with LEDGER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    rows = load_rows()
    if not rows:
        print("ok: true\nupdated: 0")
        return

    fieldnames = list(rows[0].keys())
    latest_sid_by_ticker: dict[str, str] = {}
    updated = 0

    for r in rows:
        action = (r.get("action") or "").upper()
        ticker = (r.get("ticker") or "").upper()
        sid = (r.get("strategy_id") or "").strip()
        if action == "BUY" and ticker and sid:
            latest_sid_by_ticker[ticker] = sid
        elif action == "SELL" and ticker and not sid:
            inferred = latest_sid_by_ticker.get(ticker, "")
            if inferred:
                r["strategy_id"] = inferred
                updated += 1

    save_rows(rows, fieldnames)
    print(f"ok: true\nupdated: {updated}")


if __name__ == "__main__":
    main()
