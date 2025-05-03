import streamlit as st
from utils import *
import os

# Set up page configuration
st.set_page_config("Stock Info", layout="wide")

# Title of the web page
st.title("📈 Stock Info with Alpha Vantage")

# Input field for the stock ticker symbol
ticker = st.text_input("Enter stock ticker (e.g. AAPL)", value="AAPL").upper()

# Proceed only if ticker is entered
if ticker:
    apikey = st.secrets["ALPHA_VANTAGE_KEY"]  # Fetch API key from Streamlit secrets

    # Check if the data for the given ticker is stale (older than 1 day)
    if is_data_stale(ticker):
        with st.spinner(f"Fetching fresh data for {ticker}..."):
            # Fetch new stock data if stale
            df = fetch_stock_data_alpha(ticker, apikey)
            if df is not None:
                # If data fetched successfully, save it locally
                save_data(ticker, df)
            else:
                st.error("API limit reached or invalid ticker.")
                st.stop()  # Stop execution if there's an error
    else:
        # Load cached data if it is fresh
        df = load_cached_data(ticker)

    # If valid data is available, proceed to display
    if df is not None and not df.empty:
        st.subheader(f"📉 Daily Close Price for {ticker}")

        # Line chart for displaying the stock's daily closing price
        st.line_chart(df.set_index("Date")["close"])

        # Placeholder for key metrics (Coming soon)
        with st.expander("📊 Key Metrics"):
            st.markdown("Coming soon: P/E, EPS, Revenue, etc.")

        # Placeholder for company info (Coming soon)
        with st.expander("🏢 Company Info"):
            st.markdown("Coming soon: Sector, Description, Exchange, etc.")

    else:
        # Display an error if no data is available
        st.error("No data available for this ticker.")
