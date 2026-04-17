#!/usr/bin/env python3
"""Provider health check for the paper bot.

Checks whether the configured provider is returning reasonably fresh bars for a
small representative set of symbols before the bot trades.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from market_data import last_bar_on_or_before

RULES = Path("paper/rules.json")


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def read_rules() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=date.today().isoformat(), help="YYYY-MM-DD")
    ap.add_argument("--max-lag-days", type=int, default=2)
    ap.add_argument("--symbols", nargs="*", default=["SPY", "QQQ", "IWM", "XLE"])
    args = ap.parse_args()

    asof = parse_date(args.asof)
    rules = read_rules()
    md = rules.get("marketData", {})
    provider = md.get("provider", "yahoo")
    fallback = md.get("fallbackProvider", "stooq")

    ok = True
    lines: list[str] = []
    worst_lag = 0

    for sym in args.symbols:
        bar = last_bar_on_or_before(sym, asof, provider=provider, fallback_provider=fallback)
        if not bar:
            ok = False
            lines.append(f"ALERT: {sym} has no bar on or before {asof} (provider={provider}, fallback={fallback})")
            continue
        lag = (asof - bar.d).days
        worst_lag = max(worst_lag, lag)
        status = "OK" if lag <= args.max_lag_days else "ALERT"
        if lag > args.max_lag_days:
            ok = False
        lines.append(f"{status}: {sym} bar_date={bar.d} close={bar.close:.2f} provider={bar.provider} lag_days={lag}")

    print(f"provider: {provider}")
    print(f"fallback: {fallback}")
    print(f"asof: {asof}")
    print(f"worst_lag_days: {worst_lag}")
    print(f"health_ok: {str(ok).lower()}")
    print("checks:")
    for line in lines:
        print(line)

    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
