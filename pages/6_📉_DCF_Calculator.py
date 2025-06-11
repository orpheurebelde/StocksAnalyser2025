import streamlit as st
import yfinance as yf
import numpy as np
from utils.utils import load_stock_list, get_stock_info
import time
import datetime

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

        if not market_cap or not shares_outstanding or not eps_ttm or eps_ttm <= 0 or not pe_ratio:
            st.error("❌ Required financials (EPS, Market Cap, Shares Outstanding, or PE ratio) are missing or invalid.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                base_growth_rate = st.number_input("📈 Estimated Annual Company Growth (%)", value=10.0, step=0.5) / 100
            with col2:
                base_discount_rate = st.number_input(
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
                ) / 100

            years = 5

            scenario = st.selectbox(
                "Choose Projection Scenario",
                ["Base", "Bull", "Bear"],
                index=0,
                help="Select different projection scenarios."
            )

            # Improved scenario multipliers
            growth_multipliers = {"Base": 1.0, "Bull": 1.5, "Bear": 0.5}
            discount_multipliers = {"Base": 1.0, "Bull": 0.85, "Bear": 1.2}

            growth_rate = base_growth_rate * growth_multipliers[scenario]
            discount_rate = base_discount_rate * discount_multipliers[scenario]

            projected_eps = [eps_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
            projected_pe = [pe_ratio * (0.95 ** i) for i in range(years)]

            projected_stock_price = [eps * pe for eps, pe in zip(projected_eps, projected_pe)]
            projected_market_cap = [price * shares_outstanding for price in projected_stock_price]

            future_value = projected_market_cap[-1]
            present_value = future_value / ((1 + discount_rate) ** years)
            fair_value_per_share = present_value / shares_outstanding

            with st.expander("ℹ️ Why Fair Value Might Exceed Next Year’s Price"):
                st.markdown("""
                The **Fair Value Today** is calculated by discounting the company's **expected future earnings over multiple years**
                (5 in this model) to reflect what an investor should pay **right now** to receive that future value.

                However, the **Projected Stock Price for next year** is a single-point estimate based on:
                
                - Projected EPS for the year
                - A potentially shrinking PE ratio
                
                As such, it doesn't represent the full intrinsic value of the company, just how the stock may be priced by the market short-term.

                Therefore, it's normal (and not an error) for the fair value today to appear higher than next year's stock price —
                especially for companies with strong long-term growth potential or temporarily compressed valuations.

                Always use both values together to form a complete picture.
                """)

            # Comparison between Present Value and Market Cap
            pv_diff = present_value - market_cap
            pv_color = "green" if pv_diff > 0 else "red"
            valuation_vs_price = "🟢 Undervalued" if fair_value_per_share > current_price else "🔴 Overvalued"

            # Styled expander using markdown and HTML
            with st.expander("📈 Company Valuation Projection (5 Years)", expanded=True):
                st.markdown(f"""
                <div style='padding: 10px; background-color: #transparent; font-size: 20px; border-radius: 10px; border: 1px solid #ccc;'>
                    <p><strong>Current Market Cap:</strong> {format_currency(market_cap)}</p>
                    <p><strong>Future Company Value:</strong> {format_currency(future_value)}</p>
                    <p><strong>Discounted Present Value:</strong> 
                        <span style='color: {pv_color}; font-weight: bold;'>{format_currency(present_value)}</span>
                    </p>
                    <p><strong>Fair Value Per Share (Today):</strong> {format_currency_dec(fair_value_per_share)}</p>
                    <p><strong>Compared to Current Price ({format_currency_dec(current_price)}):</strong> {valuation_vs_price}</p>
                    <p>------</p>
                </div>
                """, unsafe_allow_html=True)

            # Styling
            header_style = "text-align: center;font-weight: bold;font-size: 18px;color: white;margin-bottom: 10px;"
            projection_box_style = (
                "border: 2px solid #FFA500;padding: 12px;border-radius: 12px;"
                "text-align: center;margin-bottom: 12px;color: white;font-size: 20px;"
                "font-weight: 600;background-color: rgba(255,165,0,0.15);"
            )
            metric_box_style = (
                "border: 2px solid #28a745;padding: 12px;border-radius: 15px;text-align: center;"
                "margin-bottom: 12px;color: white;font-size: 18px;font-weight: bold;"
                "background-color: rgba(40, 167, 69, 0.85);display: flex;align-items: center;"
                "justify-content: center;height: 48px;"
            )

            with st.expander("🔮 5-Year Stock Price Projection (DCF Model)", expanded=True):
                start_year = datetime.datetime.now().year + 1
                years_labels = [str(start_year + i) for i in range(5)]
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
                    row_cols[0].markdown(f"<div style='{metric_box_style}'>{metric}</div>", unsafe_allow_html=True)
                    for i in range(years):
                        val = rows[metric][i]
                        if metric == "PE Ratio":
                            fmt = f"{val:.2f}"
                        elif metric in ["EPS", "Stock Price"]:
                            fmt = f"${val:,.2f}"
                        else:
                            fmt = f"${val:,.0f}"
                        row_cols[i + 1].markdown(f"<div style='{projection_box_style}'>{fmt}</div>", unsafe_allow_html=True)

            with st.spinner("Updating projections based on scenario..."):
                time.sleep(0.5)

    except Exception as e:
        st.error("⚠️ Error while calculating DCF.")
        st.exception(e)