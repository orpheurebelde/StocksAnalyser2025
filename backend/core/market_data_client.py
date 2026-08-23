"""Single market-data facade used by every route.

Provider policy:
- Finnhub Free: quote, search, profile2, basic metrics, recommendations.
- SEC/XBRL: reported US financial facts.
- FMP Free: detailed profile, forward estimates, analyst targets.
- Twelve Data Free: equity/ETF OHLCV history.
- FRED: index and VIX daily history.
"""

from core.finnhub_client import get_ticker_info as _finnhub_info, search_symbols
from core.fmp_client import get_fmp_info_fields
from core.historical_client import download_data, get_history
from core.sec_financials import get_sec_info_fields


def get_ticker_info(symbol: str):
    base = _finnhub_info(symbol) or {}
    # Reported SEC facts override vendor-standardized totals. FMP only fills
    # missing fields, except forward-looking fields unavailable in free Finnhub.
    sec = get_sec_info_fields(symbol)
    base.update(sec)
    fmp = get_fmp_info_fields(symbol)
    forward_fields = {"forwardEps", "forwardPE", "targetMeanPrice", "targetLowPrice", "targetHighPrice"}
    for key, value in fmp.items():
        if value is not None and (key in forward_fields or base.get(key) is None):
            base[key] = value
    return base or None


__all__ = ["download_data", "get_history", "get_ticker_info", "search_symbols"]
