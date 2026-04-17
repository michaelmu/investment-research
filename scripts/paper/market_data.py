#!/usr/bin/env python3
"""Market data provider interface for the paper bot.

Current providers:
- yahoo: default, daily OHLCV via yfinance (repo-local .venv)
- stooq: legacy CSV endpoint (may block automated access)
- tiingo: daily EOD bars via API key

The rest of the bot should import this module instead of talking directly to a
specific provider. That keeps it easy to swap in Tiingo/Polygon later.
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests

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
    provider: str = "unknown"


DEFAULT_CACHE_DIR = Path("paper/cache/prices")
DEFAULT_PROVIDER = "yahoo"
FALLBACK_PROVIDER = "stooq"
TIINGO_KEY_FILE = Path("paper/tiingo_api_key.txt")


def _cache_path(ticker: str, provider: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{provider.lower()}-{ticker.upper()}.csv"


def _cached_last_date(path: Path) -> Optional[date]:
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) < 2:
            return None
        last = lines[-1].split(",", 1)[0]
        return datetime.strptime(last, "%Y-%m-%d").date()
    except Exception:
        return None


def load_bars(csv_path: Path, provider: str = "unknown") -> list[Bar]:
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
                    provider=provider,
                )
            )
    rows.sort(key=lambda b: b.d)
    return rows


def _write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _fetch_yahoo_csv(ticker: str, out: Path) -> Path:
    if yf is None:
        raise RuntimeError("yfinance unavailable")
    sym = ticker.upper()
    df = yf.download(sym, period="max", interval="1d", auto_adjust=False, progress=False)
    if df is None or len(df) == 0:
        raise RuntimeError(f"No Yahoo data for {ticker}")

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
    return _write_csv(out, lines)


def _stooq_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    return t.lower() if t.endswith(".US") else f"{t}.US".lower()


def _fetch_stooq_csv(ticker: str, out: Path) -> Path:
    url = f"https://stooq.com/q/d/l/?s={_stooq_symbol(ticker)}&i=d"
    r = requests.get(url, headers={"User-Agent": "OpenClaw"}, timeout=30)
    r.raise_for_status()
    if "Date,Open,High,Low,Close,Volume" not in r.text:
        raise RuntimeError(f"Unexpected Stooq response for {ticker}: {url}")
    out.write_text(r.text, encoding="utf-8")
    return out


def _tiingo_key() -> str:
    key = (os.environ.get("TIINGO_API_KEY") or "").strip()
    if key:
        return key
    if TIINGO_KEY_FILE.exists():
        return TIINGO_KEY_FILE.read_text(encoding="utf-8").strip()
    raise RuntimeError("Tiingo API key not found. Set TIINGO_API_KEY or create paper/tiingo_api_key.txt")


def _fetch_tiingo_csv(ticker: str, out: Path) -> Path:
    key = _tiingo_key()
    url = f"https://api.tiingo.com/tiingo/daily/{ticker.upper()}/prices"
    params = {"startDate": "1900-01-01", "resampleFreq": "daily", "token": key}
    r = requests.get(url, params=params, headers={"Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"No Tiingo data for {ticker}")
    lines = ["Date,Open,High,Low,Close,Volume"]
    for row in data:
        d = str(row.get("date", "")).split("T", 1)[0]
        if not d:
            continue
        o = float(row.get("open") or 0.0)
        h = float(row.get("high") or 0.0)
        l = float(row.get("low") or 0.0)
        c = float(row.get("close") or 0.0)
        v = int(float(row.get("volume") or 0))
        lines.append(f"{d},{o:.4f},{h:.4f},{l:.4f},{c:.4f},{v}")
    return _write_csv(out, lines)


def fetch_daily_csv(
    ticker: str,
    provider: str = DEFAULT_PROVIDER,
    fallback_provider: Optional[str] = FALLBACK_PROVIDER,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
    min_date: Optional[date] = None,
) -> tuple[Path, str]:
    provider = (provider or DEFAULT_PROVIDER).lower()
    out = _cache_path(ticker, provider, cache_dir)

    if out.exists() and not force:
        if min_date is None:
            return out, provider
        last_d = _cached_last_date(out)
        if last_d is not None and last_d >= min_date:
            return out, provider

    try:
        if provider == "yahoo":
            return _fetch_yahoo_csv(ticker, out), provider
        if provider == "stooq":
            return _fetch_stooq_csv(ticker, out), provider
        if provider == "tiingo":
            return _fetch_tiingo_csv(ticker, out), provider
        raise RuntimeError(f"Unsupported provider: {provider}")
    except Exception:
        if fallback_provider and fallback_provider.lower() != provider:
            fb = fallback_provider.lower()
            fb_out = _cache_path(ticker, fb, cache_dir)
            try:
                if fb == "yahoo":
                    return _fetch_yahoo_csv(ticker, fb_out), fb
                if fb == "stooq":
                    return _fetch_stooq_csv(ticker, fb_out), fb
                if fb == "tiingo":
                    return _fetch_tiingo_csv(ticker, fb_out), fb
            except Exception:
                pass

        if out.exists() and out.stat().st_size > 0:
            return out, provider
        raise


def get_bars(ticker: str, min_date: Optional[date] = None, provider: str = DEFAULT_PROVIDER, fallback_provider: Optional[str] = FALLBACK_PROVIDER) -> tuple[list[Bar], str]:
    path, used = fetch_daily_csv(ticker, provider=provider, fallback_provider=fallback_provider, min_date=min_date)
    return load_bars(path, provider=used), used


def last_bar_on_or_before(ticker: str, d: date, provider: str = DEFAULT_PROVIDER, fallback_provider: Optional[str] = FALLBACK_PROVIDER) -> Optional[Bar]:
    try:
        bars, used = get_bars(ticker, min_date=d, provider=provider, fallback_provider=fallback_provider)
    except Exception:
        return None
    last = None
    for b in bars:
        if b.d <= d:
            b.provider = used
            last = b
        else:
            break
    return last


def last_close_on_or_before(ticker: str, d: date, provider: str = DEFAULT_PROVIDER, fallback_provider: Optional[str] = FALLBACK_PROVIDER) -> Optional[float]:
    b = last_bar_on_or_before(ticker, d, provider=provider, fallback_provider=fallback_provider)
    return b.close if b else None
