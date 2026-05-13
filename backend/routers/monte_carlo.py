from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.yfinance_client import download_data
import numpy as np

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class MonteCarloRequest(BaseModel):
    ticker: str
    n_simulations: int
    total_days: int
    log_normal: bool
    volatility: float | None = None

@router.post("/simulate")
@limiter.limit("10/minute")
def run_monte_carlo(request: Request, body: MonteCarloRequest):
    try:
        data = download_data(body.ticker, period="2y", interval="1d")
        if data.empty:
            raise HTTPException(status_code=404, detail="No price data found.")
            
        returns = data['Close'].pct_change().dropna()
        mu = returns.mean()
        sigma = returns.std() if body.volatility is None else body.volatility
        last_price = float(data['Close'].iloc[-1])
        
        simulations = np.zeros((body.n_simulations, body.total_days))
        for i in range(body.n_simulations):
            if body.log_normal:
                daily_returns = np.random.normal(mu - 0.5 * sigma**2, sigma, body.total_days)
                price_path = last_price * np.exp(np.cumsum(daily_returns))
            else:
                daily_returns = np.random.normal(mu, sigma, body.total_days)
                price_path = last_price * np.cumprod(1 + daily_returns)
            simulations[i, :] = price_path
            
        # Instead of sending all raw arrays which could be huge (10000x1000), 
        # we calculate the percentiles on the backend and only send those to the frontend chart.
        mean_path = np.mean(simulations, axis=0).tolist()
        p5_path = np.percentile(simulations, 5, axis=0).tolist()
        p25_path = np.percentile(simulations, 25, axis=0).tolist()
        p50_path = np.percentile(simulations, 50, axis=0).tolist()
        p95_path = np.percentile(simulations, 95, axis=0).tolist()
        
        final_prices = simulations[:, -1]
        mean_price = float(np.mean(final_prices))
        prob_increase = float(np.sum(final_prices > last_price) / len(final_prices) * 100)
        
        # Prepare timeseries data for Recharts
        chart_data = []
        for day in range(body.total_days):
            chart_data.append({
                "day": day,
                "mean": mean_path[day],
                "p5": p5_path[day],
                "p25": p25_path[day],
                "p50": p50_path[day],
                "p95": p95_path[day],
            })

        return {
            "current_price": last_price,
            "mean_price": mean_price,
            "p5_price": p5_path[-1],
            "p25_price": p25_path[-1],
            "p50_price": p50_path[-1],
            "p95_price": p95_path[-1],
            "prob_increase": prob_increase,
            "chart_data": chart_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
