from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import get_ticker_info, get_ticker, download_data
from core.technical import analyze_price_action
import os
import requests
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class AIPrompt(BaseModel):
    prompt: str

@router.get("/{ticker}/info")
@limiter.limit("20/minute")
def get_info(request: Request, ticker: str):
    try:
        info = get_ticker_info(ticker)
        if not info:
            raise HTTPException(status_code=404, detail="No info found.")
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{ticker}/price-action")
@limiter.limit("20/minute")
def get_price_action(request: Request, ticker: str):
    try:
        data = download_data(ticker, period="6mo", interval="1d")
        if data.empty:
            raise HTTPException(status_code=404, detail="No historical data found.")
        score, insights = analyze_price_action(data)
        return {
            "score": score,
            "max_score": 9,
            "insights": insights
        }
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

@router.post("/{ticker}/ai-analysis")
@limiter.limit("5/minute")
def ai_analysis(request: Request, ticker: str, body: AIPrompt):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY not configured on server.")
        
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": body.prompt}],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return {"analysis": result["choices"][0]["message"]["content"].strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
