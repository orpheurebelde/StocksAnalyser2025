from fastapi import APIRouter, Request, HTTPException
from typing import List
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import get_ticker

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class CompareRequest(BaseModel):
    tickers: List[str]

@router.post("/compare")
@limiter.limit("20/minute")
def compare_stocks(request: Request, body: CompareRequest):
    results = {}
    for t in body.tickers:
        try:
            info = get_ticker(t).info
            results[t] = {
                "Trailing PE": info.get("trailingPE"),
                "Forward PE": info.get("forwardPE"),
                "Price/Book": info.get("priceToBook"),
                "Price/Sales": info.get("priceToSalesTrailing12Months"),
                "Free Cash Flow": info.get("freeCashflow"),
                "ROE": info.get("returnOnEquity"),
                "ROA": info.get("returnOnAssets"),
                "EBITDA": info.get("ebitda"),
                "Trailing EPS": info.get("trailingEps"),
                "Forward EPS": info.get("forwardEps"),
                "Gross Margin": info.get("grossMargins"),
                "Operating Margin": info.get("operatingMargins"),
                "Profit Margin": info.get("profitMargins"),
                "Net Income": info.get("netIncomeToCommon"),
                "Total Revenue": info.get("totalRevenue"),
                "Total Cash": info.get("totalCash"),
                "Total Debt": info.get("totalDebt"),
                "Current Ratio": info.get("currentRatio")
            }
        except Exception as e:
            results[t] = {"error": str(e)}
    return results
