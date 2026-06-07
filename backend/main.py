from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from routers import stock, market, dcf, monte_carlo, comparison, portfolio, quarter_earnings

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="StocksAnalyser API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://stocks-valuation.vercel.app",
        "https://stocksanalyser.onrender.com",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router, prefix="/api/stock", tags=["stock"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(dcf.router, prefix="/api/dcf", tags=["dcf"])
app.include_router(monte_carlo.router, prefix="/api/monte-carlo", tags=["monte-carlo"])
app.include_router(comparison.router, prefix="/api/comparison", tags=["comparison"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(quarter_earnings.router, prefix="/api/quarter-earnings", tags=["quarter-earnings"])

@app.get("/")
@limiter.limit("10/minute")
def read_root(request: Request):
    return {"status": "ok", "message": "API is running"}
