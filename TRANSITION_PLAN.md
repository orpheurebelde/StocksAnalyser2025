# Finnhub transition status

- [x] Central market-data facade coordinating all free providers.
- [x] Compatibility adapter for information, OHLCV history, search and statements.
- [x] Stock, Comparison, Portfolio, Monte Carlo and Market routes migrated to facade.
- [x] Twelve Data provides equity history; FRED provides index/VIX history.
- [x] SEC provides reported facts; FMP provides profiles, estimates and targets.
- [x] Direct Yahoo searches removed.
- [x] Quarter Earnings uses Finnhub first and lazy yfinance fallback.
- [x] Legacy Python UI removed; React/Vercel and FastAPI/Render remain.
- [x] Render and Vercel environment examples documented.
- [x] Monte Carlo memory bounded and matrix memory reduced.
- [ ] Run authenticated production smoke after deployment with live Finnhub entitlement.
