import json
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
try:
    import requests
except ModuleNotFoundError:  # Lightweight fallback used by minimal test runtimes.
    import urllib.error
    import urllib.parse
    import urllib.request

    class _UrlResponse:
        def __init__(self, response):
            self._response = response
            self.status_code = response.status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise urllib.error.HTTPError(self._response.url, self.status_code, "HTTP error", {}, None)

        def json(self):
            return json.loads(self._response.read().decode("utf-8"))

    class _UrlSession:
        def __init__(self):
            self.headers = {}

        def get(self, url, params, headers, timeout):
            query = urllib.parse.urlencode(params)
            request = urllib.request.Request(f"{url}?{query}", headers={**self.headers, **headers})
            return _UrlResponse(urllib.request.urlopen(request, timeout=timeout))

    class _RequestsCompat:
        RequestException = urllib.error.URLError
        Session = _UrlSession

    requests = _RequestsCompat()

BASE_URL = "https://finnhub.io/api/v1"
CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "finnhub"
CACHE_HOURS = int(os.getenv("FINNHUB_CACHE_HOURS", "24"))
MAX_REQUESTS_PER_MINUTE = int(os.getenv("FINNHUB_MAX_REQUESTS_PER_MINUTE", "55"))
MIN_REQUEST_INTERVAL_SECONDS = float(os.getenv("FINNHUB_MIN_REQUEST_INTERVAL_SECONDS", "0.1"))
TIMEOUT_SECONDS = float(os.getenv("FINNHUB_TIMEOUT_SECONDS", "12"))

_session = requests.Session()
_session.headers.update({"Accept": "application/json", "User-Agent": "StocksAnalyser2025/1.0"})
_request_lock = threading.Lock()
_recent_requests = deque()
_last_request_at = 0.0
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class FinnhubError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.getenv("FINHUB_API_KEY") or os.getenv("FINNHUB_API_KEY")
    if not key:
        raise FinnhubError("FINHUB_API_KEY is not configured.")
    return key


def _normal_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9_.=^-]+", "_", value.upper())


def _cache_path(namespace: str, key: str) -> Path:
    return CACHE_DIR / f"{namespace}_{_safe_key(key)}.json"


def _fresh(path: Path, max_age: timedelta) -> bool:
    return path.exists() and datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) < max_age


def _read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _write_json(path: Path, payload) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    temporary.replace(path)


def _wait_for_slot() -> None:
    global _last_request_at
    with _request_lock:
        now = time.monotonic()
        while _recent_requests and now - _recent_requests[0] >= 60:
            _recent_requests.popleft()
        if len(_recent_requests) >= MAX_REQUESTS_PER_MINUTE:
            time.sleep(max(0.0, 60 - (now - _recent_requests[0])))
            now = time.monotonic()
            while _recent_requests and now - _recent_requests[0] >= 60:
                _recent_requests.popleft()
        elapsed = now - _last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
            now = time.monotonic()
        _recent_requests.append(now)
        _last_request_at = now


def _get(endpoint: str, params: dict, path: Path | None = None, max_age: timedelta | None = None):
    if path and max_age and _fresh(path, max_age):
        cached = _read_json(path)
        if cached is not None:
            return cached
    stale = _read_json(path) if path and path.exists() else None
    try:
        _wait_for_slot()
        response = _session.get(
            f"{BASE_URL}/{endpoint.lstrip('/')}", params=params,
            headers={"X-Finnhub-Token": _api_key()}, timeout=TIMEOUT_SECONDS,
        )
        if response.status_code == 429:
            raise FinnhubError("Finnhub rate limit exceeded (429).")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise FinnhubError(str(payload["error"]))
        if path:
            try:
                _write_json(path, payload)
            except OSError:
                pass
        return payload
    except (requests.RequestException, ValueError, FinnhubError):
        if stale is not None:
            return stale
        raise


def search_symbols(query: str) -> list[dict]:
    payload = _get("search", {"q": query}, _cache_path("search", query), timedelta(hours=6))
    results = []
    for item in payload.get("result", []) if isinstance(payload, dict) else []:
        item_type = str(item.get("type") or "").lower()
        if item_type and not any(kind in item_type for kind in ("stock", "common", "etf", "etp", "fund", "equity")):
            continue
        symbol = item.get("symbol") or item.get("displaySymbol")
        if symbol:
            results.append({"symbol": symbol, "name": item.get("description") or ""})
    return results


def _metric(metric: dict, *names):
    for name in names:
        if metric.get(name) is not None:
            return metric[name]
    return None


def _ratio(value):
    return None if value is None else float(value) / 100.0


def _recommendation_fields(rows) -> dict:
    if not rows or not isinstance(rows, list):
        return {}
    row = rows[0]
    weights = {"strongBuy": 1, "buy": 2, "hold": 3, "sell": 4, "strongSell": 5}
    total = sum(int(row.get(key) or 0) for key in weights)
    if not total:
        return {}
    mean = sum(weights[key] * int(row.get(key) or 0) for key in weights) / total
    labels = [(1.5, "strong_buy"), (2.5, "buy"), (3.5, "hold"), (4.5, "sell"), (6, "strong_sell")]
    return {"recommendationMean": mean, "recommendationKey": next(label for ceiling, label in labels if mean < ceiling), "numberOfAnalystOpinions": total}


def get_ticker_info(symbol: str):
    symbol = _normal_symbol(symbol)
    info_path = _cache_path("info", symbol)
    if _fresh(info_path, timedelta(hours=CACHE_HOURS)):
        cached = _read_json(info_path)
        if cached:
            return cached
    quote = _get("quote", {"symbol": symbol}, _cache_path("quote", symbol), timedelta(minutes=10))
    profile = _get("stock/profile2", {"symbol": symbol}, _cache_path("profile", symbol), timedelta(days=7))
    basics = _get("stock/metric", {"symbol": symbol, "metric": "all"}, _cache_path("metric", symbol), timedelta(hours=CACHE_HOURS))
    metric = basics.get("metric", {}) if isinstance(basics, dict) else {}
    if not quote.get("c") and not profile.get("name") and not metric:
        return None
    info = {
        "symbol": symbol, "shortName": profile.get("name") or symbol, "longName": profile.get("name") or symbol,
        "currency": profile.get("currency"), "exchange": profile.get("exchange"), "industry": profile.get("finnhubIndustry"),
        "website": profile.get("weburl"), "logo_url": profile.get("logo"), "currentPrice": quote.get("c"),
        "regularMarketPrice": quote.get("c"), "previousClose": quote.get("pc"), "dayHigh": quote.get("h"),
        "dayLow": quote.get("l"), "open": quote.get("o"),
        "marketCap": (profile.get("marketCapitalization") or 0) * 1_000_000 or None,
        "sharesOutstanding": (profile.get("shareOutstanding") or 0) * 1_000_000 or None,
        "fiftyTwoWeekHigh": _metric(metric, "52WeekHigh"), "fiftyTwoWeekLow": _metric(metric, "52WeekLow"),
        "trailingPE": _metric(metric, "peTTM", "peBasicExclExtraTTM", "peAnnual"), "forwardPE": _metric(metric, "forwardPE"),
        "priceToBook": _metric(metric, "pbAnnual", "pbQuarterly"), "priceToSalesTrailing12Months": _metric(metric, "psTTM", "psAnnual"),
        "trailingEps": _metric(metric, "epsInclExtraItemsTTM", "epsBasicExclExtraItemsTTM", "epsAnnual"),
        "forwardEps": _metric(metric, "epsEstimateCurrentYear"), "epsCurrentYear": _metric(metric, "epsGrowthTTMYoy", "epsGrowthQuarterlyYoy"),
        "trailingPegRatio": _metric(metric, "pegRatio"), "grossMargins": _ratio(_metric(metric, "grossMarginTTM", "grossMarginAnnual")),
        "operatingMargins": _ratio(_metric(metric, "operatingMarginTTM", "operatingMarginAnnual")),
        "profitMargins": _ratio(_metric(metric, "netProfitMarginTTM", "netProfitMarginAnnual")),
        "returnOnEquity": _ratio(_metric(metric, "roeTTM", "roeRfy", "roeAnnual")),
        "returnOnAssets": _ratio(_metric(metric, "roaTTM", "roaRfy", "roaAnnual")),
        "currentRatio": _metric(metric, "currentRatioQuarterly", "currentRatioAnnual"),
        "revenueGrowth": _ratio(_metric(metric, "revenueGrowthTTMYoy", "revenueGrowthQuarterlyYoy")),
        "earningsGrowth": _ratio(_metric(metric, "epsGrowthTTMYoy", "epsGrowthAnnual")),
        "earningsQuarterlyGrowth": _ratio(_metric(metric, "epsGrowthQuarterlyYoy")),
    }
    try:
        info.update(_recommendation_fields(_get("stock/recommendation", {"symbol": symbol}, _cache_path("recommendation", symbol), timedelta(hours=CACHE_HOURS))))
    except Exception:
        pass
    try:
        _write_json(info_path, info)
    except OSError:
        pass
    return info
