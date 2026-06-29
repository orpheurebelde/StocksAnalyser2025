from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
import pandas as pd
import io
import requests
from core.portfolio_store import (
    add_ticker,
    create_portfolio,
    delete_portfolio,
    get_portfolio,
    list_portfolios,
    remove_ticker,
    rename_portfolio,
)
from core.yfinance_client import download_data, get_ticker_info

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class PortfolioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class TickerRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=15)


def _user_id(request: Request) -> int:
    return request.state.user["id"]


def _ticker_snapshot(ticker: str) -> dict:
    info = get_ticker_info(ticker) or {}
    history = download_data(ticker, period="5y", interval="1mo")
    evolution = []
    if history is not None and not history.empty:
        if isinstance(history.columns, pd.MultiIndex):
            history.columns = history.columns.get_level_values(0)
        close = history.get("Close")
        if close is not None:
            close = close.dropna()
            evolution = [
                {"date": index.strftime("%Y-%m-%d"), "close": round(float(value), 4)}
                for index, value in close.items()
            ]
    return {
        "ticker": ticker,
        "name": info.get("shortName") or info.get("longName") or ticker,
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "currency": info.get("currency"),
        "evolution": evolution,
    }


@router.get("")
@limiter.limit("60/minute")
def saved_portfolios(request: Request):
    return {"portfolios": list_portfolios(_user_id(request)), "max_portfolios": 5}


@router.post("")
@limiter.limit("20/minute")
def new_portfolio(request: Request, body: PortfolioRequest):
    try:
        return {"portfolio": create_portfolio(_user_id(request), body.name)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{portfolio_id}")
@limiter.limit("20/minute")
def update_portfolio(request: Request, portfolio_id: int, body: PortfolioRequest):
    try:
        portfolio = rename_portfolio(_user_id(request), portfolio_id, body.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not portfolio:
        raise HTTPException(404, "Portfolio not found.")
    return {"portfolio": portfolio}


@router.delete("/{portfolio_id}")
@limiter.limit("20/minute")
def remove_portfolio(request: Request, portfolio_id: int):
    if not delete_portfolio(_user_id(request), portfolio_id):
        raise HTTPException(404, "Portfolio not found.")
    return {"deleted": True}


@router.post("/{portfolio_id}/tickers")
@limiter.limit("30/minute")
def save_ticker(request: Request, portfolio_id: int, body: TickerRequest):
    try:
        info = get_ticker_info(body.ticker.strip().upper())
        if not info:
            raise ValueError("Ticker was not found.")
        portfolio = add_ticker(_user_id(request), portfolio_id, body.ticker)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Ticker could not be validated: {exc}") from exc
    if not portfolio:
        raise HTTPException(404, "Portfolio not found.")
    return {"portfolio": portfolio}


@router.delete("/{portfolio_id}/tickers/{ticker}")
@limiter.limit("30/minute")
def delete_ticker(request: Request, portfolio_id: int, ticker: str):
    portfolio = remove_ticker(_user_id(request), portfolio_id, ticker)
    if not portfolio:
        raise HTTPException(404, "Portfolio not found.")
    return {"portfolio": portfolio}


@router.get("/{portfolio_id}/analysis")
@limiter.limit("10/minute")
def analyze_saved_portfolio(request: Request, portfolio_id: int):
    portfolio = get_portfolio(_user_id(request), portfolio_id)
    if not portfolio:
        raise HTTPException(404, "Portfolio not found.")
    snapshots = []
    errors = []
    for ticker in portfolio["tickers"]:
        try:
            snapshots.append(_ticker_snapshot(ticker))
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})
    return {"portfolio": portfolio, "tickers": snapshots, "errors": errors}

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
