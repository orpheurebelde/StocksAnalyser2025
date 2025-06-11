import streamlit as st
import yfinance as yf
import numpy as np
from utils import load_stock_list, get_stock_info  # Assuming these are in your utils.py

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
        eps = info.get("trailingEps", None)
        pe_ratio = info.get("trailingPE", None)
        current_price = info.get("currentPrice", None)

        if not eps or not current_price:
            st.error("❌ EPS or current price not available for this stock.")
        else:
            st.markdown(f"**Current EPS (TTM):** {format_currency_dec(eps)}")
            st.markdown(f"**Current P/E Ratio:** {format_ratio(pe_ratio)}" if pe_ratio else "**P/E Ratio:** Not available")
            st.markdown(f"**Current Stock Price:** {format_currency_dec(current_price)}")

            col1, col2 = st.columns(2)
            with col1:
                growth_rate = st.number_input("📈 Estimated Annual EPS Growth (%)", value=10.0, step=0.5)
            with col2:
                discount_rate = st.number_input("💸 Discount Rate (%)", value=10.0, step=0.5)

            # Convert to decimals
            growth_rate /= 100
            discount_rate /= 100

            # Calculate 5-year projections
            projected_eps = [eps * ((1 + growth_rate) ** i) for i in range(1, 6)]
            present_values = [eps_year / ((1 + discount_rate) ** i) for i, eps_year in enumerate(projected_eps, 1)]

            terminal_value = projected_eps[-1] * (1 + growth_rate) / (discount_rate - growth_rate)
            terminal_value_pv = terminal_value / ((1 + discount_rate) ** 5)

            fair_value = sum(present_values) + terminal_value_pv

            # EPS Forecast Table
            st.markdown("### 📊 5-Year EPS Forecast")
            st.table({
                "Year": [f"Year {i}" for i in range(1, 6)],
                "Projected EPS": [format_currency_dec(e) for e in projected_eps],
                "Present Value": [format_currency_dec(pv) for pv in present_values]
            })

            # Final DCF Result
            st.markdown("---")
            st.subheader("💰 Final DCF Estimate")
            st.write(f"**Terminal Value (after 5 years):** {format_currency(terminal_value)}")
            st.write(f"**Present Value of Terminal Value:** {format_currency(terminal_value_pv)}")
            st.write(f"**Estimated Fair Value Per Share:** {format_currency_dec(fair_value)}")
            comparison = "🟢 Undervalued" if fair_value > current_price else "🔴 Overvalued"
            st.write(f"**Compared to Current Price ({format_currency_dec(current_price)}):** {comparison}")

    except Exception as e:
        st.error("⚠️ Error while calculating DCF.")
        st.exception(e)