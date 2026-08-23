import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


BASE_URL = "https://financialmodelingprep.com/stable"
CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "fmp"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _api_key() -> str:
    key = os.getenv("FMP_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FMP_API_KEY is not configured.")
    return key


def _get(endpoint: str, symbol: str, hours: int = 24, extra: dict | None = None):
    path = CACHE_DIR / f"{endpoint.replace('/', '_')}_{symbol.upper()}.json"
    if path.exists() and datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) < timedelta(hours=hours):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    query = urllib.parse.urlencode({"symbol": symbol.upper(), **(extra or {}), "apikey": _api_key()})
    request = urllib.request.Request(f"{BASE_URL}/{endpoint}?{query}", headers={"Accept": "application/json", "User-Agent": "StocksAnalyser2025/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, dict) and (payload.get("Error Message") or payload.get("error")):
        raise RuntimeError(str(payload.get("Error Message") or payload.get("error")))
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)
    return payload


def _first(payload) -> dict:
    if isinstance(payload, list):
        return payload[0] if payload else {}
    return payload if isinstance(payload, dict) else {}


def _number(row: dict, *keys):
    for key in keys:
        value = row.get(key)
        if value not in {None, "", "None"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def get_fmp_info_fields(symbol: str) -> dict:
    result = {}
    try:
        profile = _first(_get("profile", symbol, 168))
        mapped = {
            "shortName": profile.get("companyName"), "longName": profile.get("companyName"),
            "sector": profile.get("sector"), "industry": profile.get("industry"),
            "website": profile.get("website"), "longBusinessSummary": profile.get("description"),
            "country": profile.get("country"), "city": profile.get("city"), "state": profile.get("state"),
            "fullTimeEmployees": _number(profile, "fullTimeEmployees", "employees"),
            "marketCap": _number(profile, "marketCap"), "currentPrice": _number(profile, "price"),
            "regularMarketPrice": _number(profile, "price"), "currency": profile.get("currency"),
        }
        result.update({key: value for key, value in mapped.items() if value is not None})
    except Exception:
        pass

    try:
        estimate = _first(_get("analyst-estimates", symbol, 24, {"period": "annual", "page": 0, "limit": 2}))
        forward_eps = _number(estimate, "estimatedEpsAvg", "epsAvg", "estimatedEps")
        current_price = result.get("currentPrice")
        mapped = {
            "forwardEps": forward_eps,
            "forwardPE": (current_price / forward_eps) if current_price and forward_eps and forward_eps > 0 else None,
            "numberOfAnalystOpinions": _number(estimate, "numberAnalystsEstimatedEps", "numAnalystsEps", "numberAnalystEstimatedEps"),
        }
        result.update({key: value for key, value in mapped.items() if value is not None})
    except Exception:
        pass

    try:
        target = _first(_get("price-target-consensus", symbol))
        mapped = {
            "targetMeanPrice": _number(target, "targetConsensus", "targetMean", "targetAverage"),
            "targetLowPrice": _number(target, "targetLow"),
            "targetHighPrice": _number(target, "targetHigh"),
        }
        result.update({key: value for key, value in mapped.items() if value is not None})
    except Exception:
        pass
    return result
