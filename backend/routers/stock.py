from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import get_ticker_info, download_data
from core.technical import analyze_price_action
from core.auth import ensure_analysis_quota, record_analysis_use
import os
import requests
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class AIPrompt(BaseModel):
    prompt: str

@router.get("/{ticker}/full-analysis")
@limiter.limit("10/minute")
def get_full_analysis(request: Request, ticker: str):
    from core.technical import estimate_past_shares_outstanding, interpret_dilution_extended, calculate_fundamentals_score
    try:
        # 1. Fetch Info
        info = get_ticker_info(ticker)
        if not info:
            raise HTTPException(status_code=404, detail="No info found.")
        
        # Calculate Fundamentals Score
        fundamentals_score = calculate_fundamentals_score(info)

        # 2. Fetch 1y Data for everything
        hist = download_data(ticker, period="1y", interval="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail="No historical data found.")

        # 3. Price Action (Last 6 months approx 126 trading days)
        hist_6mo = hist.iloc[-126:] if len(hist) > 126 else hist
        try:
            pa_score, pa_insights = analyze_price_action(hist_6mo)
            price_action = {
                "score": pa_score,
                "max_score": 9,
                "insights": pa_insights
            }
        except Exception as e:
            price_action = None

        # 4. Dilution
        try:
            current_shares, past_shares, dilution_amt = estimate_past_shares_outstanding(info, hist)
            if not past_shares:
                dilution_data = {"dilution_pct": 0, "comments": ["Could not calculate past shares."]}
            else:
                dilution_pct = (dilution_amt / past_shares) * 100
                comments = interpret_dilution_extended(
                    dilution_pct,
                    revenue_growth=info.get("revenueGrowth"),
                    eps_current=info.get("trailingEps"),
                    eps_forward=info.get("forwardEps"),
                    sbc_expense=info.get("shareBasedCompensation"),
                    total_revenue=info.get("totalRevenue"),
                    cash_from_financing=info.get("totalCashFromFinancingActivities")
                )
                dilution_data = {
                    "current_shares": current_shares,
                    "past_shares": past_shares,
                    "dilution_amount": dilution_amt,
                    "dilution_pct": dilution_pct,
                    "comments": comments
                }
        except Exception:
            dilution_data = None

        # 5. Return Master Payload
        return {
            "info": info,
            "fundamentals_score": fundamentals_score,
            "price_action": price_action,
            "dilution": dilution_data
        }

    except HTTPException:
        raise
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
    try:
        user = request.state.user
        if not (user.get("is_admin") or user.get("analysis_authorized")):
            raise HTTPException(status_code=403, detail="AI analysis requires administrator authorization.")
        try:
            ensure_analysis_quota(user)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        from core.ai.orchestrator import AnalysisOrchestrator
        orchestrator = AnalysisOrchestrator()
        result = orchestrator.run_analysis(ticker, body.prompt)
        record_analysis_use(user["id"], "stock")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
@limiter.limit("30/minute")
def search_ticker(request: Request, q: str):
    import requests
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={q}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        quotes = data.get("quotes", [])
        results = [{"symbol": q.get("symbol"), "name": q.get("shortname", q.get("longname", ""))} for q in quotes if q.get("quoteType") in ["EQUITY", "ETF"]]
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
