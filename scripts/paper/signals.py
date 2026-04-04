#!/usr/bin/env python3
"""Signal helpers (price-only).

We deliberately keep this price-only so it can run daily with Stooq.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from stooq import fetch_daily_csv, load_bars


@dataclass
class Momentum:
    ticker: str
    lookback_days: int
    start: float
    end: float
    return_pct: float


def last_bar_on_or_before(ticker: str, d: date):
    try:
        p = fetch_daily_csv(ticker, min_date=d)
    except Exception:
        return None
    bars = load_bars(Path(p))
    last = None
    for b in bars:
        if b.d <= d:
            last = b
        else:
            break
    return last


def close_on_or_before(ticker: str, d: date):
    b = last_bar_on_or_before(ticker, d)
    return b.close if b else None


def momentum_close_to_close(ticker: str, asof: date, lookback_days: int = 252) -> Momentum | None:
    end = close_on_or_before(ticker, asof)
    if end is None:
        return None
    start_date = asof - timedelta(days=int(lookback_days * 1.6))

    # Find first bar >= start_date, then use its close as start.
    # Ensure cache is fresh up through `asof`.
    p = fetch_daily_csv(ticker, min_date=asof)
    bars = load_bars(Path(p))
    start = None
    for b in bars:
        if b.d >= start_date:
            start = b.close
            break
    if start is None or start == 0:
        return None

    ret = end / start - 1.0
    return Momentum(ticker=ticker, lookback_days=lookback_days, start=float(start), end=float(end), return_pct=float(ret))
