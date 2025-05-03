import streamlit as st
from utils import get_stock_analysis
import pandas as pd

# Streamlit Page Setup
st.title("Stock Analyzer with Finnhub")

# User Input for stock symbol
symbol = st.text_input("Enter Stock Symbol", "AAPL")

# User Input for date range (optional)
start_date = st.date_input("Start Date", value=pd.to_datetime('2015-01-01'))
end_date = st.date_input("End Date", value=pd.to_datetime('2025-01-01'))

# Display analysis for the stock symbol
if symbol:
    analysis_data = get_stock_analysis(symbol, start_date=str(start_date), end_date=str(end_date))
    
    if isinstance(analysis_data, str):  # If the result is an error message
        st.error(analysis_data)
    else:
        # Display stock data (Price, High, Low, etc.)
        stock_data = analysis_data['stock_data']
        st.write(f"**Current Price**: {stock_data['c']}")
        st.write(f"**High**: {stock_data['h']}, **Low**: {stock_data['l']}")
        st.write(f"**Open**: {stock_data['o']}, **Previous Close**: {stock_data['pc']}")

        # Display RSI data
        rsi_data = analysis_data['rsi_data']
        st.write("**RSI Data**:")
        st.write(rsi_data[['time', 'RSI']])

        # Display Historical Data (Closing prices)
        historical_data = analysis_data['historical_data']
        st.write("**Historical Data (Closing Prices)**:")
        st.write(historical_data)