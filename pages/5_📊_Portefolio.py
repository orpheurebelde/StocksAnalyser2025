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

    # Strip suffixes like '.DE' from tickers
    df["Ticker"] = df["Ticker"].str.upper().str.split('.').str[0]

    # Assume your CSV has: Date, Ticker, Quantity, Price, Type (Buy/Sell)
    st.info("✅ CSV successfully loaded. Sample data:")
    st.dataframe(df.head(), use_container_width=True)

    # Add Current Price using yfinance
    tickers = df["Ticker"].unique()
    current_prices = {ticker: get_stock_price_yf(ticker) for ticker in tickers}
    df["Current Price"] = df["Ticker"].map(current_prices)

    # Unrealized Gain/Loss Calculation
    df["Investment"] = df["Quantity"] * df["Price"]
    df["Market Value"] = df["Quantity"] * df["Current Price"]
    df["Unrealized Gain"] = df["Market Value"] - df["Investment"]

    # Separate Buy and Sell to compute Realized Gains
    buys = df[df["Type"].str.lower() == "buy"]
    sells = df[df["Type"].str.lower() == "sell"]

    # Grouped Summary per Ticker
    summary = df.groupby("Ticker").agg({
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
    realized["Realized Gain"] = (sells["Price"] - buys.groupby("Ticker")["Price"].transform("mean")) * sells["Quantity"]

    if not realized.empty:
        st.subheader("💰 Realized Gains")
        st.dataframe(realized[["Date", "Ticker", "Quantity", "Price", "Realized Gain"]], use_container_width=True)

    # Annual Performance Summary
    df["Year"] = df["Date"].dt.year
    annual_summary = df.groupby(["Ticker", "Year"]).agg({
        "Investment": "sum",
        "Market Value": "sum",
        "Unrealized Gain": "sum"
    }).reset_index()

    st.subheader("📈 Annual Performance")
    st.dataframe(annual_summary, use_container_width=True)

    # AI Analysis Trigger
    if st.button("🤖 Run AI Portfolio Analysis"):
        with st.spinner("Sending portfolio to Mistral AI..."):
            # Placeholder logic — integrate your actual mistral call
            user_prompt = (
                f"Analyze this portfolio:\n\n{summary.to_string(index=False)}\n\n"
                "Suggest rebalancing and improvements using Modern Portfolio Theory."
            )
            # Replace this with real AI call
            ai_response = "✅ Based on current metrics, you might consider rebalancing away from overexposed tech stocks..."
            st.success("AI analysis complete.")
            st.markdown(f"**AI Suggestion:**\n\n{ai_response}")