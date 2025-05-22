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
model_id = "HuggingFaceH4/zephyr-7b-beta"  # Replace with your model ID

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
                            prompt,
                            model=model_id,
                            max_new_tokens=500,  # Increased from 150
                            temperature=0.7,
                            do_sample=True,
                            # You can add `top_p=0.9` or other params if needed
                        )
                        st.write("Raw API response:", response)
                        if isinstance(response, list) and len(response) > 0:
                            generated_text = response[0].get('generated_text', '').strip()
                        elif isinstance(response, dict):
                            generated_text = response.get('generated_text', '').strip()
                        else:
                            generated_text = ""

                        if not generated_text:
                            return "ERROR: Empty response from Hugging Face model."
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
                analysis = get_ai_analysis(prompt)

                if analysis.startswith("ERROR:"):
                    st.error("AI analysis failed.")
                    st.code(analysis, language="text")
                else:
                    # Justify text via custom CSS injection
                    justify_style = """
                    <style>
                    .justified-text {
                        text-align: justify;
                        text-justify: inter-word;
                        white-space: pre-wrap;  /* Preserve newlines */
                    }
                    </style>
                    """
                    st.markdown(justify_style, unsafe_allow_html=True)
                    st.markdown(f"<div class='justified-text'>**AI Analysis for {ticker.upper()}:**<br><br>{analysis}</div>", unsafe_allow_html=True)
else:
    st.info("Please select a stock from the list.")