import streamlit as st 
import pandas as pd
from datetime import datetime
import numpy as np
from tradingview_ta import TA_Handler, Interval
import yfinance as yf

st.set_page_config(page_title="📊 Portfolio Analysis", layout="wide")
st.title("📊 Portfolio Analysis & AI Suggestions")

uploaded_file = st.file_uploader("📁 Upload Portfolio CSV", type=["csv"])

# ===== Exchange detection =====
exchange_map = {
    'gettex': ('GETTEX', 'europe'),
    'xetra': ('XETR', 'europe'),
    'nasdaq': ('NASDAQ', 'america'),
    'nyse': ('NYSE', 'america'),
    'ams': ('EURONEXT', 'europe'),
    'par': ('EURONEXT', 'europe'),
}

def detect_exchange(symbol):
    """Detect GETTEX, NASDAQ, NYSE automatically using tradingview_ta."""
    exchanges = [
        ("GETTEX", "europe"),
        ("NASDAQ", "america"),
        ("NYSE", "america")
    ]
    
    for exchange, screener in exchanges:
        try:
            handler = TA_Handler(
                symbol=symbol,
                screener=screener,
                exchange=exchange,
                interval=Interval.INTERVAL_1_DAY
            )
            # Attempt to get analysis
            analysis = handler.get_analysis()
            # If it works without exception, symbol is valid
            if analysis:
                return exchange, screener
        except Exception:
            continue
    return None, None

# ===== Main logic =====
if uploaded_file:
    df = pd.read_csv(uploaded_file, parse_dates=["Date"], dayfirst=True, on_bad_lines='skip')
    df.columns = [col.strip() for col in df.columns]

    st.write("🧩 Columns detected in CSV:", list(df.columns))

    required_cols = {"Date", "Symbol", "Quantity", "Purchase Price", "Current Price"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        st.error(f"Missing required columns in CSV: {missing_cols}")
    else:
        df["Symbol"] = df["Symbol"].str.upper().str.split('.').str[0]
        df["Investment"] = df["Quantity"] * df["Purchase Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain (€)"] = df["Market Value"] - df["Investment"]
        df["Unrealized Gain (%)"] = (df["Unrealized Gain (€)"] / df["Investment"]) * 100
        df["Year"] = df["Date"].dt.year

        # 1. Transactions Table
        with st.expander("📄 Line-by-Line Transactions"):
            st.dataframe(
                df.sort_values(by="Date"),
                use_container_width=True,
                column_config={
                    "Purchase Price": st.column_config.NumberColumn("Purchase Price (€)", format="€%.2f"),
                    "Current Price": st.column_config.NumberColumn("Current Price (€)", format="€%.2f"),
                    "Investment": st.column_config.NumberColumn("Investment (€)", format="€%.2f"),
                    "Market Value": st.column_config.NumberColumn("Market Value (€)", format="€%.2f"),
                    "Unrealized Gain (€)": st.column_config.NumberColumn("Unrealized Gain (€)", format="€%.2f"),
                    "Unrealized Gain (%)": st.column_config.NumberColumn("Unrealized Gain (%)", format="%.2f%%")
                }
            )

        # 2. Stock Summary Table
        summary = df.groupby("Symbol").agg({
            "Quantity": "sum",
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        summary["Unrealized Gain (%)"] = (summary["Unrealized Gain (€)"] / summary["Investment"]) * 100

        with st.expander("📌 Compiled Stock Summary"):
            st.dataframe(
                summary,
                use_container_width=True,
                column_config={
                    "Investment": st.column_config.NumberColumn("Investment (€)", format="€%.2f"),
                    "Market Value": st.column_config.NumberColumn("Market Value (€)", format="€%.2f"),
                    "Unrealized Gain (€)": st.column_config.NumberColumn("Unrealized Gain (€)", format="€%.2f"),
                    "Unrealized Gain (%)": st.column_config.NumberColumn("Unrealized Gain (%)", format="%.2f%%")
                }
            )

        # 3. Annual Performance Summary
        annual = df.groupby("Year").agg({
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        annual["Unrealized Gain (%)"] = (annual["Unrealized Gain (€)"] / annual["Investment"]) * 100

        with st.expander("📅 Annual Unrealized Performance Summary", expanded=True):
            st.dataframe(
                annual.rename(columns={
                    "Investment": "Investment (€)",
                    "Market Value": "Market Value (€)"
                }),
                use_container_width=True,
                column_config={
                    "Investment (€)": st.column_config.NumberColumn("Investment (€)", format="€%.2f"),
                    "Market Value (€)": st.column_config.NumberColumn("Market Value (€)", format="€%.2f"),
                    "Unrealized Gain (€)": st.column_config.NumberColumn("Unrealized Gain (€)", format="€%.2f"),
                    "Unrealized Gain (%)": st.column_config.NumberColumn("Unrealized Gain (%)", format="%.2f%%")
                }
            )

        # 4. TradingView Historical Data Metrics
        with st.expander("📊 Portfolio Metrics via TradingView Historical Data", expanded=False):
            try:
                st.info("Fetching historical prices from TradingView...")
                tickers = df["Symbol"].unique()
                price_history = {}

                for t in tickers:
                    exchange, screener = detect_exchange(t)
                    if not exchange:
                        st.warning(f"Symbol {t} not found on GETTEX, NASDAQ, or NYSE.")
                        continue

                    # Build same POST request for historical data
                    hist_url = f"https://scanner.tradingview.com/{screener}/scan"
                    payload = {
                        "symbols": {"tickers": [f"{exchange}:{t}"], "query": {"types": []}},
                        "columns": ["close", "time"]
                    }
                    r = requests.post(hist_url, json=payload, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        if "data" in data and len(data["data"]) > 0:
                            # Example adaptation for price history: need real historical source here
                            closes = [row["d"][0] for row in data["data"]]
                            times = pd.date_range(end=datetime.today(), periods=len(closes))
                            df_hist = pd.DataFrame({"time": times, "close": closes}).set_index("time")
                            price_history[t] = df_hist["close"]

                if price_history:
                    all_dates = pd.Index(sorted(set().union(*[s.index for s in price_history.values()])))
                    portfolio_df = pd.DataFrame(index=all_dates)

                    for _, row in df.iterrows():
                        sym = row["Symbol"]
                        qty = row["Quantity"]
                        if sym in price_history:
                            s = price_history[sym].reindex(all_dates).ffill() * qty
                            portfolio_df[sym] = s

                    portfolio_df["Total"] = portfolio_df.sum(axis=1)

                    # Portfolio metrics
                    rets = portfolio_df["Total"].pct_change().dropna()
                    port_cagr = (portfolio_df["Total"].iloc[-1] / portfolio_df["Total"].iloc[0]) ** (252 / len(rets)) - 1
                    port_vol = rets.std() * np.sqrt(252)
                    rf = 0.0
                    port_sharpe = (port_cagr - rf) / port_vol if port_vol != 0 else np.nan
                    port_dd = (portfolio_df["Total"] / portfolio_df["Total"].cummax() - 1).min()

                    metrics_df = pd.DataFrame({
                        "Metric": ["CAGR", "Annualized Volatility", "Sharpe Ratio", "Max Drawdown"],
                        "Value": [port_cagr, port_vol, port_sharpe, port_dd]
                    })
                    st.dataframe(metrics_df, use_container_width=True)

                else:
                    st.warning("No historical price data retrieved.")

            except Exception as e:
                st.error(f"⚠️ Error fetching TradingView data: {e}")