from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from datetime import date

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
    update_holding,
)
from core.yfinance_client import download_data, get_ticker_info

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class PortfolioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class TickerRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=15)
    quantity: float = Field(default=1, gt=0)
    acquisition_date: date | None = None


class HoldingRequest(BaseModel):
    quantity: float = Field(gt=0)
    acquisition_date: date | None = None


class Trading212ImportRequest(BaseModel):
    api_key: str = Field(min_length=10, max_length=500)
    api_secret: str = Field(min_length=10, max_length=500)
    environment: str = Field(default="live", pattern="^(live|demo)$")


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


def _portfolio_evolution(snapshots: list[dict]) -> list[dict]:
    series = {}
    for snapshot in snapshots:
        values = snapshot.get("evolution") or []
        if not values:
            continue
        ticker_series = pd.Series(
            {pd.Timestamp(item["date"]): float(item["close"]) for item in values},
            name=snapshot["ticker"],
        ).sort_index()
        acquisition_date = snapshot.get("acquisition_date")
        if acquisition_date:
            ticker_series = ticker_series[ticker_series.index >= pd.Timestamp(acquisition_date)]
        if ticker_series.dropna().empty:
            continue
        series[snapshot["ticker"]] = ticker_series * float(snapshot.get("quantity") or 0)
    if not series:
        return []
    frame = pd.concat(series.values(), axis=1).sort_index().ffill()
    frame.columns = list(series)
    portfolio_value = frame.sum(axis=1, min_count=1).dropna()
    if portfolio_value.empty or portfolio_value.iloc[0] == 0:
        return []
    portfolio_index = portfolio_value / portfolio_value.iloc[0] * 100
    return [
        {"date": index.strftime("%Y-%m-%d"), "index": round(float(value), 4)}
        for index, value in portfolio_index.items()
    ]


def _resolve_market_symbol(instrument: dict) -> str:
    broker_ticker = str(instrument.get("ticker") or "").strip()
    base_symbol = broker_ticker.split("_")[0].upper()
    query = instrument.get("isin") or instrument.get("name") or base_symbol
    try:
        response = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        response.raise_for_status()
        quotes = [
            item for item in response.json().get("quotes", [])
            if item.get("quoteType") in {"EQUITY", "ETF"} and item.get("symbol")
        ]
        preferred = next((item for item in quotes if str(item["symbol"]).upper().split(".")[0] == base_symbol), None)
        if preferred:
            return str(preferred["symbol"]).upper()
        if quotes:
            return str(quotes[0]["symbol"]).upper()
    except Exception:
        pass
    return base_symbol


def _trading212_positions(api_key: str, api_secret: str, environment: str) -> list[dict]:
    base_url = "https://live.trading212.com" if environment == "live" else "https://demo.trading212.com"
    response = requests.get(
        f"{base_url}/api/v0/equity/positions",
        auth=(api_key, api_secret),
        headers={"Accept": "application/json"},
        timeout=25,
    )
    if response.status_code in {401, 403}:
        raise ValueError("Trading 212 rejected API credentials or portfolio permission.")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Trading 212 returned an unexpected positions response.")
    return payload


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
        portfolio = add_ticker(
            _user_id(request),
            portfolio_id,
            body.ticker,
            body.quantity,
            body.acquisition_date.isoformat() if body.acquisition_date else None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Ticker could not be validated: {exc}") from exc
    if not portfolio:
        raise HTTPException(404, "Portfolio not found.")
    return {"portfolio": portfolio}


@router.patch("/{portfolio_id}/tickers/{ticker}")
@limiter.limit("30/minute")
def edit_holding(request: Request, portfolio_id: int, ticker: str, body: HoldingRequest):
    try:
        portfolio = update_holding(
            _user_id(request),
            portfolio_id,
            ticker,
            body.quantity,
            body.acquisition_date.isoformat() if body.acquisition_date else None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not portfolio:
        raise HTTPException(404, "Portfolio not found.")
    return {"portfolio": portfolio}


@router.post("/{portfolio_id}/import/trading212")
@limiter.limit("5/minute")
def import_trading212(request: Request, portfolio_id: int, body: Trading212ImportRequest):
    user_id = _user_id(request)
    if not get_portfolio(user_id, portfolio_id):
        raise HTTPException(404, "Portfolio not found.")
    try:
        positions = _trading212_positions(body.api_key, body.api_secret, body.environment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(502, f"Trading 212 API unavailable: {exc}") from exc

    imported = []
    errors = []
    for position in positions:
        try:
            quantity = float(position.get("quantity") or 0)
            if quantity <= 0:
                continue
            ticker = _resolve_market_symbol(position.get("instrument") or {})
            created_at = str(position.get("createdAt") or "")[:10] or None
            add_ticker(user_id, portfolio_id, ticker, quantity, created_at)
            imported.append({"ticker": ticker, "quantity": quantity, "acquisition_date": created_at})
        except Exception as exc:
            errors.append({"broker_ticker": (position.get("instrument") or {}).get("ticker"), "error": str(exc)})
    return {
        "portfolio": get_portfolio(user_id, portfolio_id),
        "imported": imported,
        "errors": errors,
        "credentials_stored": False,
    }


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
    holdings = {item["ticker"]: item for item in portfolio["holdings"]}
    for ticker in portfolio["tickers"]:
        try:
            snapshots.append({**_ticker_snapshot(ticker), **holdings[ticker]})
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})
    return {
        "portfolio": portfolio,
        "tickers": snapshots,
        "portfolio_evolution": _portfolio_evolution(snapshots),
        "evolution_method": "Quantity-weighted market value, starting from each acquisition date; portfolio indexed to 100.",
        "errors": errors,
    }

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
