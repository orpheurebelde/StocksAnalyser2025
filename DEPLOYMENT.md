# Deployment: Vercel + Render

## Render backend

- Build from repository root: `pip install -r requirements.txt`
- Start from repository root: `uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT`
- If Render root is `backend`, use `pip install -r requirements.txt` and `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Health endpoint: `/`

Required variables:

- `FINHUB_API_KEY`: existing deployed Finnhub key. `FINNHUB_API_KEY` also works.
- `TWELVE_DATA_API_KEY`: equity and ETF OHLCV history.
- `FRED_API_KEY`: S&P 500, Nasdaq 100 and VIX daily series.
- `FMP_API_KEY`: detailed profiles, forward estimates and analyst targets.
- `DATABASE_URL`: Render PostgreSQL connection.
- `GOOGLE_CLIENT_ID`: Google OAuth web client ID.
- `MISTRAL_API_KEY`: stock and valuation AI.
- `GROQ_API_KEY`: Quarter Earnings AI.
- `FRONTEND_ORIGINS=https://stocks-valuation.vercel.app`
- `AUTH_COOKIE_SECURE=true`
- `SEC_USER_AGENT`: application name plus contact email.

Optional tuning:

- `FINNHUB_CACHE_HOURS=24`
- `FINNHUB_MAX_REQUESTS_PER_MINUTE=55`
- `FINNHUB_MIN_REQUEST_INTERVAL_SECONDS=0.1`
- `FINNHUB_TIMEOUT_SECONDS=12`
- `AUTH_SESSION_DAYS=7`
- `MAX_REGISTERED_USERS=90`
- `ADMIN_EMAILS`: comma-separated emails.

Keep `yfinance` installed: Quarter Earnings uses it as lazy fallback.

## Vercel frontend

- Project root: `frontend`
- Build: `npm run build`
- Output: `dist`
- `VITE_GOOGLE_CLIENT_ID`: recommended.
- Leave `VITE_API_URL` unset to use same-origin rewrite from `frontend/vercel.json`.

If Render URL changes, update `frontend/vercel.json` and `FRONTEND_ORIGINS`, then redeploy both services.
