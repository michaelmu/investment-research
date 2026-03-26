#!/usr/bin/env python3
"""Minimal Stooq daily OHLC fetcher with caching.

This is intentionally lightweight and does not require pandas.

Data source: https://stooq.com/q/d/l/?s=SYMBOL.US&i=d
Note: unadjusted OHLC (splits/dividends not adjusted).
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests


@dataclass
class Bar:
    d: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def stooq_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    if t.endswith(".US"):
        return t.lower()
    return f"{t}.US".lower()


def fetch_daily_csv(ticker: str, cache_dir: Path = Path("paper/cache/prices"), force: bool = False, sleep_s: float = 0.1) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{ticker.upper()}.csv"
    if out.exists() and not force:
        return out
    time.sleep(sleep_s)
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol(ticker)}&i=d"
    r = requests.get(url, headers={"User-Agent": "OpenClaw"}, timeout=30)
    r.raise_for_status()
    if "Date,Open,High,Low,Close,Volume" not in r.text:
        raise RuntimeError(f"Unexpected Stooq response for {ticker}: {url}")
    out.write_text(r.text, encoding="utf-8")
    return out


def load_bars(csv_path: Path) -> list[Bar]:
    rows: list[Bar] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            d = datetime.strptime(r["Date"], "%Y-%m-%d").date()
            rows.append(
                Bar(
                    d=d,
                    open=float(r["Open"]),
                    high=float(r["High"]),
                    low=float(r["Low"]),
                    close=float(r["Close"]),
                    volume=int(float(r.get("Volume") or 0)),
                )
            )
    rows.sort(key=lambda b: b.d)
    return rows


def last_close_on_or_before(ticker: str, d: date) -> Optional[float]:
    p = fetch_daily_csv(ticker)
    bars = load_bars(p)
    last = None
    for b in bars:
        if b.d <= d:
            last = b.close
        else:
            break
    return last
