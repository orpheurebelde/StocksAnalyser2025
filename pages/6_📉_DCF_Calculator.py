import streamlit as st
import yfinance as yf
import numpy as np
from utils.utils import load_stock_list, get_stock_info
import time
import datetime

st.set_page_config(page_title="DCF Calculator", layout="wide")
st.title("Discounted Cash Flow (DCF) Calculator")

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

        col1, col2 = st.columns(2)
        with col1:
            base_growth_rate = st.number_input(
                "📈 Estimated Annual Company Growth (%)",
                value=10.0,
                step=0.5,
                min_value=0.1,
                max_value=100.0  # changed to float
            ) / 100
        with col2:
            base_discount_rate = st.number_input(
                "💸 Discount Rate (%)",
                value=10.0,
                step=0.5,
                min_value=6.0,
                max_value=15.0,  # ensure float, here 15.0 is fine since it has decimal
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

        growth_multipliers = {"Base": 1.0, "Bull": 1.5, "Bear": 0.5}
        discount_multipliers = {"Base": 1.0, "Bull": 0.85, "Bear": 1.2}

        growth_rate = base_growth_rate * growth_multipliers[scenario]
        discount_rate = base_discount_rate * discount_multipliers[scenario]

        if not eps_ttm or eps_ttm <= 0 or not pe_ratio or pe_ratio <= 0:
            st.warning("⚠️ EPS or PE ratio is invalid. Using revenue-based fallback DCF model.")

            revenue_ttm = info.get("totalRevenue", None)

            if not revenue_ttm or revenue_ttm <= 0:
                st.error("❌ Revenue data not available to perform fallback DCF.")
            else:
                with st.expander("⚙️ Adjust P/S Growth Factor"):
                    ps_factor = st.slider("P/S Growth Factor", min_value=0.1, max_value=1.0, value=0.6, step=0.05)

                estimated_ps_ratio = base_growth_rate * 100 * ps_factor
                st.markdown(f"🔢 Auto-calculated P/S Ratio based on growth: **{estimated_ps_ratio:.2f}**")

                projected_revenue = [revenue_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
                projected_market_cap = [rev * estimated_ps_ratio for rev in projected_revenue]

                future_value = projected_market_cap[-1]
                present_value = future_value / ((1 + discount_rate) ** years)
                fair_value_per_share = present_value / shares_outstanding

                pv_color = "green" if future_value > market_cap else "red"
                valuation_vs_price = "🟢 Undervalued" if fair_value_per_share > current_price else "🔴 Overvalued"

                with st.expander("📈 Company Valuation Projection (5 Years)", expanded=True):
                    st.markdown(f"""
                        <div style='padding: 10px; background-color: transparent; font-size: 18px; border-radius: 10px; border: 1px solid #ccc;'>
                            <p><strong>Current Market Cap:</strong> {format_currency(market_cap)}</p>
                            <p><strong>Future Company Value:</strong> {format_currency(future_value)}</p>
                            <p><strong>Discounted Present Value:</strong> 
                                <span style='color: {pv_color}; font-weight: bold;'>{format_currency(present_value)}</span>
                            </p>
                            <p><strong>Fair Value Per Share (Today):</strong> {format_currency_dec(fair_value_per_share)}</p>
                            <p><strong>Compared to Current Price ({format_currency_dec(current_price)}):</strong> {valuation_vs_price}</p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.markdown("<div style='margin-bottom: 10px;'>&nbsp;</div>", unsafe_allow_html=True)

        else:
            projected_eps = [eps_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
            projected_pe = [pe_ratio * (0.95 ** i) for i in range(years)]

            projected_stock_price = [eps * pe for eps, pe in zip(projected_eps, projected_pe)]
            projected_market_cap = [price * shares_outstanding for price in projected_stock_price]

            future_value = projected_market_cap[-1]
            present_value = future_value / ((1 + discount_rate) ** years)
            fair_value_per_share = present_value / shares_outstanding

            pv_color = "green" if future_value > market_cap else "red"
            valuation_vs_price = "🟢 Undervalued" if fair_value_per_share > current_price else "🔴 Overvalued"

            with st.expander("📈 Company Valuation Projection (5 Years)", expanded=True):
                st.markdown(f"""
                <div style='padding: 10px; background-color: transparent; font-size: 18px; border-radius: 10px; border: 1px solid #ccc;'>
                    <p><strong>Current Market Cap:</strong> {format_currency(market_cap)}</p>
                    <p><strong>Future Company Value:</strong> {format_currency(future_value)}</p>
                    <p><strong>Discounted Present Value:</strong> 
                        <span style='color: {pv_color}; font-weight: bold;'>{format_currency(present_value)}</span>
                    </p>
                    <p><strong>Fair Value Per Share (Today):</strong> {format_currency_dec(fair_value_per_share)}</p>
                    <p><strong>Compared to Current Price ({format_currency_dec(current_price)}):</strong> {valuation_vs_price}</p>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<div style='margin-bottom: 10px;'>&nbsp;</div>", unsafe_allow_html=True)

            header_style = "text-align: center;font-weight: bold;font-size: 18px;color: white;margin-bottom: 10px;"
            projection_box_style = (
                "border: 2px solid #FFA500;padding: 12px;border-radius: 12px;"
                "text-align: center;margin-bottom: 12px;color: white;font-size: 18px;"
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