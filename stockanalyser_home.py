import streamlit as st
from utils import get_stock_info

# Set up Streamlit page config
st.set_page_config(page_title="Stock Info", layout="wide")

# Stock Info Section
#if menu == "Stock Info":
st.title("📊 Stock Info and Metrics")
st.markdown("### Search for a Stock Ticker or Company Name")

# Input box for user to type the stock name, with a default value
search_input = st.text_input("Enter Stock Ticker or Name", "Apple")

# Ensure session state is initialized for selected_ticker
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None

if search_input:
    # Dynamically fetch matching tickers
    ticker_options = get_stock_info(search_input)

    with st.expander("### Matching Companies:"):
        if ticker_options:
            for company_name, ticker in ticker_options.items():
                if st.button(f"{ticker} - {company_name}"):
                    st.session_state.selected_ticker = ticker  # Store in session state
                    st.rerun()  # Rerun script to update display immediately
        else:
            st.warning("No matching stocks found. Please refine your search.")
else:
    st.info("Please enter a stock name or ticker to search.")

# Display stock information
with st.expander("Sector and Industry", expanded=False):
    if st.session_state.selected_ticker:
        st.write(f"**Selected Ticker:** {st.session_state.selected_ticker}")
        # Here you can fetch stock data and display additional information
    else:
        st.warning("No stock selected. Please choose a ticker.")

    col1, col2, col3 = st.columns(3)  # Initialize columns

    with col1:
        if st.session_state.selected_ticker:
            _, info = fetch_data(st.session_state.selected_ticker)
            if info:
                st.markdown(f"<h4>Name: {st.session_state.selected_ticker} - {info.get('longName', 'Company Name Not Found')}</h4>", unsafe_allow_html=True)
            else:
                st.warning("Stock information not found.")
        else:
            st.warning("No stock selected.")
    with col2:
        if st.session_state.selected_ticker:
            _, info = fetch_data(st.session_state.selected_ticker)
            if info:
                st.markdown(f"<h4>Sector: {info.get('sector', 'Sector Not Found')}</h4>", unsafe_allow_html=True)
            else:
                st.warning("No stock selected.")
    with col3:
        if st.session_state.selected_ticker:
            _, info = fetch_data(st.session_state.selected_ticker)
            if info:
                st.markdown(f"<h4>Industry: {info.get('industry', 'Industry Not Found')}</h4>", unsafe_allow_html=True)
            else:
                st.warning("No stock selected.")
    
# Initialize info with a default value
info = None  

with st.expander("Company Info", expanded=False):
    if st.session_state.selected_ticker:
        _, info = fetch_data(st.session_state.selected_ticker)
        if info:
            st.write(info)
        else:
            st.warning("No stock selected.")

# Check if key exists and value is valid before using it
def safe_metric(value, divisor=1, suffix="", percentage=False):
        """Safely formats a metric value for Streamlit display."""
        try:
            if value is None:
                return "N/A"
            if isinstance(value, (int, float)):
                if math.isnan(value):  # Handle NaN values
                    return "N/A"
                if percentage:
                    return f"{value:.2%}"
                return f"${value / divisor:.2f}{suffix}" if divisor > 1 else f"${value:.2f}"
            return "N/A"
        except Exception as e:
            return f"Error: {e}"  # Return error message instead of crashing

if isinstance(info, dict) and info:  # Ensure 'info' is a dictionary and not empty
    freecash_flow = info.get('freeCashflow', 'N/A')
    pe_ratio = info.get('trailingPE', 'N/A')
    peg_ratio = info.get('trailingPegRatio', 'N/A')
    earnings_growth = info.get('earningsGrowth', 'N/A')
    forward_pe = info.get('forwardPE', 'N/A')
    freecash_flow = info.get('freeCashflow', 'N/A')
    netincome = info.get('netIncomeToCommon', 'N/A')
    grossmargin = info.get('grossMargins', 'N/A')
    operatingmargin = info.get('operatingMargins', 'N/A')
    profit_margin = info.get('profitMargins', 'N/A')
    institutional_ownership = info.get('heldPercentInstitutions', 'N/A')
    insider_ownership = info.get('heldPercentInsiders', 'N/A')
else:
    st.warning("Stock information not found.")

if isinstance(info, dict) and info:  # Ensure 'info' is a dictionary and not empty
    pe_ratio = info.get('trailingPE', 'N/A')
    peg_ratio = info.get('trailingPegRatio', 'N/A')
    earnings_growth = info.get('earningsGrowth', 'N/A')
    forward_pe = info.get('forwardPE', 'N/A')
    freecash_flow = info.get('freeCashflow', 'N/A')
    netincome = info.get('netIncomeToCommon', 'N/A')
    grossmargin = info.get('grossMargins', 'N/A')
    operatingmargin = info.get('operatingMargins', 'N/A')
    profit_margin = info.get('profitMargins', 'N/A')
    institutional_ownership = info.get('heldPercentInstitutions', 'N/A')
    insider_ownership = info.get('heldPercentInsiders', 'N/A')
    trailingeps = info.get('epsCurrentYear', 'N/A')
    forwardeps = info.get('forwardEps', 'N/A')
    revenue = info.get('totalRevenue', 'N/A')
    totaldebt = info.get('totalDebt', 'N/A')
    totalcash = info.get('totalCash', 'N/A')
    revenuegrowth = info.get('revenueGrowth', 'N/A')
else:
    st.warning("Stock information not found.")

with st.expander("Stock Overview", expanded=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="📈 Market Cap", value=safe_metric(info['marketCap'], 1e9, "B") if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Free Cash Flow", value=safe_metric(freecash_flow, 1e9, "B") if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Net Income", value=safe_metric(netincome, 1e9, "B") if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Gross Margin", value=safe_metric(grossmargin, percentage=True) if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Operating Margin", value=safe_metric(operatingmargin, percentage=True) if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Profit Margin", value=safe_metric(profit_margin, percentage=True) if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Earnings Growth", value=safe_metric(earnings_growth, percentage=True) if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Dividend Yield", value=safe_metric(info.get('dividendYield'), percentage=True) if isinstance(info, dict) and 'marketCap' in info else "N/A")

    with col2:
        # Safe conversion function to handle None and invalid values
        def safe_float(value):
            try:
                return float(value) if value not in [None, 'N/A', '', 'NaN'] else None
            except (ValueError, TypeError):
                return None

        if info is not None:    
            # Fetch and safely convert values from `info`
            pe_ratio = safe_float(info.get('trailingPE', None))
            pb_ratio = safe_float(info.get('priceToBook', None))
            ps_ratio = safe_float(info.get('priceToSalesTrailing12Months', None))
            roe = safe_float(info.get('returnOnEquity', None))
            forward_pe = safe_float(info.get('forwardPE', None))
            totaldebt = safe_float(info.get('totalDebt', None))
            totalcash = safe_float(info.get('totalCash', None))

            # Ensure info is a dictionary
            if isinstance(info, dict):
                peg_ratio = info.get('pegRatio', None)  # Fetch pegRatio safely
            else:
                peg_ratio = None  # Default to None if info is invalid

            # Convert safely
            try:
                peg_ratio = float(peg_ratio) if peg_ratio not in [None, 'N/A', '', 'NaN'] else "N/A"
            except (ValueError, TypeError):
                peg_ratio = "N/A"  # If conversion fails, set as "N/A"

            # Assign color based on value
            if isinstance(peg_ratio, (int, float)):
                peg_color = "green" if peg_ratio < 1 else "orange" if 1 <= peg_ratio <= 2 else "red"
            else:
                peg_color = "gray"

            # Categorize P/E Ratio
            if isinstance(pe_ratio, (int, float)) and pe_ratio is not None and not math.isnan(pe_ratio):
                pe_color = "green" if pe_ratio < 15 else "orange" if 15 <= pe_ratio <= 25 else "red"
                st.markdown(f"<span style='color:{pe_color}; font-size:25px;'>📈 P/E Ratio: {pe_ratio:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:gray; font-size:25px;'>📈 P/E Ratio: N/A</span>", unsafe_allow_html=True)

            # Categorize Forward P/E Ratio
            if isinstance(forward_pe, (int, float)) and forward_pe is not None and not math.isnan(forward_pe):
                pe_color = "green" if forward_pe < 15 else "orange" if 15 <= forward_pe <= 25 else "red"
                st.markdown(f"<span style='color:{pe_color}; font-size:25px;'>📈 Forward P/E Ratio: {forward_pe:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:gray; font-size:25px;'>📈 Forward P/E Ratio: N/A</span>", unsafe_allow_html=True)
            
            # Categorize P/S Ratio
            if isinstance(ps_ratio, (int, float)) and ps_ratio is not None and not math.isnan(ps_ratio):
                ps_color = "green" if ps_ratio < 1 else "orange" if 1 <= ps_ratio <= 2 else "red"
                st.markdown(f"<span style='color:{ps_color}; font-size:25px;'>📈 P/S Ratio: {ps_ratio:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:gray; font-size:25px;'>📈 P/S Ratio: N/A</span>", unsafe_allow_html=True)

            # Categorize P/B Ratio
            if isinstance(pb_ratio, (int, float)) and pb_ratio is not None and not math.isnan(pb_ratio):
                pb_color = "green" if pb_ratio < 1 else "orange" if 1 <= pb_ratio <= 2 else "red"
                st.markdown(f"<span style='color:{pb_color}; font-size:25px;'>📈 P/B Ratio: {pb_ratio:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:gray; font-size:25px;'>📈 P/B Ratio: N/A</span>", unsafe_allow_html=True)

            #Categorize ROE Ratio
            if isinstance(roe, (int, float)) and roe is not None and not math.isnan(roe):
                roe_color = "green" if roe > 0.15 else "orange" if 0.05 <= roe <= 0.15 else "red"
                st.markdown(f"<span style='color:{roe_color}; font-size:25px;'>📈 ROE Ratio: {roe:.2%}</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:gray; font-size:25px;'>📈 ROE Ratio: N/A</span>", unsafe_allow_html=True)

            # Categorize Debt to Equity Ratio
            if isinstance(totaldebt, (int, float)) and isinstance(totalcash, (int, float)) and totaldebt > 0 and totalcash > 0:
                debt_to_equity = totaldebt / totalcash
                debt_color = "green" if debt_to_equity < 1 else "orange" if 1 <= debt_to_equity <= 2 else "red"
                st.markdown(f"<span style='color:{debt_color}; font-size:25px;'>📈 Debt to Equity Ratio: {debt_to_equity:.2f}</span>", unsafe_allow_html=True)
            else:
                st.metric(label="📈 Debt to Equity Ratio", value="N/A")

            st.write("")  # Empty line

            # Display Total Debt & Total Cash
            st.metric(label="📈 Total Debt", value=f"${totaldebt / 1e9:.2f}B" if isinstance(totaldebt, (int, float)) else "N/A")
            st.metric(label="📈 Total Cash", value=f"${totalcash / 1e9:.2f}B" if isinstance(totalcash, (int, float)) else "N/A")

        else:
            # Handle the case where info is None
            st.write("Error: 'info' object is not properly initialized or is None.")

    with col3:
        st.metric(label="📈 Trailing EPS", value=f"${trailingeps:.2f}" if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Forward EPS", value=f"${forwardeps:.2f}" if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Revenue", value=f"${revenue / 1e9:.2f}B" if revenue and isinstance(revenue, (int, float)) else "N/A")
        st.metric(label="📈 Revenue Growth", value=f"{revenuegrowth:.2%}" if revenuegrowth and isinstance(revenuegrowth, (int, float)) else "N/A")
        st.metric(label="📈 Institutional Ownership", value=f"{institutional_ownership:.2%}" if isinstance(info, dict) and 'marketCap' in info else "N/A")
        st.metric(label="📈 Insider Ownership", value=f"{insider_ownership:.2%}" if isinstance(info, dict) and 'marketCap' in info else "N/A")

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