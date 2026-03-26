#!/usr/bin/env python3
"""Append-only paper trading ledger.

Commands:
- init: create ledger with starting cash
- add-trade: record BUY/SELL
- add-dividend: record DIVIDEND cash
- add-split: record SPLIT share ratio

All events are appended to paper/ledger.csv.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

LEDGER = Path("paper/ledger.csv")

FIELDS = [
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
]


def now_et_iso() -> str:
    # store as ISO string; timezone label in field name (ET)
    return datetime.now().isoformat(timespec="seconds")


def ensure_header(path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()


def append_rows(rows: Iterable[dict]) -> None:
    ensure_header(LEDGER)
    with LEDGER.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        for r in rows:
            w.writerow(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--cash", type=float, required=True)
    p_init.add_argument("--note", default="starting cash")

    p_trade = sub.add_parser("add-trade")
    p_trade.add_argument("--action", choices=["BUY", "SELL"], required=True)
    p_trade.add_argument("--ticker", required=True)
    p_trade.add_argument("--qty", type=float, required=True)
    p_trade.add_argument("--price", type=float, required=True)
    p_trade.add_argument("--fees", type=float, default=0.0)
    p_trade.add_argument("--slippage-bps", type=float, default=10.0)
    p_trade.add_argument("--strategy-id", default="")
    p_trade.add_argument("--reason", dest="reason_code", default="")
    p_trade.add_argument("--note", default="")
    p_trade.add_argument("--source", dest="source_doc", default="")

    p_div = sub.add_parser("add-dividend")
    p_div.add_argument("--ticker", required=True)
    p_div.add_argument("--amount", type=float, required=True, help="cash amount")
    p_div.add_argument("--note", default="")

    p_split = sub.add_parser("add-split")
    p_split.add_argument("--ticker", required=True)
    p_split.add_argument("--ratio", required=True, help="e.g. 2:1 or 3:2")
    p_split.add_argument("--note", default="")

    args = ap.parse_args()

    ts = now_et_iso()

    if args.cmd == "init":
        append_rows(
            [
                {
                    "timestamp_et": ts,
                    "action": "CASH",
                    "ticker": "USD",
                    "qty": args.cash,
                    "price": "",
                    "fees": 0,
                    "slippage_bps": "",
                    "notional": args.cash,
                    "strategy_id": "",
                    "reason_code": "init",
                    "note": args.note,
                    "source_doc": "",
                }
            ]
        )
        print("ok: true")
        return

    if args.cmd == "add-trade":
        notional = float(args.qty) * float(args.price)
        append_rows(
            [
                {
                    "timestamp_et": ts,
                    "action": args.action,
                    "ticker": args.ticker.upper(),
                    "qty": args.qty,
                    "price": args.price,
                    "fees": args.fees,
                    "slippage_bps": args.slippage_bps,
                    "notional": notional,
                    "strategy_id": args.strategy_id,
                    "reason_code": args.reason_code,
                    "note": args.note,
                    "source_doc": args.source_doc,
                }
            ]
        )
        print("ok: true")
        return

    if args.cmd == "add-dividend":
        append_rows(
            [
                {
                    "timestamp_et": ts,
                    "action": "DIVIDEND",
                    "ticker": args.ticker.upper(),
                    "qty": "",
                    "price": "",
                    "fees": 0,
                    "slippage_bps": "",
                    "notional": args.amount,
                    "strategy_id": "",
                    "reason_code": "dividend",
                    "note": args.note,
                    "source_doc": "",
                }
            ]
        )
        print("ok: true")
        return

    if args.cmd == "add-split":
        append_rows(
            [
                {
                    "timestamp_et": ts,
                    "action": "SPLIT",
                    "ticker": args.ticker.upper(),
                    "qty": args.ratio,
                    "price": "",
                    "fees": 0,
                    "slippage_bps": "",
                    "notional": "",
                    "strategy_id": "",
                    "reason_code": "split",
                    "note": args.note,
                    "source_doc": "",
                }
            ]
        )
        print("ok: true")
        return


if __name__ == "__main__":
    main()
