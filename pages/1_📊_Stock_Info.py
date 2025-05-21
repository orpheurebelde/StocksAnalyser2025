import streamlit as st
import pandas as pd
from utils.utils import get_stock_info
from langchain_community.llms import HuggingFaceHub
from langchain.prompts import PromptTemplate
import os

# Load API key from Streamlit secrets
os.environ["HUGGINGFACEHUB_API_TOKEN"] = st.secrets["HUGGINGFACE_API_KEY"]

st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("📁 Welcome to Your Finance App")

# Load stock list
@st.cache_data
def load_stock_list():
    df = pd.read_csv("stocks_list.csv", sep=";")
    df["Display"] = df["Ticker"] + " - " + df["Name"]
    return df

stock_df = load_stock_list()
options = ["Select a stock..."] + stock_df["Display"].tolist()

selected_display = st.selectbox(
    "🔎 Search Stock by Ticker or Name",
    options,
    index=0,
)

def format_currency(val):
    return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"

def format_currency_dec(val):
    return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"

def format_percent(val):
    return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"

def format_number(val):
    return f"{val:,}" if isinstance(val, (int, float)) else "N/A"

def format_ratio(val):
    return f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"

if selected_display != "Select a stock...":
    ticker = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    info = get_stock_info(ticker)

    if 'error' in info:
        st.error(info['error'])
    else:
        st.subheader(f"{info.get('shortName', ticker)} ({ticker.upper()})")

        # Use wide layout but center logical content into wide columns
        left, main, right = st.columns([0.5, 10, 0.5])

        with main:

            with st.expander("📉 Click to Expand TradingView Chart"):
                st.markdown(
                    f'<iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_1&symbol={ticker}&interval=W&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=Dark&style=2&timezone=Etc%2FGMT%2B3&hideideas=1" width="100%" height="400" frameborder="0" allowtransparency="true" scrolling="no"></iframe>',
                    unsafe_allow_html=True,
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
                    st.metric("Trailing P/E", format_ratio(info.get("trailingPE")))
                    st.metric("Forward P/E", format_ratio(info.get("forwardPE")))
                with col2:
                    st.metric("PEG Ratio", format_ratio(info.get("pegRatio")))
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

            with st.expander("💰 Financials", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Free Cash Flow:** {format_currency(info.get('freeCashflow'))}")
                    st.write(f"**Net Income:** {format_currency(info.get('netIncomeToCommon'))}")
                    st.write(f"**Total Revenue:** {format_currency(info.get('totalRevenue'))}")
                with col2:
                    st.write(f"**Total Debt:** {format_currency(info.get('totalDebt'))}")
                    st.write(f"**Total Cash:** {format_currency(info.get('totalCash'))}")

            with st.expander("📊 Margins & Growth", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Gross Margin:** {format_percent(info.get('grossMargins'))}")
                    st.write(f"**Operating Margin:** {format_percent(info.get('operatingMargins'))}")
                    st.write(f"**Profit Margin:** {format_percent(info.get('profitMargins'))}")
                with col2:
                    st.write(f"**Earnings Growth:** {format_percent(info.get('earningsGrowth'))}")
                    st.write(f"**Revenue Growth:** {format_percent(info.get('revenueGrowth'))}")

            with st.expander("📦 Ownership", expanded=False):
                st.write(f"**Institutional Ownership:** {format_percent(info.get('heldPercentInstitutions'))}")
                st.write(f"**Insider Ownership:** {format_percent(info.get('heldPercentInsiders'))}")

            if info.get("logo_url", "").startswith("http"):
                st.image(info["logo_url"], width=120)

            with st.expander("🧠 AI Stock Report & Forecast", expanded=False):
                with st.spinner("Generating analysis..."):

                    st.write("Secrets available:", list(st.secrets.keys()))
                    st.write("Hugging Face key:", st.secrets.get("HUGGINGFACE_API_KEY", "Not found"))

                    def build_prompt(ticker, info):
                        return f"""
                        You are a financial analyst. Analyze the following stock based on current metrics:

                        - Ticker: {ticker}
                        - Sector: {info.get('sector')}
                        - Industry: {info.get('industry')}
                        - Market Cap: {info.get('marketCap')}
                        - Trailing P/E: {info.get('trailingPE')}
                        - Forward P/E: {info.get('forwardPE')}
                        - ROE: {info.get('returnOnEquity')}
                        - EPS (Current Year): {info.get('epsCurrentYear')}
                        - EPS (Forward): {info.get('forwardEps')}
                        - Revenue Growth: {info.get('revenueGrowth')}
                        - Earnings Growth: {info.get('earningsGrowth')}
                        - Free Cash Flow: {info.get('freeCashflow')}
                        - Dividend Yield: {info.get('dividendYield')}

                        Write a report with:
                        1. Performance overview for 2024
                        2. 3-year and 5-year projections
                        3. Risks and opportunities
                        4. Investor recommendation (bullish, bearish, neutral)
                                                """

                    prompt_text = build_prompt(ticker, info)

                    llm = HuggingFaceHub(
                        repo_id="google/flan-t5-large",
                        model_kwargs={"temperature": 0.7, "max_length": 800}
                    )

                    try:
                        response = llm(prompt_text)
                        st.write(response)
                    except Exception as e:
                        st.error("⚠️ AI analysis failed.")
                        st.exception(e)
else:
    st.info("Please select a stock from the list.")