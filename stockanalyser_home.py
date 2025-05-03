import streamlit as st
from utils import get_stock_info

# Set up Streamlit page config
st.set_page_config(page_title="Stock Info", layout="wide")

st.title("📊 Stock Info")

# Input for stock ticker
ticker = st.text_input("Enter Stock Ticker", "AAPL")

if ticker:
    info = get_stock_info(ticker)

    if 'error' in info:
        st.error(info['error'])
    else:
        st.subheader(f"{info.get('shortName', ticker)} ({ticker.upper()})")

        # Center content using three columns layout
        left_space, main_col, right_space = st.columns([1, 2, 1])

        with main_col:
            # Company Profile
            with st.expander("🏢 Company Profile", expanded=True):
                st.write(f"**Sector:** {info.get('sector')}")
                st.write(f"**Industry:** {info.get('industry')}")
                st.write(f"**Employees:** {info.get('fullTimeEmployees')}")
                st.write(f"**Location:** {info.get('city')}, {info.get('state')}, {info.get('country')}")
                st.write(f"**Website:** {info.get('website')}")
                st.write(f"**Description:**\n{info.get('longBusinessSummary')}")

            # Valuation & Fundamentals
            with st.expander("📈 Valuation & Fundamentals", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Market Cap", f"{info.get('marketCap', 'N/A'):,}")
                    st.metric("Trailing P/E", info.get("trailingPE"))
                    st.metric("Forward P/E", info.get("forwardPE"))
                with col2:
                    st.metric("PEG Ratio", info.get("pegRatio"))
                    st.metric("P/B", info.get("priceToBook"))
                    st.metric("P/S", info.get("priceToSalesTrailing12Months"))

                st.markdown("---")
                st.metric("ROE", info.get("returnOnEquity"))
                st.metric("EPS (Current Year)", info.get("epsCurrentYear"))
                st.metric("EPS (Forward)", info.get("forwardEps"))
                st.metric("Dividend Yield", info.get("dividendYield"))

            # Financials
            with st.expander("💰 Financials", expanded=False):
                st.write(f"**Free Cash Flow:** {info.get('freeCashflow'):,}")
                st.write(f"**Net Income:** {info.get('netIncomeToCommon'):,}")
                st.write(f"**Total Revenue:** {info.get('totalRevenue'):,}")
                st.write(f"**Total Debt:** {info.get('totalDebt'):,}")
                st.write(f"**Total Cash:** {info.get('totalCash'):,}")

            # Margins & Growth
            with st.expander("📊 Margins & Growth", expanded=False):
                st.write(f"**Gross Margin:** {info.get('grossMargins')}")
                st.write(f"**Operating Margin:** {info.get('operatingMargins')}")
                st.write(f"**Profit Margin:** {info.get('profitMargins')}")
                st.write(f"**Earnings Growth:** {info.get('earningsGrowth')}")
                st.write(f"**Revenue Growth:** {info.get('revenueGrowth')}")

            # Ownership
            with st.expander("📦 Ownership", expanded=False):
                st.write(f"**Institutional Ownership:** {info.get('heldPercentInstitutions')}")
                st.write(f"**Insider Ownership:** {info.get('heldPercentInsiders')}")

            # Show the logo
            if info.get("logo_url") and info["logo_url"].startswith("http"):
                st.image(info["logo_url"], width=100)