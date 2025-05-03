import streamlit as st
from utils import *
import os

st.set_page_config("Stock Info", layout="wide")

st.title("📈 Stock Info with Alpha Vantage")
ticker = st.text_input("Enter stock ticker (e.g. AAPL)", value="AAPL").upper()

if ticker:
    apikey = st.secrets["ALPHA_VANTAGE_KEY"]

    if is_data_stale(ticker):
        with st.spinner(f"Fetching fresh data for {ticker}..."):
            df = fetch_stock_data_alpha(ticker, apikey)
            if df is not None:
                save_data(ticker, df)
            else:
                st.error("API limit reached or invalid ticker.")
                st.stop()
    else:
        df = load_cached_data(ticker)

    if df is not None and not df.empty:
        st.subheader(f"📉 Adjusted Close Price for {ticker}")
        st.line_chart(df.set_index("Date")["adj_close"])

        with st.expander("📊 Key Metrics"):
            st.markdown("Coming soon: P/E, EPS, Revenue, etc.")

        with st.expander("🏢 Company Info"):
            st.markdown("Coming soon: Sector, Description, Exchange, etc.")
