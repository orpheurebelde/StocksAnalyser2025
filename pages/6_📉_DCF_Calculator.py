import streamlit as st
import yfinance as yf
import numpy as np
import time
import datetime

st.set_page_config(page_title="DCF Calculator", layout="wide")
st.title("Discounted Cash Flow (DCF) Calculator")

# Helpers for formatting
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"

# Load your stock list function here or replace with your own
# from utils.utils import load_stock_list, get_stock_info
# For demo purposes, let's simulate:
def load_stock_list():
    return st.session_state.get("stock_df", None) or st.experimental_data_editor({"Display": ["Apple - AAPL", "Meta - META"], "Ticker": ["AAPL", "META"]})

def get_stock_info(ticker):
    stock = yf.Ticker(ticker)
    return stock.info

# UI: Stock selector
stock_df = load_stock_list()
if stock_df is None or len(stock_df) == 0:
    st.error("Stock list not loaded.")
    st.stop()

stock_df = stock_df.sort_values(by="Display")
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

if selected_display != "Select a stock...":
    ticker = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    info = get_stock_info(ticker)

    try:
        # Extract key data
        market_cap = info.get("marketCap")
        shares_outstanding = info.get("sharesOutstanding")
        current_price = info.get("currentPrice")
        eps_ttm = info.get("trailingEps")
        pe_ratio = info.get("trailingPE")
        revenue_ttm = info.get("totalRevenue")
        total_debt = info.get("totalDebt", 0) or 0
        total_cash = info.get("totalCash", 0) or 0

        # Inputs
        col1, col2 = st.columns(2)
        with col1:
            base_growth_rate = st.number_input("📈 Estimated Annual Company Growth (%)", value=10.0, step=0.5, min_value=0.1, max_value=100) / 100
        with col2:
            base_discount_rate = st.number_input(
                "💸 Discount Rate (%)",
                value=10.0,
                step=0.5,
                min_value=6.0,
                max_value=20.0,
                help=(
                    "Suggested Discount Rates by Company Risk:\n"
                    "• Low-risk (e.g., Apple, MSFT): 6% – 8%\n"
                    "• Medium-risk (e.g., large growth companies): 8% – 10%\n"
                    "• High-risk (e.g., small-cap, tech startups): 10% – 20%"
                )
            ) / 100

        years = 5
        terminal_growth_rate = 0.025  # 2.5% long-term growth

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

        def discount_cash_flows(cash_flows, discount_rate):
            return sum([cf / ((1 + discount_rate) ** (i + 1)) for i, cf in enumerate(cash_flows)])

        # Try EPS/PE valuation if valid
        if eps_ttm and eps_ttm > 0 and pe_ratio and pe_ratio > 0:
            projected_eps = [eps_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
            # PE usually contracts slightly as company matures
            projected_pe = [pe_ratio * (0.95 ** i) for i in range(years)]
            projected_stock_prices = [eps * pe for eps, pe in zip(projected_eps, projected_pe)]
            projected_market_caps = [price * shares_outstanding for price in projected_stock_prices]

            # Discount projected market caps
            discounted_market_caps = [mc / ((1 + discount_rate) ** (i + 1)) for i, mc in enumerate(projected_market_caps)]

            # Terminal value calculation
            terminal_value = projected_market_caps[-1] * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
            discounted_terminal_value = terminal_value / ((1 + discount_rate) ** years)

            present_value = sum(discounted_market_caps) + discounted_terminal_value

            # Adjust for net debt
            net_debt = total_debt - total_cash
            equity_value = present_value - net_debt

            fair_value_per_share = equity_value / shares_outstanding

        else:
            # Fallback to revenue / P-S ratio model
            if not revenue_ttm or revenue_ttm <= 0:
                st.error("❌ Revenue data not available to perform fallback DCF.")
                st.stop()

            with st.expander("⚙️ Adjust P/S Growth Factor"):
                ps_factor = st.slider("P/S Growth Factor", min_value=0.1, max_value=1.0, value=0.6, step=0.05)

            estimated_ps_ratio = base_growth_rate * 100 * ps_factor
            st.markdown(f"🔢 Auto-calculated P/S Ratio based on growth: **{estimated_ps_ratio:.2f}**")

            projected_revenue = [revenue_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
            projected_market_caps = [rev * estimated_ps_ratio for rev in projected_revenue]

            # Discount projected market caps
            discounted_market_caps = [mc / ((1 + discount_rate) ** (i + 1)) for i, mc in enumerate(projected_market_caps)]

            # Terminal value
            terminal_value = projected_market_caps[-1] * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
            discounted_terminal_value = terminal_value / ((1 + discount_rate) ** years)

            present_value = sum(discounted_market_caps) + discounted_terminal_value

            net_debt = total_debt - total_cash
            equity_value = present_value - net_debt

            fair_value_per_share = equity_value / shares_outstanding

        # Valuation comparison
        undervalued = fair_value_per_share > current_price
        valuation_diff_pct = ((fair_value_per_share - current_price) / current_price) * 100

        # Color for valuation
        pv_color = "green" if undervalued else "red"
        valuation_vs_price = "🟢 Undervalued" if undervalued else "🔴 Overvalued"

        # Output valuation summary
        with st.expander("📈 Company Valuation Projection (5 Years)", expanded=True):
            st.markdown(f"""
                <div style='padding: 10px; font-size: 18px; border-radius: 10px; border: 1px solid #ccc;'>
                    <p><strong>Current Market Cap:</strong> {format_currency(market_cap)}</p>
                    <p><strong>Future Company Value (Year {years}):</strong> {format_currency(projected_market_caps[-1])}</p>
                    <p><strong>Discounted Present Value (incl. Terminal):</strong> 
                        <span style='color: {pv_color}; font-weight: bold;'>{format_currency(present_value)}</span>
                    </p>
                    <p><strong>Net Debt:</strong> {format_currency(net_debt)}</p>
                    <p><strong>Equity Value (after debt):</strong> {format_currency(equity_value)}</p>
                    <p><strong>Fair Value Per Share (Today):</strong> {format_currency_dec(fair_value_per_share)}</p>
                    <p><strong>Current Price:</strong> {format_currency_dec(current_price)}</p>
                    <p><strong>Valuation vs Current Price:</strong> {valuation_vs_price} ({valuation_diff_pct:.1f}%)</p>
                </div>
            """, unsafe_allow_html=True)

        # Show detailed 5-year projections table (EPS/PE or Revenue/P-S)
        header_style = "text-align: center;font-weight: bold;font-size: 18px;color: black;margin-bottom: 10px;"
        projection_box_style = (
            "border: 2px solid #FFA500;padding: 12px;border-radius: 12px;"
            "text-align: center;margin-bottom: 12px;color: black;font-size: 18px;"
            "font-weight: 600;background-color: rgba(255,165,0,0.15);"
        )
        metric_box_style = (
            "border: 2px solid #28a745;padding: 12px;border-radius: 15px;text-align: center;"
            "margin-bottom: 12px;color: black;font-size: 18px;font-weight: bold;"
            "background-color: rgba(40, 167, 69, 0.85);display: flex;align-items: center;"
            "justify-content: center;height: 48px;"
        )

        with st.expander("🔮 5-Year Stock Price Projection (DCF Model)", expanded=True):
            start_year = datetime.datetime.now().year + 1
            years_labels = [str(start_year + i) for i in range(years)]
            header_cols = st.columns(years + 1)
            header_cols[0].markdown(f"<div style='{header_style}'>Metric</div>", unsafe_allow_html=True)
            for i, year in enumerate(years_labels):
                header_cols[i + 1].markdown(f"<div style='{header_style}'>{year}</div>", unsafe_allow_html=True)

            if eps_ttm and eps_ttm > 0 and pe_ratio and pe_ratio > 0:
                metrics = ["EPS", "PE Ratio", "Stock Price", "Market Cap"]
                projected_pe = [pe_ratio * (0.95 ** i) for i in range(years)]
                projected_eps = [eps_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
                projected_stock_price = [eps * pe for eps, pe in zip(projected_eps, projected_pe)]
                projected_market_cap = [price * shares_outstanding for price in projected_stock_price]

                rows = {
                    "EPS": projected_eps,
                    "PE Ratio": projected_pe,
                    "Stock Price": projected_stock_price,
                    "Market Cap": projected_market_cap
                }
            else:
                metrics = ["Revenue", "P/S Ratio", "Market Cap"]
                estimated_ps_ratio = base_growth_rate * 100 * st.session_state.get('ps_factor', 0.6)
                projected_revenue = [revenue_ttm * ((1 + growth_rate) ** i) for i in range(1, years + 1)]
                projected_market_cap = [rev * estimated_ps_ratio for rev in projected_revenue]

                # We don’t track changing P/S here but could be added if desired
                rows = {
                    "Revenue": projected_revenue,
                    "P/S Ratio": [estimated_ps_ratio] * years,
                    "Market Cap": projected_market_cap
                }

            for metric in metrics:
                row_cols = st.columns(years + 1)
                row_cols[0].markdown(f"<div style='{metric_box_style}'>{metric}</div>", unsafe_allow_html=True)
                for i in range(years):
                    val = rows[metric][i]
                    if metric == "P/S Ratio":
                        fmt = f"{val:.2f}"
                    elif metric in ["EPS", "Stock Price", "Revenue"]:
                        fmt = f"${val:,.2f}"
                    else:
                        fmt = f"${val:,.0f}"
                    row_cols[i + 1].markdown(f"<div style='{projection_box_style}'>{fmt}</div>", unsafe_allow_html=True)

        with st.spinner("Updating projections based on scenario..."):
            time.sleep(0.5)

    except Exception as e:
        st.error("⚠️ Error while calculating DCF.")
        st.exception(e)

else:
    st.warning("⚠️ Please select a valid stock ticker from the dropdown above to view DCF valuation.")