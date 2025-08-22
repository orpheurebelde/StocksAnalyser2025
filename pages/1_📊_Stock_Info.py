import streamlit as st
import pandas as pd
from utils.utils import interpret_dilution_extended, estimate_past_shares_outstanding, calculate_peg_ratio, load_stock_list, get_stock_info, get_ai_analysis, format_number, fetch_data, display_fundamentals_score, fetch_price_data, analyze_price_action
import re
import time
from datetime import datetime

# Current year for DCF calculations
current_year = datetime.now().year

# Page config
st.set_page_config(page_title="Finance Dashboard", layout="wide")

# Session management
SESSION_TIMEOUT_SECONDS = 3600
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "last_activity" not in st.session_state:
    st.session_state["last_activity"] = time.time()

if st.session_state["authenticated"]:
    now = time.time()
    if now - st.session_state["last_activity"] > SESSION_TIMEOUT_SECONDS:
        st.session_state["authenticated"] = False
        st.warning("Session expired.")
        st.rerun()
    else:
        st.session_state["last_activity"] = now

if not st.session_state["authenticated"]:
    st.error("Unauthorized. Please go to the home page and log in.")
    st.stop()

st.title("📁 Análise de Ações | S&P 500 e NASDAQ")

stock_df = load_stock_list()
stock_df = stock_df.sort_values(by="Display")  # Sort alphabetically by Display column
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

# Format helpers
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_percent(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"
def format_ratio(val): return f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"

def clean_ai_output(analysis: str, true_price: float) -> str:
    """
    Replaces all fabricated price mentions with the real current price.
    """
    current_price_str = f"${true_price:.2f}"
    analysis = re.sub(r"(current\s+(stock|market)?\s*price\s*[:\-]?\s*)\$[0-9]+(?:\.[0-9]{1,2})?", rf"\1{current_price_str}", analysis, flags=re.IGNORECASE)
    analysis = re.sub(r"\bprice\s*~?\s*\$[0-9]+(?:\.[0-9]{1,2})?", f"price ~ {current_price_str}", analysis)
    return analysis.strip()

if selected_display != "Select a stock...":
    ticker = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    info = get_stock_info(ticker)

    if 'error' in info:
        st.error(info['error'])
    else:
        st.subheader(f"{info.get('shortName', ticker)} ({ticker.upper()})")
        left, main, right = st.columns([0.5, 10, 0.5])
        with main:
            with st.expander("📉 Click to Expand TradingView Chart"):
                st.markdown(
                    f'<iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_1&symbol={ticker}&interval=W&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=Dark&style=2&timezone=Etc%2FGMT%2B3&hideideas=1" width="100%" height="400" frameborder="0" allowtransparency="true" scrolling="no"></iframe>',
                    unsafe_allow_html=True
                )

            with st.expander("📊 Price Action Score (RSI, Volume, Ichimoku, MACD)", expanded=True):
                st.markdown(
                    """
                    <style>
                    .custom-font {
                        font-size: 20px;  /* change to whatever size you want */
                        font-weight: bold; /* optional */
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )
                data = fetch_price_data(ticker)
                score, insights = analyze_price_action(data)

                max_score = 9  # adjust if your scoring max changes

                st.markdown(f"### 📈 Price Action Score: **{score}/{max_score}**")

                # Split explanations into two columns
                half = (len(insights) + 1) // 2
                col1_items = insights[:half]
                col2_items = insights[half:]

                col1, divider, col2 = st.columns([5, 0.05, 5])

                with col1:
                    for line in col1_items:
                        st.write(line)

                with divider:
                    st.markdown(
                        """
                        <div style="border-left:1px solid gray; height: 100%; margin: 0 10px;"></div>
                        """,
                        unsafe_allow_html=True,
                    )

                with col2:
                    for line in col2_items:
                        st.write(line)

                # Determine overall buy/hold/sell signal
                if score >= 7:
                    signal = "BUY"
                    color = "green"
                elif score >= 4:
                    signal = "HOLD"
                    color = "orange"
                else:
                    signal = "SELL"
                    color = "red"

                # Display styled valuation quality score box
                st.markdown(f"""
                    <div style='padding: 1rem; border: 2px solid {color}; border-radius: 1rem; background-color: #1e1e1e; margin-top: 1rem; margin-bottom: 1rem;'>
                        <h4 style='margin: 0 0 0.5rem 0; color: #FFFFFF;'>🔎 Price Action Quality Score</h4>
                        <span style='font-size: 48px; font-weight: bold; color: {color};'>{signal}</span>
                        <div style='font-size: 18px; color: #AAAAAA;'>({score}/{max_score} points)</div>
                    </div>
                """, unsafe_allow_html=True)

            with st.expander("🏢 Company Profile", expanded=True):
                st.write(f"**Sector:** {info.get('sector', 'N/A')}")
                st.write(f"**Industry:** {info.get('industry', 'N/A')}")
                st.write(f"**Employees:** {format_number(info.get('fullTimeEmployees'))}")
                st.write(f"**Location:** {info.get('city', '')}, {info.get('state', '')}, {info.get('country', '')}")
                st.write(f"**Website:** {info.get('website', 'N/A')}")
                st.write(f"**Description:**\n{info.get('longBusinessSummary', 'N/A')}")

            with st.expander("📈 Valuation & Fundamentals", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    #Format in Millions, Billions or Trillions Market Cap
                    def format_currency(val):
                        if isinstance(val, (int, float)):
                            if val >= 1e9:
                                return f"${val / 1e9:.2f}B"
                            elif val >= 1e6:
                                return f"${val / 1e6:.2f}M"
                            else:
                                return f"${val:,.0f}"
                        return "N/A"
                    st.metric("Market Cap", format_currency(info.get('marketCap')))
                    # Categorize with green,yellow and red Trailing P/E
                    trailing_pe = info.get("trailingPE")
                    # Define value and color
                    if trailing_pe is None:
                        color = "gray"
                        value = "N/A"
                    elif trailing_pe < 15:
                        color = "green"
                        value = f"{trailing_pe:.2f}"
                    elif 15 <= trailing_pe <= 25:
                        color = "orange"
                        value = f"{trailing_pe:.2f}"
                    else:
                        color = "red"
                        value = f"{trailing_pe:.2f}"
                    # Display like st.metric with style
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start;'>
                            <span style='font-size: 16px; color: #FFFFFF;'>Trailing P/E</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    # Categorize with green,yellow and red forward P/E
                    forward_pe = info.get("forwardPE")
                    # Define value and color
                    if forward_pe is None:
                        color = "gray"
                        value = "N/A"
                    elif forward_pe < 15:
                        color = "green"
                        value = f"{forward_pe:.2f}"
                    elif 15 <= forward_pe <= 25:
                        color = "orange"
                        value = f"{forward_pe:.2f}"
                    else:
                        color = "red"
                        value = f"{forward_pe:.2f}"
                    # Display like st.metric with style
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start;'>
                            <span style='font-size: 16px; color: #FFFFFF;'>Forward P/E</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
                with col2:
                    #Categorize with green,yellow and red PEG Ratio
                    peg_ratio = info.get("trailingPegRatio")

                    # If PEG ratio is missing or invalid, calculate manually
                    if not peg_ratio:
                        pe = info.get("forwardPE") or info.get("trailingPE")
                        eps_growth = info.get("earningsQuarterlyGrowth")
                        # You may also use your own forecast or a manual override if available
                        if eps_growth and pe:
                            # Convert to annual growth rate if you know it's quarterly
                            eps_growth_annualized = (1 + eps_growth) ** 4 - 1
                            peg_ratio = calculate_peg_ratio(pe, eps_growth_annualized * 100)
                    else:
                        # Define value and color
                        if peg_ratio is None:
                            color = "gray"
                            value = "N/A"
                        elif peg_ratio < 1:
                            color = "green"
                            value = f"{peg_ratio:.2f}"
                        elif 1 <= peg_ratio <= 2:
                            color = "orange"
                            value = f"{peg_ratio:.2f}"
                        else:
                            color = "red"
                            value = f"{peg_ratio:.2f}"
                        # Display like st.metric with style
                        st.markdown(f"""
                            <div style='display: flex; flex-direction: column; align-items: start;'>
                                <span style='font-size: 16px; color: #FFFFFF;'>PEG Ratio</span>
                                <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                            </div>
                        """, unsafe_allow_html=True)
                    #Categorize with green,yellow and red Price To Book Ratio
                    pb_ratio = info.get("priceToBook")
                    # Define value and color
                    if pb_ratio is None:
                        color = "gray"
                        value = "N/A"
                    elif pb_ratio < 5:
                        color = "green"
                        value = f"{pb_ratio:.2f}"
                    elif 5 <= pb_ratio <= 15:
                        color = "orange"
                        value = f"{pb_ratio:.2f}"
                    else:
                        color = "red"
                        value = f"{pb_ratio:.2f}"
                    # Display like st.metric with style
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start;'>
                            <span style='font-size: 16px; color: #FFFFFF;'>P/B Ratio</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    #Categorize with green,yellow and red Price To Sales Ratio
                    ps_ratio = info.get("priceToSalesTrailing12Months")
                    # Define value and color
                    if ps_ratio is None:
                        color = "gray"
                        value = "N/A"
                    elif ps_ratio < 4:
                        color = "green"
                        value = f"{ps_ratio:.2f}"
                    elif 4 <= ps_ratio <= 10:
                        color = "orange"
                        value = f"{ps_ratio:.2f}"
                    else:
                        color = "red"
                        value = f"{ps_ratio:.2f}"
                    # Display like st.metric with style
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start;'>
                            <span style='font-size: 16px; color: #FFFFFF;'>P/S Ratio</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    #Categorize with green,yellow and red Price To Sales Ratio
                    roe_ratio = info.get("returnOnEquity")
                    # Define value and color
                    if roe_ratio is None:
                        color = "gray"
                        value = "N/A"
                    elif roe_ratio < 0.1:
                        color = "red"
                        value = f"{roe_ratio:.2f}%"
                    elif 0.1 <= roe_ratio <= 0.2:
                        color = "orange"
                        value = f"{roe_ratio:.2f}%"
                    else:
                        color = "green"
                        value = f"{roe_ratio:.2f}%"
                    value = format_percent(roe_ratio) if isinstance(roe_ratio, (int, float)) else "N/A"
                    # Display like st.metric with style
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start;'>
                            <span style='font-size: 16px; color: #FFFFFF;'>ROE</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    #Categorize EPS CurrentYear
                    eps_current_year = info.get("epsCurrentYear")
                    # Define value and color
                    if eps_current_year is None:
                        color = "gray"
                        value = "N/A"
                    elif eps_current_year < 0:
                        color = "red"
                        value = f"{eps_current_year:.2f}$ (Loss)"
                    elif 0 <= eps_current_year <= 1:
                        color = "orange"
                        value = f"{eps_current_year:.2f}$"
                    elif 1 < eps_current_year <= 5:
                        color = "green"
                        value = f"{eps_current_year:.2f}$"
                    else:
                        color = "blue"
                        value = f"{eps_current_year:.2f}$"
                    eps_current_year = format_currency_dec(eps_current_year)
                    # Display like st.metric with style
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start;'>
                            <span style='font-size: 16px; color: #FFFFFF;'>EPS (Current Year)</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
                with col2:
                    #Categorize EPS Forward
                    eps_forward = info.get("forwardEps")
                    # Define value and color
                    if eps_forward is None:
                        color = "gray"
                        value = "N/A"
                    elif eps_forward < 0:
                        color = "red"
                        value = f"{eps_forward:.2f}$ (Loss)"
                    elif 0 <= eps_forward <= 1:
                        color = "orange"
                        value = f"{eps_forward:.2f}$"
                    elif 1 < eps_forward <= 5:
                        color = "green"
                        value = f"{eps_forward:.2f}$"
                    else:
                        color = "blue"
                        value = f"{eps_forward:.2f}$"
                    eps_forward = format_currency_dec(eps_forward)
                    # Display like st.metric with style
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start;'>
                            <span style='font-size: 16px; color: #FFFFFF;'>EPS(Forward)</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    # Get EBITDA and Revenue from ticker info
                    ebitda = info.get("ebitda")
                    revenue = info.get("totalRevenue")

                    # Compute EBITDA Margin safely
                    if ebitda and revenue and revenue != 0:
                        ebitda_margin = ebitda / revenue * 100
                    else:
                        ebitda_margin = None

                    # Categorize and style
                    if ebitda_margin is None:
                        color = "gray"
                        value = "N/A"
                        tooltip = "EBITDA Margin not available"
                    elif ebitda_margin < 10:
                        color = "red"
                        value = f"{ebitda_margin:.1f}%"
                        tooltip = "Low profitability (EBITDA Margin < 10%)"
                    elif 10 <= ebitda_margin <= 20:
                        color = "orange"
                        value = f"{ebitda_margin:.1f}%"
                        tooltip = "Moderate profitability (10% ≤ EBITDA Margin ≤ 20%)"
                    else:
                        color = "green"
                        value = f"{ebitda_margin:.1f}%"
                        tooltip = "Strong profitability (EBITDA Margin > 20%)"

                    # Display with custom styling and tooltip
                    st.markdown(f"""
                        <div style='display: flex; flex-direction: column; align-items: start; margin-bottom: 1rem;' title="{tooltip}">
                            <span style='font-size: 16px; color: #FFFFFF;'>EBITDA Margin</span>
                            <span style='font-size: 32px; font-weight: bold; color: {color};'>{value}</span>
                        </div>
                    """, unsafe_allow_html=True)

                #Divide sections for displaying Fundamentals Score
                st.divider()
                display_fundamentals_score(info)

            def categorize_cashflow(fcf, revenue):
                if fcf is None or revenue is None:
                    return "N/A", "gray"
                ratio = fcf / revenue
                if ratio > 0.15:
                    return "🟢 Strong", "green"
                elif 0.05 <= ratio <= 0.15:
                    return "🟡 Moderate", "orange"
                else:
                    return "🔴 Weak", "red"

            def categorize_net_income(ni):
                if ni is None:
                    return "N/A", "gray"
                elif ni > 0:
                    return "🟢 Profitable", "green"
                else:
                    return "🔴 Negative", "red"

            def categorize_debt_vs_cash(debt, cash):
                if debt is None or cash is None:
                    return "N/A", "gray"
                if cash > debt:
                    return "🟢 More Cash than Debt", "green"
                elif cash == debt:
                    return "🟡 Balanced", "orange"
                else:
                    return "🔴 High Debt", "red"

            with st.expander("💰 Financials"):
                col1, col2 = st.columns(2)

                fcf = info.get('freeCashflow')
                revenue = info.get('totalRevenue')
                fcf_cat, _ = categorize_cashflow(fcf, revenue)

                net_income = info.get('netIncomeToCommon')
                ni_cat, _ = categorize_net_income(net_income)

                total_debt = info.get('totalDebt')
                total_cash = info.get('totalCash')
                debt_cat, _ = categorize_debt_vs_cash(total_debt, total_cash)

                with col1:
                    st.write(f"**Free Cash Flow:** {format_currency(fcf)} ({fcf_cat})")
                    st.write(f"**Net Income:** {format_currency(net_income)} ({ni_cat})")
                    st.write(f"**Total Revenue:** {format_currency(revenue)}")

                with col2:
                    st.write(f"**Total Debt:** {format_currency(total_debt)}")
                    st.write(f"**Total Cash:** {format_currency(total_cash)} ({debt_cat})")
                    # Compute overall financial health
                    scores = {
                        "green": 2,
                        "orange": 1,
                        "red": 0,
                        "gray": 0
                    }
                    # Get colors for scoring
                    fcf_cat, fcf_color = categorize_cashflow(fcf, revenue)
                    ni_cat, ni_color = categorize_net_income(net_income)
                    debt_cat, debt_color = categorize_debt_vs_cash(total_debt, total_cash)

                    # Score total
                    score = scores[fcf_color] + scores[ni_color] + scores[debt_color]

                    # Final judgment
                    if score >= 5:
                        overall = ("🟢 Healthy Financials", "green")
                    elif 3 <= score < 5:
                        overall = ("🟡 Mixed Financials", "orange")
                    else:
                        overall = ("🔴 Weak Financials", "red")

                    # Display summary
                    st.markdown(f"""
                    <div style='font-size:20px; font-weight:bold; color:{overall[1]};'>
                        {overall[0]}
                    </div>
                    """, unsafe_allow_html=True)

            def categorize_margin(value):
                if value is None:
                    return "N/A", "gray"
                elif value >= 0.4:
                    return "🟢 Excellent", "green"
                elif 0.2 <= value < 0.4:
                    return "🟡 Average", "orange"
                else:
                    return "🔴 Weak", "red"

            def categorize_growth(value):
                if value is None:
                    return "N/A", "gray"
                elif value > 0.15:
                    return "🟢 High Growth", "green"
                elif 0.05 <= value <= 0.15:
                    return "🟡 Moderate", "orange"
                elif value < 0.05:
                    return "🔴 Low Growth", "red"
                return "N/A", "gray"

            with st.expander("📊 Margins & Growth"):
                col1, col2 = st.columns(2)

                # Column 1: Margins
                with col1:
                    gm = info.get('grossMargins')
                    gm_cat, gm_color = categorize_margin(gm)
                    st.write(f"**Gross Margin:** {format_percent(gm)} ({gm_cat})")

                    om = info.get('operatingMargins')
                    om_cat, om_color = categorize_margin(om)
                    st.write(f"**Operating Margin:** {format_percent(om)} ({om_cat})")

                    pm = info.get('profitMargins')
                    pm_cat, pm_color = categorize_margin(pm)
                    st.write(f"**Profit Margin:** {format_percent(pm)} ({pm_cat})")

                # Column 2: Growth
                with col2:
                    eg = info.get('earningsGrowth')
                    eg_cat, eg_color = categorize_growth(eg)
                    st.write(f"**Earnings Growth:** {format_percent(eg)} ({eg_cat})")

                    rg = info.get('revenueGrowth')
                    rg_cat, rg_color = categorize_growth(rg)
                    st.write(f"**Revenue Growth:** {format_percent(rg)} ({rg_cat})")

            with st.expander("📈 Share Dilution Check (Estimation)"):
                st.session_state.selected_ticker = ticker

                info = get_stock_info(ticker)

                revenue_growth = info.get("revenueGrowth", None)
                net_income = info.get("netIncomeToCommon", None)
                previous_net_income = info.get("trailingNetIncome", None)  # Optional
                eps_current = info.get("trailingEps", None)
                eps_forward = info.get("forwardEps", None)
                sbc_expense = info.get("shareBasedCompensation", None)
                total_revenue = info.get("totalRevenue", None)
                cash_from_financing = info.get("totalCashFromFinancingActivities", None)

                if ticker:
                    current_shares, past_shares, dilution = estimate_past_shares_outstanding(ticker)
                    info = get_stock_info(ticker)

                    if current_shares and past_shares and info:
                        dilution_pct = (dilution / past_shares) * 100 if past_shares else 0

                        st.write(f"**Current Shares Outstanding**: {current_shares:,.0f}")
                        st.write(f"**Estimated Shares Outstanding 1 Year Ago**: {past_shares:,.0f}")
                        st.write(f"**Dilution Over 1 Year**: {dilution:,.0f} shares ({dilution_pct:.2f}%)")

                        interpretation = interpret_dilution_extended(
                            dilution_pct,
                            revenue_growth=info.get("revenueGrowth"),
                            eps_current=info.get("trailingEps"),
                            eps_forward=info.get("forwardEps"),
                            sbc_expense=info.get("shareBasedCompensation"),
                            total_revenue=info.get("totalRevenue"),
                            cash_from_financing=info.get("totalCashFromFinancingActivities"),
                        )

                        st.markdown(f"### 🧠 Dilution Context Analysis")
                        st.markdown(interpretation)
                    else:
                        st.warning("Could not estimate dilution due to missing data.")

            with st.expander("📦 Ownership"):
                st.write(f"**Institutional Ownership:** {format_percent(info.get('heldPercentInstitutions'))}")
                st.write(f"**Insider Ownership:** {format_percent(info.get('heldPercentInsiders'))}")

                #if info.get("logo_url", "").startswith("http"):
                    #st.image(info["logo_url"], width=120)

            with st.expander("Company Info", expanded=False):
                _, info = fetch_data(ticker)
                if info:
                    st.write(info)
                else:
                    st.warning("No stock selected.")

            # AI Analysis Section
            # --- Expander 1: AI Analysis & Forecast ---
            with st.expander("💡 AI Analysis & Forecast"):
                if ticker:
                    MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]
                    info = get_stock_info(ticker)

                    current_year = datetime.now().year

                    # Extract basic info
                    company_name = info.get("longName") or info.get("shortName") or ticker
                    sector = info.get("sector", "N/A")
                    market_cap = format_number(info.get("marketCap", "N/A"))
                    current_price = info.get("currentPrice", "N/A")
                    trail_pe = info.get("trailingPE", "N/A")
                    forward_pe = info.get("forwardPE", "N/A")
                    revenue = format_number(info.get("totalRevenue", "N/A"))
                    net_income = format_number(info.get("netIncomeToCommon", "N/A"))
                    eps_current = info.get("trailingEps", "N/A")
                    fcf = format_number(info.get("freeCashflow", "N/A"))
                    dividend_yield = info.get("dividendYield")
                    if dividend_yield is not None:
                        dividend_yield_percent = dividend_yield * 100 if dividend_yield < 0.01 else dividend_yield
                        dividend_yield_str = f"{dividend_yield_percent:.2f}%"
                    else:
                        dividend_yield_str = "N/A"
                    shares_outstanding = info.get("sharesOutstanding", "N/A")
                    summary_of_news = "N/A"

                    # Independent prompt for Analysis
                    analysis_prompt = f"""
                    You are a professional equity analyst. Write a deep analysis using ONLY the following structured data:

                    - Company: {company_name}
                    - Sector: {sector}
                    - Market Cap: {market_cap}
                    - Current Price: ${current_price}
                    - P/E (TTM): {trail_pe}
                    - Forward P/E: {forward_pe}
                    - Revenue: {revenue}
                    - Net Income: {net_income}
                    - EPS: {eps_current}
                    - Free Cash Flow: {fcf}
                    - Dividend Yield: {dividend_yield}
                    - Shares Outstanding: {shares_outstanding}
                    - News: {summary_of_news}

                    Structure the analysis:
                    1. **Executive Summary**
                    2. **Valuation**
                    3. **Financial Health**
                    4. **Growth Potential**
                    5. **Risks**
                    6. **DCF Valuation** - Base, Bull, Bear
                    7. **Fair Value vs Current Price**
                    8. **12-Month Target & Recommendation**
                    9. **Support & Resistance**
                    """

                    if st.button(f"🧠 Generate AI Analysis for {ticker.upper()}", key="analysis_btn"):
                        with st.spinner("Calling Mistral for analysis..."):
                            raw = get_ai_analysis(analysis_prompt, MISTRAL_API_KEY)

                        if raw.startswith("ERROR:"):
                            st.error("Failed to generate AI analysis.")
                            st.code(raw)
                        else:
                            corrected = clean_ai_output(raw, true_price=info.get("currentPrice", 0.0))
                            st.markdown(f"**AI Analysis for {ticker.upper()}:**")
                            sections = re.split(r'\n(?=\d+\.)', corrected)
                            for section in sections:
                                st.markdown(section.strip().replace('\n', '  \n'))
                else:
                    st.info("Please select a ticker to view AI analysis.")


            # --- Expander 2: AI DCF Valuation ---
            with st.expander("💰 AI DCF Valuation"):
                if ticker:
                    MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]
                    info = get_stock_info(ticker)

                    # Extract values safely
                    def clean_value(value, default="N/A"):
                        return value if value not in [None, "N/A", float("nan")] else default

                    company_name = info.get("longName") or info.get("shortName") or ticker
                    sector = clean_value(info.get("sector"))
                    market_cap = clean_value(info.get("marketCap"))
                    current_price = clean_value(info.get("currentPrice"))
                    trail_pe = clean_value(info.get("trailingPE"))
                    forward_pe = clean_value(info.get("forwardPE"))
                    revenue = clean_value(info.get("totalRevenue"))
                    net_income = clean_value(info.get("netIncomeToCommon"))
                    eps_current = clean_value(info.get("trailingEps"))
                    fcf = clean_value(info.get("freeCashflow"))
                    shares_outstanding = clean_value(info.get("sharesOutstanding"))
                    debt_data = clean_value("totalDebt")
                    cash_data = clean_value("totalCash")
                    eps_growth = clean_value("earningsQuarterlyGrowth")
                    revenue_growth = clean_value("revenueGrowth")

                    dividend_yield = info.get("dividendYield")
                    if dividend_yield is not None:
                        dividend_yield_percent = dividend_yield * 100 if dividend_yield < 0.01 else dividend_yield
                        dividend_yield_str = f"{dividend_yield_percent:.2f}%"
                    else:
                        dividend_yield_str = "N/A"

                    # Independent prompt for DCF
                    dcf_prompt = f"""
                    You are a professional equity analyst. Based on the financial metrics retrieved earlier from Yahoo Finance 
                    and current market expectations for {company_name} ({ticker.upper()}), generate a realistic 5-year DCF valuation 
                    starting from fiscal year {current_year}.

                    Use the following data as a baseline:
                    - Company: {company_name}
                    - Sector: {sector}
                    - Market Cap: {market_cap}
                    - Current Price: ${current_price}
                    - P/E (TTM): {trail_pe}
                    - Forward P/E: {forward_pe}
                    - Revenue (TTM): {revenue}
                    - Net Income: {net_income}
                    - EPS: {eps_current}
                    - Free Cash Flow (TTM): {fcf}
                    - Dividend Yield: {dividend_yield_str}
                    - Shares Outstanding: {shares_outstanding}
                    - Total Debt: {debt_data}
                    - Total Cash: {cash_data}
                    - EPS Growth: {eps_growth}
                    - RevenueGrowth: {revenue_growth}

                    DCF guidelines:
                    1. Use the latest reported revenue as the starting point (do not inflate starting revenue).
                    2. Assume FCF margins based on Sector Comparison, Sector Average, Stock historical performance and Stock Future Growth based on Future Guidance(Do not guess or invent data).
                    3. Estimate base, bull, and bear revenue growth rates based essentially on current {revenue_growth} and apply majoration for each scenario.
                    4. Use a discount rate based on Sector Average allways considering Company Actual Growth, especially if Company is growing at a faster pace than Average.
                    5. Based essencially on {revenue_growth} apply a realistic terminal growth rate
                    6. Run a 5-year DCF using {revenue_growth}, {fcf} and clearly show PV of cash flows and terminal value.
                    7. Output per-share valuation for each scenario (bear, base, bull).
                    8. Compare to current market price and provide % upside/downside.
                    9. Give a final fair value estimate and recommendation (Buy, Hold, Sell).
                    10. Provide the most accurate Weekly Support and Resistance levels based on technical analysis.

                    ❗Emphasize realism, forward-looking assumptions, and avoid overly conservative or overly aggressive inputs.
                    """
                    # Warn if shares outstanding looks off
                    if isinstance(shares_outstanding, (float, int)) and shares_outstanding > 100_000_000_000:
                        st.warning(f"Unusually large shares outstanding reported for {ticker}: {shares_outstanding}")

                    if st.button("🧠 Generate AI-Powered DCF Valuation", key="dcf_btn"):
                        with st.spinner("Calling Mistral for DCF valuation..."):
                            raw_dcf = get_ai_analysis(dcf_prompt, MISTRAL_API_KEY)

                        if raw_dcf.startswith("ERROR:"):
                            st.error("Failed to generate AI DCF valuation.")
                            st.code(raw_dcf)
                        else:
                            st.markdown("**📈 AI-Generated DCF Valuation:**")
                            sections = re.split(r'\n(?=\d+\.)', raw_dcf)
                            for section in sections:
                                st.markdown(section.strip().replace('\n', '  \n'))
                else:
                    st.warning("Please select a stock ticker.")