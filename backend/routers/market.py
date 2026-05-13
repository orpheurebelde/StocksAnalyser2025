from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import get_ticker

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.get("/vix")
@limiter.limit("10/minute")
def get_vix(request: Request):
    try:
        vix = get_ticker("^VIX")
        data = vix.history(period="1d", interval="1m")
        if not data.empty:
            return {"vix": float(data["Close"].iloc[-1])}
        return {"vix": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
