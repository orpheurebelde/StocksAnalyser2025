import streamlit as st
import pandas as pd
from utils.utils import get_stock_info
from huggingface_hub import InferenceClient
import os
import traceback

# Page config
st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("📁 Welcome to Your Finance App")

#  Set API token
api_key = st.secrets["HUGGINGFACE_API_KEY"]
os.environ["HUGGINGFACEHUB_API_TOKEN"] = api_key
client = InferenceClient(token=api_key)

# Use a FREE model (ensure it's compatible with text_generation)
model_id = "HuggingFaceH4/zephyr-7b-beta"

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

                @st.cache_data(show_spinner=False)
                def get_ai_analysis(prompt):
                    try:
                        response = client.text_generation(
                            model=model_id,
                            prompt=prompt,
                            max_new_tokens=200,
                            temperature=0.7,
                        ) 
                        if not response or not response.strip():
                            return "ERROR: Empty response from Hugging Face model."
                        return response.strip()
                    except Exception as e:
                        return f"ERROR: {traceback.format_exc()}"


                prompt = f"""
                You are a financial analyst. Provide a brief report for {ticker.upper()} stock based on the following:
                - Company: {info.get('shortName')}
                - Sector: {info.get('sector')}
                - Industry: {info.get('industry')}
                - Market Cap: {info.get('marketCap')}
                - P/E Ratio: {info.get('trailingPE')}
                - Revenue: {info.get('totalRevenue')}
                - Dividend Yield: {info.get('dividendYield')}
                - Country: {info.get('country')}
                Include a 3-year and 5-year future outlook.
                """

                analysis = get_ai_analysis(prompt)
                if analysis.startswith("ERROR:"):
                    st.error("AI analysis failed.")
                    st.code(analysis, language="text")
                else:
                    st.markdown(f"**AI Analysis for {ticker.upper()}:**\n\n{analysis}")
else:
    st.info("Please select a stock from the list.")