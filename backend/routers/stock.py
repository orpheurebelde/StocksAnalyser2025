from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import get_ticker, download_data

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.get("/{ticker}/info")
@limiter.limit("20/minute")
def get_info(request: Request, ticker: str):
    try:
        t = get_ticker(ticker)
        return t.info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{ticker}/history")
@limiter.limit("20/minute")
def get_history(request: Request, ticker: str, period: str = "6mo", interval: str = "1d"):
    try:
        df = download_data(ticker, period=period, interval=interval)
        return df.reset_index().to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
