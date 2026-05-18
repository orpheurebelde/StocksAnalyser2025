import json
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"
INFO_CACHE_FILE = CACHE_DIR / "stock_info_cache.json"
FAILURE_CACHE_FILE = CACHE_DIR / "yfinance_failures.json"
STATEMENT_CACHE_DIR = CACHE_DIR / "statements"

CACHE_HOURS = int(os.getenv("YF_CACHE_HOURS", "24"))
FALLBACK_CACHE_MINUTES = int(os.getenv("YF_FALLBACK_CACHE_MINUTES", "30"))
RATE_LIMIT_COOLDOWN_MINUTES = int(os.getenv("YF_RATE_LIMIT_COOLDOWN_MINUTES", "10"))
MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv("YF_MIN_REQUEST_INTERVAL_SECONDS", "1.5"))
MAX_REQUESTS_PER_MINUTE = int(os.getenv("YF_MAX_REQUESTS_PER_MINUTE", "30"))

_request_lock = threading.Lock()
_recent_requests = deque()
_last_request_at = 0.0

CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATEMENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _normal_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _safe_cache_key(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9_.=^-]+", "_", _normal_symbol(symbol))


def _cache_path(symbol: str, period: str, interval: str) -> Path:
    return CACHE_DIR / f"{_safe_cache_key(symbol)}_{period}_{interval}.csv"


def _statement_cache_path(symbol: str, statement: str) -> Path:
    return STATEMENT_CACHE_DIR / f"{_safe_cache_key(symbol)}_{statement}.pkl"


def _json_default(value):
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, default=_json_default)
    tmp.replace(path)


def _is_rate_limit_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "rate limit",
            "too many requests",
            "429",
            "yfratelimiterror",
            "unauthorized",
            "crumb",
        )
    )


def _record_failure(symbol: str, error: Exception) -> None:
    failures = _read_json(FAILURE_CACHE_FILE)
    failures[_safe_cache_key(symbol)] = {
        "_timestamp": datetime.now().isoformat(),
        "is_rate_limit": _is_rate_limit_error(error),
        "error": str(error),
    }
    try:
        _write_json(FAILURE_CACHE_FILE, failures)
    except Exception:
        pass


def _recent_rate_limit(symbol: str) -> bool:
    failures = _read_json(FAILURE_CACHE_FILE)
    entry = failures.get(_safe_cache_key(symbol))
    if not entry or not entry.get("is_rate_limit"):
        return False
    try:
        failed_at = datetime.fromisoformat(entry.get("_timestamp", "2000-01-01T00:00:00"))
    except Exception:
        return False
    return datetime.now() - failed_at < timedelta(minutes=RATE_LIMIT_COOLDOWN_MINUTES)


def _wait_for_yahoo_slot() -> None:
    global _last_request_at

    with _request_lock:
        now = time.monotonic()
        while _recent_requests and now - _recent_requests[0] > 60:
            _recent_requests.popleft()

        if len(_recent_requests) >= MAX_REQUESTS_PER_MINUTE:
            sleep_for = max(0.0, 60 - (now - _recent_requests[0]))
            time.sleep(sleep_for)
            now = time.monotonic()
            while _recent_requests and now - _recent_requests[0] > 60:
                _recent_requests.popleft()

        elapsed = now - _last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
            now = time.monotonic()

        _recent_requests.append(now)
        _last_request_at = now


def _is_cache_fresh(path: Path, max_age: timedelta) -> bool:
    if not path.exists():
        return False
    file_time = datetime.fromtimestamp(path.stat().st_mtime)
    return datetime.now() - file_time < max_age


def _history_cache_duration(period: str, interval: str) -> timedelta:
    if interval.endswith("m"):
        return timedelta(minutes=15)
    if period in {"1d", "5d"}:
        return timedelta(hours=1)
    return timedelta(hours=CACHE_HOURS)


def _read_cached_history(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _load_info_cache(symbol: str):
    cache = _read_json(INFO_CACHE_FILE)
    cached_data = cache.get(_normal_symbol(symbol))
    if not cached_data:
        return None, None, cache

    try:
        fetch_time = datetime.fromisoformat(cached_data.get("_timestamp", "2000-01-01T00:00:00"))
    except Exception:
        fetch_time = datetime(2000, 1, 1)
    return cached_data.get("info"), fetch_time, cache


def _minimal_info_from_fast_info(ticker: yf.Ticker, symbol: str) -> dict:
    fast = ticker.fast_info
    if not fast or len(fast) == 0:
        return {}
    return {
        "currentPrice": getattr(fast, "last_price", None),
        "marketCap": getattr(fast, "market_cap", None),
        "fiftyTwoWeekLow": getattr(fast, "year_low", None),
        "fiftyTwoWeekHigh": getattr(fast, "year_high", None),
        "shortName": symbol,
        "symbol": symbol,
    }


def get_ticker_info(symbol: str):
    """Return Yahoo info with throttling, disk cache, and stale fallback."""
    symbol = _normal_symbol(symbol)
    cached_info, fetch_time, cache = _load_info_cache(symbol)

    if cached_info:
        is_fallback = "grossMargins" not in cached_info
        cache_duration = (
            timedelta(minutes=FALLBACK_CACHE_MINUTES)
            if is_fallback
            else timedelta(hours=CACHE_HOURS)
        )
        if datetime.now() - fetch_time < cache_duration:
            return cached_info
        if _recent_rate_limit(symbol):
            return cached_info

    try:
        _wait_for_yahoo_slot()
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or ("regularMarketPrice" not in info and "currentPrice" not in info):
            info = _minimal_info_from_fast_info(ticker, symbol)
    except Exception as e:
        _record_failure(symbol, e)
        if cached_info:
            return cached_info
        print(f"Error fetching info for {symbol}: {e}")
        return None

    if not info:
        return cached_info

    cache[symbol] = {"_timestamp": datetime.now().isoformat(), "info": info}
    try:
        _write_json(INFO_CACHE_FILE, cache)
    except Exception:
        pass

    return info


def get_ticker(symbol: str):
    """Compatibility helper. Prefer cached wrappers for new code."""
    return yf.Ticker(_normal_symbol(symbol))


def download_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Return historical prices with throttling, disk cache, and stale fallback."""
    symbol = _normal_symbol(symbol)
    path = _cache_path(symbol, period, interval)
    cache_duration = _history_cache_duration(period, interval)

    if _is_cache_fresh(path, cache_duration):
        cached = _read_cached_history(path)
        if not cached.empty:
            return cached

    stale = _read_cached_history(path) if path.exists() else pd.DataFrame()
    if not stale.empty and _recent_rate_limit(symbol):
        return stale

    try:
        _wait_for_yahoo_slot()
        df = yf.download(symbol, period=period, interval=interval, progress=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if not df.empty:
            df.to_csv(path)
            return df
    except Exception as e:
        _record_failure(symbol, e)
        print(f"Error downloading data for {symbol}: {e}")

    return stale


def get_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    return download_data(symbol, period=period, interval=interval)


def get_statement(symbol: str, statement: str) -> pd.DataFrame:
    """Return cached yfinance statement dataframes like cashflow/balance_sheet."""
    symbol = _normal_symbol(symbol)
    allowed = {
        "balance_sheet",
        "quarterly_balance_sheet",
        "cashflow",
        "quarterly_cashflow",
        "financials",
    }
    if statement not in allowed:
        raise ValueError(f"Unsupported Yahoo statement: {statement}")

    path = _statement_cache_path(symbol, statement)
    if _is_cache_fresh(path, timedelta(hours=CACHE_HOURS)):
        try:
            return pd.read_pickle(path)
        except Exception:
            pass

    stale = pd.DataFrame()
    if path.exists():
        try:
            stale = pd.read_pickle(path)
        except Exception:
            stale = pd.DataFrame()

    if not stale.empty and _recent_rate_limit(symbol):
        return stale

    try:
        _wait_for_yahoo_slot()
        ticker = yf.Ticker(symbol)
        df = getattr(ticker, statement)
        if df is not None and not df.empty:
            df.to_pickle(path)
            return df
    except Exception as e:
        _record_failure(symbol, e)
        print(f"Error fetching {statement} for {symbol}: {e}")

    return stale
