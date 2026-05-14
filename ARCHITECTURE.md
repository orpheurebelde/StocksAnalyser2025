# StocksAnalyser2025 - Architecture Map for AI Agents

> [!NOTE]
> This document provides a high-level architectural overview of the StocksAnalyser2025 application. It is designed to quickly orient AI Agents or developers to the file structure, technology stack, data flow, and routing of the application.

## 🚀 Technology Stack

- **Frontend:** React 19 (Vite) + React Router DOM + Recharts (for charting) + Tailwind/Vanilla CSS (`index.css`)
- **Backend:** Python 3.14 + FastAPI + Uvicorn
- **Data Integrations:** YFinance (Core market data), Mistral AI (LLM Analyst logic)
- **Deployment Strategy:** Vercel (Frontend) + Render (Backend)

---

## 📁 Directory Structure Overview

### `/frontend` (React SPA)
The frontend uses standard Vite architecture. All network requests go through an Axios instance (`api.js`) which points to the FastAPI backend.

- `src/App.jsx`: Main routing file defining all 6 major views.
- `src/index.css`: Global CSS containing the custom "Glassmorphic" design system and markdown styling logic (`.markdown-content`).
- `src/api.js`: Axios client configured with `import.meta.env.VITE_API_URL`.
- `src/pages/`:
  - `Dashboard.jsx`: Market analysis overview (S&P 500, Nasdaq, VIX) with technicals.
  - `StockInfo.jsx`: Deep dive into a single ticker. Contains TradingView iframe, fundamentals, share dilution, and dynamic Mistral AI prompting.
  - `Portfolio.jsx`: Portfolio risk metric calculators (CAGR, Sharpe, Max Drawdown).
  - `DCFCalculator.jsx`: Interactive Discounted Cash Flow modeling with Recharts graphs.
  - `MonteCarlo.jsx`: Monte Carlo simulation parameters and results.
  - `StockComparison.jsx`: Side-by-side metric comparison of multiple tickers.

### `/backend` (FastAPI)
The backend is split into logical routers and core calculation modules to maintain separation of concerns and avoid massive files.

- `main.py`: Application entry point. Configures CORS, initializes `slowapi` rate limiter, and mounts all routers.
- `core/`:
  - `yfinance_client.py`: The single source of truth for Yahoo Finance scraping. Implements custom JSON/CSV caching to prevent rate-limit blocks.
  - `technical.py`: Complex math functions (Fibonacci, RSI, MACD calculations, Price Action 9-point score, Dilution estimation).
- `routers/`:
  - `stock.py` (`/api/stock`): Contains the master `/full-analysis` endpoint which batches fundamental and historical fetches to bypass YF rate limits. Also handles Mistral AI proxy requests.
  - `market.py` (`/api/market`): Serves macro market data.
  - `dcf.py` (`/api/dcf`): Handles Discounted Cash Flow backend formulas.
  - `monte_carlo.py` (`/api/monte-carlo`): Handles simulation math.
  - `portfolio.py` (`/api/portfolio`): Processes historical list of tickers to compute portfolio-level volatility and returns.
  - `comparison.py` (`/api/comparison`): Batches info fetching for multiple stocks.

---

## 🔄 Data Flow & Rate Limiting Strategy

> [!IMPORTANT]
> Yahoo Finance rate limits are extremely strict. The application handles this via **Endpoint Batching** and **Disk Caching**.

1. **Frontend Request:** When a user navigates to `StockInfo.jsx` and searches for "AAPL", React makes a *single* batched request to `/api/stock/AAPL/full-analysis`.
2. **Backend Intercept:** `stock.py` receives the request.
3. **Fundamental Cache Check:** `yfinance_client.py` checks `cache/stock_info_cache.json`. If valid, it returns the fundamental dictionary immediately. If missing/stale, it fetches `yf.Ticker().info`.
4. **Historical Cache Check:** `yfinance_client.py` checks for `cache/AAPL_1y_1d.csv`. If valid, it reads the local CSV. If missing, it downloads a single 1-year history dataset.
5. **Compute & Respond:** The backend slices the historical data to compute the Price Action score (last 6 months) and Dilution score (1-year span), combines everything with the fundamentals, and returns it in one JSON payload.

## 🤖 AI Integration (Mistral)
- The React frontend constructs highly structured Markdown prompts using live YFinance data.
- The user can view/edit these prompts in the UI.
- The prompt is sent to `POST /api/stock/{ticker}/ai-analysis`.
- FastAPI proxies the request securely to Mistral's API (hiding the `MISTRAL_API_KEY`).
- The frontend renders the returned Markdown using `react-markdown` and `remark-gfm` (for table support).
