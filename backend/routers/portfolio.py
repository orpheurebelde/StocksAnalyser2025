from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import pandas as pd
import io
import requests
from core.yfinance_client import download_data

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

@router.post("/analyze")
@limiter.limit("5/minute")
async def analyze_portfolio(request: Request, file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files are allowed.")
        
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content), parse_dates=["Date"], dayfirst=True, on_bad_lines='skip')
        df.columns = [col.strip() for col in df.columns]
        
        required_cols = {"Date", "Symbol", "Quantity", "Purchase Price", "Current Price"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise HTTPException(400, f"Missing columns: {missing_cols}")
            
        df["Symbol"] = df["Symbol"].astype(str).str.upper().str.split('.').str[0]
        df["Investment"] = df["Quantity"] * df["Purchase Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain (€)"] = df["Market Value"] - df["Investment"]
        df["Unrealized Gain (%)"] = (df["Unrealized Gain (€)"] / df["Investment"]) * 100
        df["Year"] = df["Date"].dt.year
        
        summary = df.groupby("Symbol").agg({
            "Quantity": "sum",
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        summary["Unrealized Gain (%)"] = (summary["Unrealized Gain (€)"] / summary["Investment"]) * 100
        
        annual = df.groupby("Year").agg({
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        annual["Unrealized Gain (%)"] = (annual["Unrealized Gain (€)"] / annual["Investment"]) * 100
        
        # Calculate True Risk Metrics via YFinance
        tickers = df["Symbol"].unique()
        price_history = {}
        import numpy as np
        
        for t in tickers:
            try:
                hist = download_data(t, period="1y", interval="1d")
                if not hist.empty:
                    if isinstance(hist.columns, pd.MultiIndex):
                        hist.columns = hist.columns.get_level_values(0)
                    price_history[t] = hist["Close"]
            except:
                pass
                
        metrics = []
        if price_history:
            all_dates = pd.Index(sorted(set().union(*[s.index for s in price_history.values()])))
            portfolio_df = pd.DataFrame(index=all_dates)

            for _, row in df.iterrows():
                sym = row["Symbol"]
                qty = row["Quantity"]
                if sym in price_history:
                    # forward fill missing days
                    s = price_history[sym].reindex(all_dates).ffill() * qty
                    portfolio_df[sym] = s

            portfolio_df["Total"] = portfolio_df.sum(axis=1)

            rets = portfolio_df["Total"].pct_change().dropna()
            if len(rets) > 0:
                total_return = portfolio_df["Total"].iloc[-1] / portfolio_df["Total"].iloc[0]
                port_cagr = (total_return) ** (252 / len(rets)) - 1
                port_vol = rets.std() * np.sqrt(252)
                rf = 0.04 # Assume 4% risk-free rate
                port_sharpe = (port_cagr - rf) / port_vol if port_vol != 0 else np.nan
                port_dd = (portfolio_df["Total"] / portfolio_df["Total"].cummax() - 1).min()
                
                metrics = [
                    {"Metric": "CAGR (1Y)", "Value": f"{port_cagr*100:.2f}%"},
                    {"Metric": "Annualized Volatility", "Value": f"{port_vol*100:.2f}%"},
                    {"Metric": "Sharpe Ratio", "Value": f"{port_sharpe:.2f}"},
                    {"Metric": "Max Drawdown", "Value": f"{port_dd*100:.2f}%"}
                ]

        return {
            "transactions": df.to_dict(orient="records"),
            "summary": summary.to_dict(orient="records"),
            "annual": annual.to_dict(orient="records"),
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(500, str(e))
