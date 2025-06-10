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
    df.columns = [col.strip() for col in df.columns]
    st.write("Columns found in CSV:", list(df.columns))

    # Check required columns (Symbol instead of Ticker)
    required_cols = {"Date", "Symbol", "Quantity", "Purchase Price"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        st.error(f"Missing required columns in CSV: {missing_cols}")
    else:
        # Handle missing or empty "Transaction Type"
        if "Transaction Type" not in df.columns or df["Transaction Type"].isnull().all() or df["Transaction Type"].eq("").all():
            st.warning("⚠️ 'Transaction Type' is missing or empty. Please classify each transaction.")

            user_choices = []
            for i, row in df.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{row['Date'].date()} | {row['Symbol']} | Qty: {row['Quantity']} @ {row['Purchase Price']}")
                with col2:
                    choice = st.radio(
                        f"Row {i+1}",
                        options=["Buy", "Sell"],
                        key=f"txn_type_{i}",
                        horizontal=True
                    )
                user_choices.append(choice)
            df["Transaction Type"] = user_choices

        # Clean symbol column
        df["Symbol"] = df["Symbol"].str.upper().str.split('.').str[0]

        # Add current price via yfinance
        tickers = df["Symbol"].unique()
        current_prices = {ticker: get_stock_price_yf(ticker) for ticker in tickers}
        df["Current Price"] = df["Symbol"].map(current_prices)

        # Financial calculations
        df["Investment"] = df["Quantity"] * df["Purchase Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain"] = df["Market Value"] - df["Investment"]

        # Separate Buy and Sell
        buys = df[df["Transaction Type"].str.lower() == "buy"]
        sells = df[df["Transaction Type"].str.lower() == "sell"]

        # Summary per symbol
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

        # Estimate Realized Gains (naive)
        realized = sells.copy()
        if not buys.empty and not sells.empty:
            avg_buy_prices = buys.groupby("Symbol")["Purchase Price"].transform("mean")
            realized["Realized Gain"] = (realized["Purchase Price"] - avg_buy_prices) * realized["Quantity"]

            st.subheader("💰 Realized Gains")
            st.dataframe(realized[["Date", "Symbol", "Quantity", "Purchase Price", "Realized Gain"]], use_container_width=True)

        # Annual performance
        df["Year"] = df["Date"].dt.year
        annual_summary = df.groupby(["Symbol", "Year"]).agg({
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain": "sum"
        }).reset_index()

        st.subheader("📈 Annual Performance")
        st.dataframe(annual_summary, use_container_width=True)

        # AI Trigger
        if st.button("🤖 Run AI Portfolio Analysis"):
            with st.spinner("Sending portfolio to Mistral AI..."):
                user_prompt = (
                    f"Analyze this portfolio:\n\n{summary.to_string(index=False)}\n\n"
                    "Suggest rebalancing and improvements using Modern Portfolio Theory."
                )
                # Placeholder AI logic
                ai_response = "✅ Based on current metrics, you might consider rebalancing away from overexposed tech stocks..."
                st.success("AI analysis complete.")
                st.markdown(f"**AI Suggestion:**\n\n{ai_response}")