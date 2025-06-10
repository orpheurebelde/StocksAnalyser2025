import streamlit as st 
import pandas as pd
from utils.utils import get_stock_price_yf
from datetime import datetime

st.set_page_config(page_title="📊 Portfolio Analysis", layout="wide")

st.title("📊 Portfolio Analysis & AI Suggestions")

# Upload CSV
uploaded_file = st.file_uploader("📁 Upload Portfolio CSV", type=["csv"])

if uploaded_file:
    # Read CSV while skipping bad lines
    df = pd.read_csv(uploaded_file, parse_dates=["Date"], dayfirst=True, on_bad_lines='skip')

    # Clean up column names
    df.columns = [col.strip() for col in df.columns]

    # Debug: show column names to help identify issues
    st.write("Columns found in CSV:", list(df.columns))

    # Check required columns (with Symbol instead of Ticker)
    required_cols = {"Date", "Symbol", "Quantity", "Purchase Price", "Transaction Type"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        st.error(f"Missing required columns in CSV: {missing_cols}")
    else:
        # Strip suffixes like '.DE' from symbols
        df["Symbol"] = df["Symbol"].str.upper().str.split('.').str[0]

        # Add Current Price using yfinance
        tickers = df["Symbol"].unique()
        current_prices = {ticker: get_stock_price_yf(ticker) for ticker in tickers}
        df["Current Price"] = df["Symbol"].map(current_prices)

        # Unrealized Gain/Loss Calculation
        df["Investment"] = df["Quantity"] * df["Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain"] = df["Market Value"] - df["Investment"]

        # Separate Buy and Sell to compute Realized Gains
        buys = df[df["Transaction Type"].str.lower() == "buy"]
        sells = df[df["Transaction Type"].str.lower() == "sell"]

        # Grouped Summary per Symbol
        summary = df.groupby("Symbol").agg({
            "Quantity": "sum",
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain": "sum"
        }).reset_index()

        st.subheader("📌 Compiled Stock Summary")
        st.dataframe(summary, use_container_width=True)

        st.subheader("📄 Line-by-Line Transactions")
        st.dataframe(df.sort_values(by="Date"), use_container_width=True)

        # Realized Gain Estimation (naive method)
        realized = sells.copy()
        realized["Realized Gain"] = (sells["Purchase Price"] - buys.groupby("Symbol")["Purchase Price"].transform("mean")) * sells["Quantity"]

        if not realized.empty:
            st.subheader("💰 Realized Gains")
            st.dataframe(realized[["Date", "Symbol", "Quantity", "Purchase Price", "Realized Gain"]], use_container_width=True)

        # Annual Performance Summary
        df["Year"] = df["Date"].dt.year
        annual_summary = df.groupby(["Symbol", "Year"]).agg({
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain": "sum"
        }).reset_index()

        st.subheader("📈 Annual Performance")
        st.dataframe(annual_summary, use_container_width=True)

        # AI Analysis Trigger
        if st.button("🤖 Run AI Portfolio Analysis"):
            with st.spinner("Sending portfolio to Mistral AI..."):
                user_prompt = (
                    f"Analyze this portfolio:\n\n{summary.to_string(index=False)}\n\n"
                    "Suggest rebalancing and improvements using Modern Portfolio Theory."
                )
                # Replace this with real AI call
                ai_response = "✅ Based on current metrics, you might consider rebalancing away from overexposed tech stocks..."
                st.success("AI analysis complete.")
                st.markdown(f"**AI Suggestion:**\n\n{ai_response}")