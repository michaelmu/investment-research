#!/usr/bin/env python3
"""Minimal Stooq daily OHLC fetcher with caching.

This is intentionally lightweight and does not require pandas.

Data source: https://stooq.com/q/d/l/?s=SYMBOL.US&i=d
Note: unadjusted OHLC (splits/dividends not adjusted).
"""

from __future__ import annotations

import csv
import time
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests

# Optional Yahoo fallback (installed in repo venv)
try:
    import yfinance as yf  # type: ignore
except Exception:  # pragma: no cover
    yf = None


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


def _cached_last_date(path: Path) -> Optional[date]:
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) < 2:
            return None
        last = lines[-1].split(",", 1)[0]
        return datetime.strptime(last, "%Y-%m-%d").date()
    except Exception:
        return None


def fetch_daily_csv(
    ticker: str,
    cache_dir: Path = Path("paper/cache/prices"),
    force: bool = False,
    min_date: Optional[date] = None,
    sleep_s: float = 0.1,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{ticker.upper()}.csv"

    if out.exists() and not force:
        if min_date is None:
            return out
        last_d = _cached_last_date(out)
        if last_d is not None and last_d >= min_date:
            return out
        # else: stale cache, refetch

    time.sleep(sleep_s)
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol(ticker)}&i=d"
    r = requests.get(url, headers={"User-Agent": "OpenClaw"}, timeout=30)
    r.raise_for_status()

    if "Date,Open,High,Low,Close,Volume" not in r.text:
        blocked = "want to use our data" in r.text.lower() or r.text.strip().lower().startswith("write to")

        # Fallback: Yahoo Finance via yfinance (if available).
        if blocked and yf is not None:
            sym = ticker.upper()
            df = yf.download(sym, period="max", interval="1d", auto_adjust=False, progress=False)
            if df is not None and len(df) > 0:
                # yfinance sometimes returns a MultiIndex columns like ("Open", "SPY")
                multi = hasattr(df.columns, "levels") and len(getattr(df.columns, "levels", [])) == 2

                def get(row, field: str) -> float:
                    try:
                        if multi:
                            val = row[(field, sym)]
                        else:
                            val = row[field]
                        f = float(val)
                        return 0.0 if math.isnan(f) else f
                    except Exception:
                        return 0.0

                # Normalize to Stooq-like CSV header
                lines = ["Date,Open,High,Low,Close,Volume"]
                for idx, row in df.iterrows():
                    d = idx.date().isoformat()
                    o = get(row, "Open")
                    h = get(row, "High")
                    l = get(row, "Low")
                    c = get(row, "Close")
                    try:
                        v = row[("Volume", sym)] if multi else row.get("Volume", 0)
                        v = int(float(v) if v is not None else 0)
                    except Exception:
                        v = 0
                    lines.append(f"{d},{o:.4f},{h:.4f},{l:.4f},{c:.4f},{v}")
                out.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return out

        # If we have *any* cached data, fall back to it rather than crashing.
        if out.exists() and out.stat().st_size > 0:
            return out
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
    try:
        p = fetch_daily_csv(ticker, min_date=d)
        bars = load_bars(p)
    except Exception:
        return None
    last = None
    for b in bars:
        if b.d <= d:
            last = b.close
        else:
            break
    return last
