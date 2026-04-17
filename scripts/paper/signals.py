#!/usr/bin/env python3
"""Signal helpers (price-only).

We deliberately keep this price-only so it can run daily with the configured
market data provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from market_data import get_bars


@dataclass
class Momentum:
    ticker: str
    lookback_days: int
    start: float
    end: float
    return_pct: float


@dataclass
class SignalSnapshot:
    ticker: str
    close: float
    sma_200: float | None
    mom_1m: float | None
    mom_3m: float | None
    mom_6m: float | None
    mom_12m: float | None
    trend_ok: bool
    composite: float | None


def _bars_on_or_before(ticker: str, d: date):
    bars, _ = get_bars(ticker, min_date=d)
    return [b for b in bars if b.d <= d]


def last_bar_on_or_before(ticker: str, d: date):
    try:
        bars = _bars_on_or_before(ticker, d)
    except Exception:
        return None
    return bars[-1] if bars else None


def close_on_or_before(ticker: str, d: date):
    b = last_bar_on_or_before(ticker, d)
    return b.close if b else None


def momentum_close_to_close(ticker: str, asof: date, lookback_days: int = 252) -> Momentum | None:
    end = close_on_or_before(ticker, asof)
    if end is None:
        return None
    start_date = asof - timedelta(days=int(lookback_days * 1.6))

    # Find first bar >= start_date, then use its close as start.
    bars, _ = get_bars(ticker, min_date=asof)
    start = None
    for b in bars:
        if b.d >= start_date:
            start = b.close
            break
    if start is None or start == 0:
        return None

    ret = end / start - 1.0
    return Momentum(ticker=ticker, lookback_days=lookback_days, start=float(start), end=float(end), return_pct=float(ret))


def sma_on_or_before(ticker: str, asof: date, window: int = 200) -> float | None:
    bars, _ = get_bars(ticker, min_date=asof)
    closes = [b.close for b in bars if b.d <= asof]
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def signal_snapshot(ticker: str, asof: date) -> SignalSnapshot | None:
    try:
        bars = _bars_on_or_before(ticker, asof)
    except Exception:
        return None
    if not bars:
        return None

    close = bars[-1].close
    closes = [b.close for b in bars]

    def mom(window: int) -> float | None:
        if len(closes) < window + 1:
            return None
        start = closes[-(window + 1)]
        end = closes[-1]
        return (end / start - 1.0) if start else None

    sma_200 = (sum(closes[-200:]) / 200.0) if len(closes) >= 200 else None
    vals = [mom(21), mom(63), mom(126), mom(252)]
    comp_parts = [v for v in vals if v is not None]
    composite = None
    if comp_parts:
        w = []
        for v, wt in zip(vals, [0.1, 0.2, 0.3, 0.4]):
            if v is not None:
                w.append((v, wt))
        if w:
            composite = sum(v * wt for v, wt in w) / sum(wt for _, wt in w)
    trend_ok = bool(sma_200 is not None and close >= sma_200)
    return SignalSnapshot(
        ticker=ticker,
        close=float(close),
        sma_200=float(sma_200) if sma_200 is not None else None,
        mom_1m=vals[0],
        mom_3m=vals[1],
        mom_6m=vals[2],
        mom_12m=vals[3],
        trend_ok=trend_ok,
        composite=composite,
    )
