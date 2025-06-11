import streamlit as st
import yfinance as yf
import numpy as np
from utils.utils import load_stock_list, get_stock_info
import time

st.set_page_config(page_title="📉 DCF Calculator", layout="wide")
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
        eps_ttm = info.get("trailingEps", None)
        pe_ratio = info.get("trailingPE", None)

        if not market_cap or not shares_outstanding or not eps_ttm or eps_ttm <= 0:
            st.error("❌ Required financials (EPS, Market Cap, or Shares Outstanding) are missing or invalid.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                growth_rate = st.number_input("📈 Estimated Annual Company Growth (%)", value=10.0, step=0.5)
            with col2:
                discount_rate = st.number_input(
                    "💸 Discount Rate (%)",
                    value=10.0,
                    step=0.5,
                    min_value=6.0,
                    max_value=15.0,
                    help=(
                        "Suggested Discount Rates by Company Risk:\n"
                        "• Low-risk (e.g., Apple, MSFT): 6% – 8%\n"
                        "• Medium-risk (e.g., large growth companies): 8% – 10%\n"
                        "• High-risk (e.g., small-cap, tech startups): 10% – 15%"
                    )
                )

            # Convert to decimals
            growth_rate /= 100
            discount_rate /= 100
            years = 5

            # EPS and PE Projections
            projected_eps = [eps_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
            projected_pe = [pe_ratio * (0.9 ** i) for i in range(years)]  # Conservative PE compression
            projected_stock_price = [eps * pe for eps, pe in zip(projected_eps, projected_pe)]
            projected_market_cap = [price * shares_outstanding for price in projected_stock_price]

            # Future and Present Value Estimation
            future_value = projected_market_cap[-1]
            present_value = future_value / ((1 + discount_rate) ** years)
            fair_value_per_share = present_value / shares_outstanding

            # ⬇️ Valuation Summary
            with st.expander("📈 Company Valuation Projection (5 Years)", expanded=True):
                st.write(f"**Current Market Cap:** {format_currency(market_cap)}")
                st.write(f"**Future Company Value:** {format_currency(future_value)}")
                st.write(f"**Discounted Present Value:** {format_currency(present_value)}")
                st.write(f"**Fair Value Per Share (Today):** {format_currency_dec(fair_value_per_share)}")

                comparison = "🟢 Undervalued" if fair_value_per_share > current_price else "🔴 Overvalued"
                st.write(f"**Compared to Current Price ({format_currency_dec(current_price)}):** {comparison}")

            # ⬇️ Detailed 5-Year DCF Projection
            # Scenario selector
            scenario = st.selectbox(
                "Choose Projection Scenario",
                ["Base", "Bull", "Bear"],
                index=0,
                help="Select different projection scenarios."
            )

            # Modify growth_rate and discount_rate based on scenario (example)
            growth_multipliers = {"Base": 1.0, "Bull": 1.2, "Bear": 0.8}
            discount_multipliers = {"Base": 1.0, "Bull": 0.9, "Bear": 1.1}

            # Example base rates (you would have them set from inputs)
            base_growth_rate = 0.10
            base_discount_rate = 0.10

            growth_rate = base_growth_rate * growth_multipliers[scenario]
            discount_rate = base_discount_rate * discount_multipliers[scenario]

            # Dummy projected data generation (replace with your actual calculation)
            years = 5
            projected_eps = [1.0 * (1 + growth_rate) ** i for i in range(1, years + 1)]
            projected_pe = [15 * (1 - 0.05 * i) for i in range(years)]  # just example declining PE
            projected_stock_price = [eps * pe for eps, pe in zip(projected_eps, projected_pe)]
            projected_market_cap = [price * 1e8 for price in projected_stock_price]  # example cap

            # Styling
            # Updated styles
            header_style = (
                "text-align: center;"
                "font-weight: bold;"
                "font-size: 18px;"
                "color: black;"
                "margin-bottom: 10px;"
            )

            projection_box_style = (
                "border: 2px solid #FFA500;"
                "padding: 12px;"
                "border-radius: 12px;"
                "text-align: center;"
                "margin-bottom: 12px;"
                "color: white;"              # White text
                "font-size: 16px;"           # Larger font size
                "font-weight: 600;"
                "background-color: rgba(255,165,0,0.15);"  # Slightly more visible transparent orange bg
            )

            metric_box_style = (
                "border: 2px solid #28a745;"
                "padding: 12px;"
                "border-radius: 15px;"
                "text-align: center;"
                "margin-bottom: 12px;"
                "color: white;"
                "font-size: 18px;"
                "font-weight: bold;"
                "background-color: rgba(40, 167, 69, 0.85);"
                "display: flex;"
                "align-items: center;"
                "justify-content: center;"
                "height: 48px;"
            )

            with st.expander("🔮 5-Year Stock Price Projection (DCF Model)", expanded=True):
                years_labels = [f"Year {i}" for i in range(1, years + 1)]
                header_cols = st.columns(6)
                header_cols[0].markdown(f"<div style='{header_style}'>Metric</div>", unsafe_allow_html=True)
                for i, year in enumerate(years_labels):
                    header_cols[i + 1].markdown(f"<div style='{header_style}'>{year}</div>", unsafe_allow_html=True)

                metrics = ["EPS", "PE Ratio", "Stock Price", "Market Cap"]
                rows = {
                    "EPS": projected_eps,
                    "PE Ratio": projected_pe,
                    "Stock Price": projected_stock_price,
                    "Market Cap": projected_market_cap
                }

                for metric in metrics:
                    row_cols = st.columns(6)
                    # Metric label column with green rounded box and white text
                    row_cols[0].markdown(
                        f"<div style='{metric_box_style}'>{metric}</div>", unsafe_allow_html=True
                    )
                    # Projection data columns with orange border boxes
                    for i in range(years):
                        val = rows[metric][i]
                        if metric == "PE Ratio":
                            fmt = f"{val:.2f}"
                        elif metric == "EPS" or metric == "Stock Price":
                            fmt = f"${val:,.2f}"
                        else:
                            fmt = f"${val:,.0f}"

                        row_cols[i + 1].markdown(
                            f"<div style='{projection_box_style}'>{fmt}</div>", unsafe_allow_html=True
                        )

            # Optionally add a little animation (simulate loading)
            with st.spinner("Updating projections based on scenario..."):
                time.sleep(0.5)
                
    except Exception as e:
        st.error("⚠️ Error while calculating DCF.")
        st.exception(e)