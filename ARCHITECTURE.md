# StocksAnalyser2025 architecture

## Runtime

- Frontend: React 19 + Vite, deployed on Vercel.
- Backend: FastAPI + Uvicorn, deployed on Render.
- Market data: unified free-provider facade (`market_data_client.py`).
- Quarter Earnings: SEC/XBRL primary; Finnhub enrichment; yfinance lazy fallback only when Finnhub fails.
- Persistence: PostgreSQL when `DATABASE_URL` is configured.

## Production flow

1. Browser loads application from Vercel.
2. Frontend sends same-origin requests to `/api/*`.
3. `frontend/vercel.json` rewrites them to `https://stocksanalyser.onrender.com/api/*`.
4. FastAPI authenticates session, applies route limits, calls Finnhub, and returns existing API contracts.

Same-origin rewrites keep authentication cookies first-party. `VITE_API_URL` is optional and only needed for another backend URL.

## Market-data compatibility

`backend/core/market_data_client.py` is the only market-data entry point used by routes. It orchestrates Finnhub, Twelve Data, FRED, SEC/XBRL and FMP while preserving existing formats:

- information keys expected by React and calculations;
- Pandas OHLCV frames with `Open`, `High`, `Low`, `Close`, `Volume`;
- financial-statement frames used by DCF and Quarter Earnings;
- search results shaped as `{symbol, name}`.

HTTP session is shared. Requests use timeouts, rate limiting, and bounded disk caches. No unbounded in-memory response cache exists.

`backend/core/yfinance_client.py` remains solely for Quarter Earnings fallback. Lazy imports prevent yfinance loading during normal Finnhub operation.

## Routes

- `/api/auth`: authentication, sessions, quotas, administration.
- `/api/stock`: stock information, history, search, AI analysis.
- `/api/market`: index analysis and AAII sentiment.
- `/api/dcf`: DCF calculations.
- `/api/monte-carlo`: price simulations.
- `/api/comparison`: multi-stock comparison.
- `/api/portfolio`: portfolios, imports, history, risk metrics.
- `/api/quarter-earnings`: SEC/PDF ingestion, scoring, valuation, AI analysis.

See `DEPLOYMENT.md` for environment and deployment configuration. Existing `FINHUB_API_KEY` spelling and canonical `FINNHUB_API_KEY` are both supported.
