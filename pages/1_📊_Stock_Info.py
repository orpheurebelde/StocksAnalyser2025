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
                    st.metric("PEG Ratio", format_ratio(info.get("trailingPegRatio")))
                    st.metric("P/B", format_ratio(info.get("priceToBook")))
                    st.metric("P/S", format_ratio(info.get("priceToSalesTrailing12Months")))
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("ROE", format_percent(info.get("returnOnEquity")))
                    st.metric("EPS (Current Year)", format_currency_dec(info.get("epsCurrentYear")))
                with col2:
                    st.metric("EPS (Forward)", format_currency_dec(info.get("forwardEps")))
                    st.metric("Dividend Yield", format_percent(info.get("dividendYield")))

            with st.expander("💰 Financials"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Free Cash Flow:** {format_currency(info.get('freeCashflow'))}")
                    st.write(f"**Net Income:** {format_currency(info.get('netIncomeToCommon'))}")
                    st.write(f"**Total Revenue:** {format_currency(info.get('totalRevenue'))}")
                with col2:
                    st.write(f"**Total Debt:** {format_currency(info.get('totalDebt'))}")
                    st.write(f"**Total Cash:** {format_currency(info.get('totalCash'))}")

            with st.expander("📊 Margins & Growth"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Gross Margin:** {format_percent(info.get('grossMargins'))}")
                    st.write(f"**Operating Margin:** {format_percent(info.get('operatingMargins'))}")
                    st.write(f"**Profit Margin:** {format_percent(info.get('profitMargins'))}")
                with col2:
                    st.write(f"**Earnings Growth:** {format_percent(info.get('earningsGrowth'))}")
                    st.write(f"**Revenue Growth:** {format_percent(info.get('revenueGrowth'))}")

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
                    eps = info.get("trailingEps", "N/A")
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
                    - EPS: {eps}
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