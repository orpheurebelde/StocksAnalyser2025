import streamlit as st 
import pandas as pd
from datetime import datetime
import numpy as np
from tradingview_ta import TA_Handler, Interval
import requests

st.set_page_config(page_title="📊 Portfolio Analysis", layout="wide")
st.title("📊 Portfolio Analysis & AI Suggestions")

uploaded_file = st.file_uploader("📁 Upload Portfolio CSV", type=["csv"])

def detect_exchange(symbol):
    """Try GETTEX, NASDAQ, NYSE in order and return the matching one."""
    exchanges = [
        ("GETTEX", "europe"),
        ("NASDAQ", "america"),
        ("NYSE", "america")
    ]
    base_url = "https://www.tradingview.com/symbols/{exchange}-{symbol}/"

    for exchange, screener in exchanges:
        url = base_url.format(exchange=exchange, symbol=symbol.upper())
        resp = requests.get(url)
        if resp.status_code == 200 and "Page not found" not in resp.text:
            return exchange, screener
    return None, None


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

        # Display the portfolio summary
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

        with st.expander("💡 AI Analysis & Forecast"):
            try:
                MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]

                if st.button("🤖 Run Mistral AI Portfolio Analysis"):
                    with st.spinner("Sending portfolio summary to Mistral AI..."):
                        user_prompt = f"""
        You are a financial advisor analyzing a portfolio. Use Modern Portfolio Theory and sound portfolio management principles.

        Here is the aggregated portfolio summary:

        {summary.to_string(index=False)}

        And here is the annual performance breakdown:

        {annual.to_string(index=False)}

        Please perform the following:
        1. Identify overexposed sectors or individual stocks.
        2. Highlight diversification gaps.
        3. Suggest rebalancing strategies.
        4. Recommend ETF or stock alternatives to reduce risk and increase stability.
        5. Provide a short-term (1 year) and medium-term (3–5 years) forecast based on current asset mix.
        6. Mention any red flags like concentrated risk, declining sectors, or underperformers.

        Be concise, professional, and use bullet points.
        """

                        import requests

                        headers = {
                            "Authorization": f"Bearer {MISTRAL_API_KEY}",
                            "Content-Type": "application/json"
                        }

                        payload = {
                            "model": "mistral-small",  # or mistral-medium / mistral-large
                            "messages": [
                                {"role": "system", "content": "You are a helpful financial analyst AI."},
                                {"role": "user", "content": user_prompt}
                            ],
                            "temperature": 0.7
                        }

                        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)

                        if response.status_code == 200:
                            ai_response = response.json()["choices"][0]["message"]["content"]
                        else:
                            ai_response = f"⚠️ API Error: {response.status_code} - {response.text}"

                        st.success("AI analysis complete.")
                        st.markdown(f"**AI Suggestion:**\n\n{ai_response}")

            except Exception as e:
                st.warning("⚠️ Mistral API key not found in Streamlit secrets or another error occurred.")
                st.exception(e)

        # 4. Trading View Prices
        with st.expander("📊 Portfolio Metrics via TradingView Historical Data", expanded=False):
            try:
                st.info("Fetching historical prices from TradingView (may take a few seconds)...")
                tickers = df["Symbol"].unique()
                price_history = {}

                for t in tickers:
                    exchange, screener = detect_exchange(t)
                    if not exchange:
                        st.warning(f"Symbol {t} not found on GETTEX, NASDAQ, or NYSE.")
                        continue

                    handler = TA_Handler(
                        symbol=t,
                        screener=screener,
                        exchange=exchange,
                        interval=Interval.INTERVAL_1_DAY
                    )
                    analysis = handler.get_analysis()
                    current_price = analysis.indicators.get("close", None)

                    if current_price:
                        price_history[t] = pd.Series([current_price], index=[pd.Timestamp.today()])

                # Build simplified portfolio time series
                if price_history:
                    portfolio_value = pd.Series(0, index=[pd.Timestamp.today()])
                    for _, row in df.iterrows():
                        sym = row["Symbol"]
                        qty = row["Quantity"]
                        if sym in price_history:
                            portfolio_value += price_history[sym] * qty

                    # Calculate metrics (note: with one data point, metrics are placeholders)
                    port_return = (portfolio_value.iloc[-1] - portfolio_value.iloc[0]) / portfolio_value.iloc[0]
                    port_cagr = port_return
                    port_vol = np.nan
                    port_sharpe = np.nan
                    port_dd = np.nan

                    metrics_df = pd.DataFrame({
                        "Metric": ["Approx. Return", "CAGR", "Volatility", "Sharpe Ratio", "Max Drawdown"],
                        "Value": [port_return, port_cagr, port_vol, port_sharpe, port_dd]
                    })

                    st.dataframe(metrics_df, use_container_width=True)
                else:
                    st.warning("No price data retrieved from TradingView.")

            except Exception as e:
                st.error(f"⚠️ Error fetching TradingView data: {e}")
