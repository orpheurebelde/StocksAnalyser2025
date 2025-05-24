import streamlit as st
import pandas as pd
from utils.utils import get_stock_info, get_ai_analysis, format_number, fetch_data
import re
import time

# Page config
st.set_page_config(page_title="Finance Dashboard", layout="wide")

SESSION_TIMEOUT_SECONDS = 600

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "last_activity" not in st.session_state:
    st.session_state["last_activity"] = time.time()

if st.session_state["authenticated"]:
    now = time.time()
    if now - st.session_state["last_activity"] > SESSION_TIMEOUT_SECONDS:
        st.session_state["authenticated"] = False
        st.warning("Session expired.")
        st.experimental_rerun()
    else:
        st.session_state["last_activity"] = now

if not st.session_state["authenticated"]:
    st.error("Unauthorized. Please go to the home page and log in.")
    st.stop()

st.title("📁 Welcome to Your Finance App")

# Load stock list
@st.cache_data
def load_stock_list():
    df = pd.read_csv("stocks_list.csv", sep=";")
    df["Display"] = df["Ticker"] + " - " + df["Name"]
    return df

stock_df = load_stock_list()
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

# Format helpers
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_percent(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"
def format_ratio(val): return f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"

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
                    st.metric("EPS (Forward)", format_currency_dec(info.get("forwardEps")))
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
                    <hr>
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

            if info.get("logo_url", "").startswith("http"):
                st.image(info["logo_url"], width=120)

            # AI Analysis Section
            with st.expander("💡 AI Analysis & Forecast"):
                MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]

                if ticker:
                    info = get_stock_info(ticker)

                    company_name = info.get("longName") or info.get("shortName") or ticker
                    sector = info.get("sector", "N/A")
                    market_cap = format_number(info.get("marketCap", "N/A"))
                    trail_pe = info.get("trailingPE", "N/A")
                    revenue = format_number(info.get("totalRevenue", "N/A"))
                    net_income = format_number(info.get("netIncomeToCommon", "N/A"))
                    eps_current_year = info.get("trailingEps", "N/A")
                    dividend_yield_val = info.get("dividendYield", None)
                    dividend_yield = f"{dividend_yield_val * 100:.2f}%" if dividend_yield_val not in [None, "N/A"] else "N/A"
                    summary_of_news = "N/A"

                    prompt = f"""
                    You are a financial analyst. Based on the following metrics for the stock {ticker}, write a concise and clear stock analysis:

                    - Company Name: {company_name}
                    - Sector: {sector}
                    - Market Cap: {market_cap}
                    - P/E Ratio: {trail_pe}
                    - Revenue (last FY): {revenue}
                    - Net Income (last FY): {net_income}
                    - EPS: {eps_current_year}
                    - Dividend Yield: {dividend_yield}
                    - Recent News: {summary_of_news}

                    The analysis should include:
                    1. Executive summary
                    2. Valuation commentary
                    3. Growth potential
                    4. Risks
                    5. Investment outlook

                    Start now:
                    """

                if st.button(f"🧠 Generate AI Analysis for {ticker.upper()}"):
                    with st.spinner("Generating AI stock analysis..."):
                        analysis = get_ai_analysis(prompt, MISTRAL_API_KEY)

                    if analysis.startswith("ERROR:"):
                        st.error("AI analysis failed.")
                        st.code(analysis, language="text")
                    else:
                        st.markdown(f"**AI Analysis for {ticker.upper()}:**")
                        sections = re.split(r'\n(?=\d+\.)', analysis)
                        for section in sections:
                            st.markdown(section.strip().replace('\n', '  \n'))

            with st.expander("Company Info", expanded=False):
                _, info = fetch_data(ticker)
                if info:
                    st.write(info)
                else:
                    st.warning("No stock selected.")