import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "historical"
TIMEOUT_SECONDS = float(os.getenv("MARKET_DATA_TIMEOUT_SECONDS", "15"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FRED_SYMBOLS = {"^GSPC": "SP500", "^NDX": "NASDAQ100", "^VIX": "VIXCLS"}


class HistoricalDataError(RuntimeError):
    pass


def _key(name: str) -> str:
    return re.sub(r"[^A-Z0-9_.=^-]+", "_", name.upper())


def _path(provider: str, symbol: str, period: str, interval: str) -> Path:
    return CACHE_DIR / f"{provider}_{_key(symbol)}_{period}_{interval}.json"


def _fresh(path: Path, age: timedelta) -> bool:
    return path.exists() and datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) < age


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write(path: Path, payload) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def _request(url: str, params: dict, path: Path, age: timedelta):
    if _fresh(path, age):
        cached = _read(path)
        if cached is not None:
            return cached
    stale = _read(path) if path.exists() else None
    try:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "StocksAnalyser2025/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        _write(path, payload)
        return payload
    except Exception:
        if stale is not None:
            return stale
        raise


def _cache_age(period: str, interval: str) -> timedelta:
    if interval.endswith("m") or interval == "1h":
        return timedelta(minutes=15)
    if period in {"1d", "5d"}:
        return timedelta(hours=1)
    return timedelta(hours=int(os.getenv("HISTORICAL_CACHE_HOURS", "24")))


def _period_days(period: str) -> int:
    return {"1d": 1, "5d": 5, "1mo": 31, "3mo": 93, "6mo": 186, "1y": 366, "2y": 732, "5y": 1830, "10y": 3660}.get(period, 186)


def _twelve_interval(interval: str) -> str:
    mapping = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "60m": "1h", "1h": "1h", "1d": "1day", "1wk": "1week", "1mo": "1month"}
    if interval not in mapping:
        raise ValueError(f"Unsupported Twelve Data interval: {interval}")
    return mapping[interval]


def _output_size(period: str, interval: str) -> int:
    days = _period_days(period)
    if interval == "1m":
        return min(5000, days * 390)
    if interval.endswith("m"):
        minutes = int(interval[:-1])
        return min(5000, days * max(1, 390 // minutes))
    if interval in {"1h", "60m"}:
        return min(5000, days * 7)
    if interval == "1wk":
        return min(5000, max(2, days // 7 + 2))
    if interval == "1mo":
        return min(5000, max(2, days // 30 + 2))
    return min(5000, max(2, int(days * 252 / 365) + 5))


def _twelve_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    api_key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not api_key:
        raise HistoricalDataError("TWELVE_DATA_API_KEY is not configured.")
    payload = _request(
        "https://api.twelvedata.com/time_series",
        {"symbol": symbol, "interval": _twelve_interval(interval), "outputsize": _output_size(period, interval), "order": "ASC", "timezone": "UTC", "apikey": api_key},
        _path("twelve", symbol, period, interval), _cache_age(period, interval),
    )
    if not isinstance(payload, dict) or payload.get("status") == "error":
        raise HistoricalDataError(str(payload.get("message") if isinstance(payload, dict) else "Invalid Twelve Data response"))
    values = payload.get("values") or []
    if not values:
        return pd.DataFrame()
    frame = pd.DataFrame(values)
    frame.index = pd.to_datetime(frame.pop("datetime"), utc=True)
    rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    frame = frame.rename(columns=rename)
    for column in rename.values():
        if column not in frame:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame.index.name = "Date"
    return frame[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])


def _fred_history(symbol: str, period: str) -> pd.DataFrame:
    api_key = os.getenv("FRED_API_KEY", "").strip()
    if not api_key:
        raise HistoricalDataError("FRED_API_KEY is not configured.")
    start = (datetime.now(timezone.utc) - timedelta(days=_period_days(period))).date().isoformat()
    series_id = FRED_SYMBOLS[symbol]
    payload = _request(
        "https://api.stlouisfed.org/fred/series/observations",
        {"series_id": series_id, "api_key": api_key, "file_type": "json", "observation_start": start, "sort_order": "asc"},
        _path("fred", series_id, period, "1d"), _cache_age(period, "1d"),
    )
    rows = [(item.get("date"), item.get("value")) for item in payload.get("observations", []) if item.get("value") not in {None, "."}]
    if not rows:
        return pd.DataFrame()
    index = pd.to_datetime([item[0] for item in rows], utc=True)
    close = pd.to_numeric([item[1] for item in rows], errors="coerce")
    frame = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 0.0}, index=index)
    frame.index.name = "Date"
    return frame.dropna(subset=["Close"])


def download_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    symbol = (symbol or "").strip().upper()
    if symbol in FRED_SYMBOLS:
        return _fred_history(symbol, period)
    return _twelve_history(symbol, period, interval)


def get_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    return download_data(symbol, period, interval)
