import streamlit as st
import pandas as pd
from utils.utils import get_stock_info
from huggingface_hub import InferenceClient
from mistral import Client
import os
import traceback
import re

# Page config
st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("📁 Welcome to Your Finance App")

#  Set API token
api_key = st.secrets["MISTRAL_API_KEY"]
client = Client(api_key=api_key)

# Choose a Mistral model (free-tier compatible)
model_id = "mistral-small-latest"  # Options: mistral-small-latest, mistral-medium-latest, etc.

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
                        response = client.chat(
                            model=model_id,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.7,
                            max_tokens=700,
                            top_p=0.9,
                        )
                        st.write("Raw API response:", response)

                        if "choices" in response and len(response["choices"]) > 0:
                            generated_text = response["choices"][0]["message"]["content"].strip()
                        else:
                            return "ERROR: No valid response from Mistral model."

                        return generated_text

                    except Exception:
                        return f"ERROR: {traceback.format_exc()}"

                def format_number(num):
                    if isinstance(num, (int, float)):
                        if num > 1e12:
                            return f"{num / 1e12:.2f} trillion"
                        elif num > 1e9:
                            return f"{num / 1e9:.2f} billion"
                        elif num > 1e6:
                            return f"{num / 1e6:.2f} million"
                        else:
                            return f"{num}"
                    return num

                # Assume `info` and `ticker` are defined earlier in your app
                company_name = info.get("longName") or info.get("shortName") or ticker
                sector = info.get("sector", "N/A")
                market_cap = format_number(info.get("marketCap", "N/A"))
                pe_ratio = info.get("trailingPE", "N/A")
                revenue = format_number(info.get("totalRevenue", "N/A"))
                net_income = format_number(info.get("netIncomeToCommon", "N/A"))
                eps = info.get("trailingEps", "N/A")
                dividend_yield_val = info.get("dividendYield", None)
                dividend_yield = f"{dividend_yield_val * 100:.2f}%" if dividend_yield_val not in [None, "N/A"] else "N/A"
                summary_of_news = "N/A"  # placeholder

                prompt = f"""
                You are a financial analyst. Based on the following metrics for the stock {ticker}, write a concise and clear stock analysis:
                - Company Name: {company_name}
                - Sector: {sector}
                - Market Cap: {market_cap}
                - P/E Ratio: {pe_ratio}
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
                    analysis = get_ai_analysis(prompt)

                    if analysis.startswith("ERROR:"):
                        st.error("AI analysis failed.")
                        st.code(analysis, language="text")
                    else:
                        col = st.container()
                        with col:
                            st.markdown(f"**AI Analysis for {ticker.upper()}:**")
                            sections = re.split(r'\n(?=\d+\.)', analysis)
                            for section in sections:
                                st.markdown(section.strip().replace('\n', '  \n'))
else:
    st.info("Please select a stock from the list.")