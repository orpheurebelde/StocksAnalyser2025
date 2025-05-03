import streamlit as st
from utils import get_stock_info, get_logo_url, safe_metric

# Set page config
st.set_page_config(page_title="Stock Info", layout="wide")
st.title("📊 Stock Info")

# Input
ticker = st.text_input("Enter Stock Ticker", "AAPL")

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

if ticker:
    info = get_stock_info(ticker)

    if 'error' in info:
        st.error(info['error'])
    else:
        st.subheader(f"{info.get('shortName', ticker)} ({ticker.upper()})")

        # Use wide layout but center logical content into wide columns
        left, main, right = st.columns([1, 10, 1])

        with main:

            # --- Company Profile ---
            with st.expander("🏢 Company Profile", expanded=True):
                st.write(f"**Sector:** {info.get('sector', 'N/A')}")
                st.write(f"**Industry:** {info.get('industry', 'N/A')}")
                st.write(f"**Employees:** {format_number(info.get('fullTimeEmployees'))}")
                st.write(f"**Location:** {info.get('city', '')}, {info.get('state', '')}, {info.get('country', '')}")
                st.write(f"**Website:** {info.get('website', 'N/A')}")
                st.write(f"**Description:**\n{info.get('longBusinessSummary', 'N/A')}")

            # --- Valuation & Fundamentals ---
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

            # --- Financials ---
            with st.expander("💰 Financials", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Free Cash Flow:** {format_currency(info.get('freeCashflow'))}")
                    st.write(f"**Net Income:** {format_currency(info.get('netIncomeToCommon'))}")
                    st.write(f"**Total Revenue:** {format_currency(info.get('totalRevenue'))}")
                with col2:
                    st.write(f"**Total Debt:** {format_currency(info.get('totalDebt'))}")
                    st.write(f"**Total Cash:** {format_currency(info.get('totalCash'))}")

                # --- Margins & Growth ---
            with st.expander("📊 Margins & Growth", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Gross Margin:** {format_percent(info.get('grossMargins'))}")
                    st.write(f"**Operating Margin:** {format_percent(info.get('operatingMargins'))}")
                    st.write(f"**Profit Margin:** {format_percent(info.get('profitMargins'))}")
                with col2:
                    st.write(f"**Earnings Growth:** {format_percent(info.get('earningsGrowth'))}")
                    st.write(f"**Revenue Growth:** {format_percent(info.get('revenueGrowth'))}")

            # --- Ownership ---
            with st.expander("📦 Ownership", expanded=False):
                st.write(f"**Institutional Ownership:** {format_percent(info.get('heldPercentInstitutions'))}")
                st.write(f"**Insider Ownership:** {format_percent(info.get('heldPercentInsiders'))}")

            # --- Logo ---
            if info.get("logo_url", "").startswith("http"):
                st.image(info["logo_url"], width=120)