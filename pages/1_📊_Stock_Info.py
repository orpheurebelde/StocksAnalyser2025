import streamlit as st
import pandas as pd
from utils.utils import calculate_dcf_valor, load_stock_list, get_stock_info, get_ai_analysis, format_number, fetch_data, display_fundamentals_score, fetch_price_data, analyze_price_action
import re
import time

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

            with st.expander("📦 Ownership"):
                st.write(f"**Institutional Ownership:** {format_percent(info.get('heldPercentInstitutions'))}")
                st.write(f"**Insider Ownership:** {format_percent(info.get('heldPercentInsiders'))}")
            
            # AI Analysis Section
            with st.expander("💡 AI Analysis & Forecast"):
                MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]
                ticker = st.session_state.get("selected_ticker")

                if ticker:
                    info = get_stock_info(ticker)

                    # Collect structured data
                    company_name = info.get("longName") or info.get("shortName") or ticker
                    sector = info.get("sector", "N/A")
                    market_cap = format_number(info.get("marketCap", "N/A"))
                    trail_pe = info.get("trailingPE", "N/A")
                    forward_pe = info.get("forwardPE", "N/A")
                    revenue = format_number(info.get("totalRevenue", "N/A"))
                    net_income = format_number(info.get("netIncomeToCommon", "N/A"))
                    eps_current = info.get("trailingEps", "N/A")
                    fcf = format_number(info.get("freeCashflow", "N/A"))
                    dividend_yield_val = info.get("dividendYield", None)
                    dividend_yield = f"{dividend_yield_val * 100:.2f}%" if dividend_yield_val not in [None, "N/A"] else "N/A"
                    shares_outstanding = info.get("sharesOutstanding", "N/A")
                    current_price = info.get("currentPrice", "N/A")
                    summary_of_news = "N/A"

                    # Prompt
                    prompt = f"""
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
                        1. **Executive Summary** - Max 3 sentences.
                        2. **Valuation** - Use P/E & Fwd P/E to evaluate price fairness.
                        3. **Financial Health** - Net Income, FCF, Cash vs Debt.
                        4. **Growth Potential** - EPS, Sector outlook, revenue.
                        5. **Risks** - Competitive, macro, financial, etc.
                        6. **DCF Valuation** - Provide Base, Bull, Bear share price:
                        - Base Case: $X.XX
                        - Bull Case: $X.XX
                        - Bear Case: $X.XX
                        7. **Fair Value vs Current Price**
                        8. **12-Month Target & Recommendation** - Buy, Hold or Sell.

                        ❗DO NOT invent data. Stick only to the provided inputs.
                        """

                    if st.button(f"🧠 Generate AI Analysis for {ticker.upper()}"):
                        with st.spinner("Calling Mistral for analysis..."):
                            raw = get_ai_analysis(prompt, MISTRAL_API_KEY)

                        if raw.startswith("ERROR:"):
                            st.error("Failed to generate AI analysis.")
                            st.code(raw)
                        else:
                            corrected = clean_ai_output(raw, true_price=info.get("currentPrice", 0.0))
                            st.markdown(f"**AI Analysis for {ticker.upper()}:**")
                            sections = re.split(r'\n(?=\d+\.)', corrected)
                            for section in sections:
                                st.markdown(section.strip().replace('\n', '  \n'))

            with st.expander("Company Info", expanded=False):
                _, info = fetch_data(ticker)
                if info:
                    st.write(info)
                else:
                    st.warning("No stock selected.")

            with st.expander("🛠️ Customize DCF Inputs"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    base_growth = st.number_input("Base Revenue CAGR (%)", min_value=0.0, max_value=50.0, value=8.0, step=0.5) / 100
                with col2:
                    bull_growth = st.number_input("Bull Case Revenue CAGR (%)", min_value=0.0, max_value=50.0, value=12.0, step=0.5) / 100
                with col3:
                    bear_growth = st.number_input("Bear Case Revenue CAGR (%)", min_value=0.0, max_value=50.0, value=4.0, step=0.5) / 100
                
                discount_rate = st.slider("Discount Rate (%)", min_value=4.0, max_value=15.0, value=10.0, step=0.5) / 100

            with st.expander("💰 Discounted Cash Flow (DCF) Valuation"):
                with st.spinner("Calculating DCF..."):
                    ticker_symbol = ticker.split(" - ")[0].strip().upper()
                    result = calculate_dcf_valor(
                        ticker,
                        revenue_growth_base=base_growth,
                        revenue_growth_bull=bull_growth,
                        revenue_growth_bear=bear_growth,
                        discount_rate=discount_rate
                    )

                if "Error" in result:
                    st.error(f"❌ Error: {result['Error']}")
                else:
                    current_price = result['Current Price']
                    st.metric("📊 Current Price", f"${current_price:.2f}")

                    cols = st.columns(3)
                    for i, case in enumerate(["Bear", "Base", "Bull"]):
                        valuation = result[case]
                        delta = valuation - current_price
                        delta_pct = (delta / current_price) * 100

                        color = "normal"
                        if delta > 0:
                            color = "inverse"
                        elif delta < 0:
                            color = "off"

                        cols[i].metric(
                            f"{case} Case Valuation",
                            f"${valuation:.2f}",
                            f"{delta_pct:.1f}%",
                            delta_color=color
                        )