from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import get_ticker, download_data
import numpy as np

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.get("/analysis")
@limiter.limit("5/minute")
def get_market_analysis(request: Request):
    try:
        tickers = {"S&P 500": "^GSPC", "Nasdaq 100": "^NDX"}
        results = {}
        for name, t in tickers.items():
            data = download_data(t, period="5y", interval="1d")
            if data.empty:
                continue
                
            close = data['Close']
            price = float(close.iloc[-1])
            high_52w = float(close[-252:].max())
            low_52w = float(close[-252:].min())
            
            # Simple RSI approximation
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs)).iloc[-1])
            
            # YTD
            ytd_start_idx = close.index.searchsorted(f"{close.index[-1].year}-01-01")
            start_price = float(close.iloc[ytd_start_idx])
            ytd = ((price / start_price) - 1) * 100
            
            # 1Y return
            ret_1y = float(close.pct_change(252).iloc[-1] * 100)
            
            results[name] = {
                "price": price,
                "high_52w": high_52w,
                "low_52w": low_52w,
                "rsi": rsi,
                "ytd": ytd,
                "ret_1y": ret_1y
            }
            
        vix = get_ticker("^VIX").history(period="1d", interval="1m")
        vix_val = float(vix["Close"].iloc[-1]) if not vix.empty else None
            
        return {"indices": results, "vix": vix_val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
