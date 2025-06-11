import streamlit as st
import yfinance as yf
import numpy as np
from utils.utils import load_stock_list, get_stock_info  # Assuming these are in your utils.py

st.set_page_config(page_title="📉 DCF Calculator", layout="centered")
st.title("📉 Discounted Cash Flow (DCF) Calculator")

# Load and display stock selector
stock_df = load_stock_list()
stock_df = stock_df.sort_values(by="Display")
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

# Formatting helpers
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_percent(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"
def format_ratio(val): return f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"

if selected_display != "Select a stock...":
    ticker = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    info = get_stock_info(ticker)

    try:
        market_cap = info.get("marketCap", None)
        shares_outstanding = info.get("sharesOutstanding", None)
        current_price = info.get("currentPrice", None)

        if not market_cap or not shares_outstanding:
            st.error("❌ Market Cap or Shares Outstanding not available.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                growth_rate = st.number_input("📈 Estimated Annual Company Growth (%)", value=10.0, step=0.5)
            with col2:
                discount_rate = st.number_input("💸 Discount Rate (%)", value=10.0, step=0.5)

            # Convert to decimals
            growth_rate /= 100
            discount_rate /= 100
            years = 5

            # Future and Present Value Estimation
            future_value = market_cap * ((1 + growth_rate) ** years)
            present_value = future_value / ((1 + discount_rate) ** years)
            fair_value_per_share = present_value / shares_outstanding

            st.markdown("### 📈 Company Valuation Projection (5 Years)")
            st.write(f"**Current Market Cap:** {format_currency(market_cap)}")
            st.write(f"**Future Company Value:** {format_currency(future_value)}")
            st.write(f"**Discounted Present Value:** {format_currency(present_value)}")
            st.write(f"**Fair Value Per Share (Today):** {format_currency_dec(fair_value_per_share)}")

            comparison = "🟢 Undervalued" if fair_value_per_share > current_price else "🔴 Overvalued"
            st.write(f"**Compared to Current Price ({format_currency_dec(current_price)}):** {comparison}")

    except Exception as e:
        st.error("⚠️ Error while calculating DCF.")
        st.exception(e)