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
        # Display error message if there was an issue with fetching stock info
        st.error(info['error'])
    else:
        # Display company information if no error occurred
        st.subheader(f"{info.get('shortName', ticker)} ({ticker.upper()})")

        # Create columns to display data side by side
        col1, col2 = st.columns(2)

        # Left Column: Basic Info & Company Profile
        with col1:
            st.markdown("### Company Profile")
            st.write(f"**Sector:** {info.get('sector')}")
            st.write(f"**Industry:** {info.get('industry')}")
            st.write(f"**Employees:** {info.get('fullTimeEmployees')}")
            st.write(f"**Location:** {info.get('city')}, {info.get('state')}, {info.get('country')}")
            st.write(f"**Website:** {info.get('website')}")
            st.write(f"**Description:**\n{info.get('longBusinessSummary')}")

        # Right Column: Valuation & Financials
        with col2:
            st.markdown("### Valuation & Fundamentals")
            st.metric("Market Cap", f"{info.get('marketCap', 'N/A'):,}")
            st.metric("Trailing P/E", info.get("trailingPE"))
            st.metric("Forward P/E", info.get("forwardPE"))
            st.metric("PEG Ratio", info.get("pegRatio"))
            st.metric("P/B", info.get("priceToBook"))
            st.metric("P/S", info.get("priceToSalesTrailing12Months"))

            st.markdown("---")

            st.metric("ROE", info.get("returnOnEquity"))
            st.metric("EPS (Current Year)", info.get("epsCurrentYear"))
            st.metric("EPS (Forward)", info.get("forwardEps"))
            st.metric("Dividend Yield", info.get("dividendYield"))

        # Financials Section
        st.markdown("### Financials")
        st.write(f"**Free Cash Flow:** {info.get('freeCashflow'):,}")
        st.write(f"**Net Income:** {info.get('netIncomeToCommon'):,}")
        st.write(f"**Total Revenue:** {info.get('totalRevenue'):,}")
        st.write(f"**Total Debt:** {info.get('totalDebt'):,}")
        st.write(f"**Total Cash:** {info.get('totalCash'):,}")

        # Margins & Growth Section
        st.markdown("### Margins & Growth")
        st.write(f"**Gross Margin:** {info.get('grossMargins')}")
        st.write(f"**Operating Margin:** {info.get('operatingMargins')}")
        st.write(f"**Profit Margin:** {info.get('profitMargins')}")
        st.write(f"**Earnings Growth:** {info.get('earningsGrowth')}")
        st.write(f"**Revenue Growth:** {info.get('revenueGrowth')}")

        # Ownership Section
        st.markdown("### Ownership")
        st.write(f"**Institutional Ownership:** {info.get('heldPercentInstitutions')}")
        st.write(f"**Insider Ownership:** {info.get('heldPercentInsiders')}")

        # Show the logo image if available
        if info.get("logo_url") and info["logo_url"].startswith("http"):
            st.image(info["logo_url"], width=100)