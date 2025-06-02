import streamlit as st
import yfinance as yf
import pandas as pd
from utils.utils import show_indicators
from datetime import datetime    

st.title("📈 Market Analysis | Buy Signals")

# Define tickers
tickers = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX"
}

# Display market indicators
with st.expander("📈 Market Indicators (S&P 500 & Nasdaq 100)"):
    col1, col2 = st.columns(2)

    # Show both market indicators
    with col1:
        show_indicators("^GSPC", "S&P 500 Indicators")

    with col2:
        show_indicators("^NDX", "Nasdaq 100 Indicators")
    
with st.expander("📈 Monthly Performance Analysis", expanded=True):
    @st.cache_data
    def fetch_monthly_returns(ticker):
        # Fetch data from Yahoo Finance
        data = yf.download(ticker, period="10y", interval="1d", progress=False)
        
        if data.empty:
            st.error(f"Could not fetch data for {ticker}")
            return pd.DataFrame()

        # Resample to monthly frequency (closing prices)
        monthly_data = data['Close'].resample('M').ffill()
        
        # Calculate percentage change to get returns
        monthly_returns = monthly_data.pct_change().dropna()

        # Check if monthly_returns is a Series and convert to DataFrame
        if isinstance(monthly_returns, pd.Series):
            df = monthly_returns.to_frame(name='Monthly Return')
        else:
            df = monthly_returns.rename(columns={monthly_returns.columns[0]: 'Monthly Return'})

        # Add 'Year' and 'Month' columns for easy filtering
        df['Year'] = df.index.year
        df['Month'] = df.index.month

        return df

    def analyze_monthly_performance(monthly_returns):
        current_year = datetime.now().year
        current_month = datetime.now().month

        current_month_data = monthly_returns[
            (monthly_returns['Year'] == current_year) & 
            (monthly_returns['Month'] == current_month)
        ]

        if current_month_data.empty:
            current_performance = None
        else:
            current_performance = current_month_data['Monthly Return'].values[0]

        historical_max = monthly_returns['Monthly Return'].max()
        historical_min = monthly_returns['Monthly Return'].min()

        if current_performance is not None:
            if current_performance > historical_max:
                category = 'Highest'
            elif current_performance < historical_min:
                category = 'Lowest'
            else:
                category = 'Neutral'
        else:
            category = 'No Data'

        return current_performance, historical_max, historical_min, category

    def display_monthly_performance(ticker, title):
        monthly_returns = fetch_monthly_returns(ticker)
        if monthly_returns.empty or 'Monthly Return' not in monthly_returns.columns:
            st.error(f"Could not fetch data for {ticker}")
            return

        current_performance, historical_max, historical_min, category = analyze_monthly_performance(monthly_returns)

        if current_performance is not None:
            if current_performance > historical_max:
                colorM = 'green'
            elif current_performance < historical_min:
                colorM = 'red'
            else:
                colorM = 'orange'

        st.subheader(f"{title} - Monthly Performance")
        if current_performance is not None:
            st.markdown(f"<span style='color:{colorM}; font-size:18px;'><strong>Current Month Perfomance</strong>: {current_performance * 100:.2f}%</span>",unsafe_allow_html=True)
            st.write(f"**Historical Max Monthly Return**: {historical_max * 100:.2f}%")
            st.write(f"**Historical Min Monthly Return**: {historical_min * 100:.2f}%")
            # Display category with color
            if category == 'Highest':
                st.markdown(f"<span style='color:green;'>**Category**: {category}</span>", unsafe_allow_html=True)
            elif category == 'Lowest':
                st.markdown(f"<span style='color:red;'>**Category**: {category}</span>", unsafe_allow_html=True)
            elif category == 'Neutral':
                st.markdown(f"<span style='color:orange;'>**Category**: {category}</span>", unsafe_allow_html=True)
        else:
            st.write("No data available for the current month.")

    def display_yearly_performance(ticker, title):
        import yfinance as yf
        import pandas as pd
        from datetime import datetime

        # Fetch historical data for the past 10 years
        data = yf.download(ticker, period="10y", interval="1d", progress=False)
        if data.empty:
            st.error(f"Could not fetch data for {ticker}")
            return

        # Resample to yearly frequency and calculate yearly returns
        yearly_data = data['Close'].resample('Y').ffill()
        yearly_returns = yearly_data.pct_change().dropna()
        yearly_returns.index = yearly_returns.index.year

        # Ensure column is named properly
        if isinstance(yearly_returns, pd.Series):
            yearly_returns = yearly_returns.to_frame()
            yearly_returns.columns = ['Yearly Return']
        else:
            yearly_returns.columns = ['Yearly Return']

        # Get current year
        current_year = datetime.now().year

        if current_year in yearly_returns.index:
            current_performance = yearly_returns.loc[current_year, 'Yearly Return']
        else:
            current_performance = None

        historical_max = yearly_returns['Yearly Return'].max()
        historical_min = yearly_returns['Yearly Return'].min()

        # Categorize current performance
        if current_performance is not None:
            if current_performance > historical_max:
                category = 'Highest'
            elif current_performance < historical_min:
                category = 'Lowest'
            else:
                category = 'Neutral'
        else:
            category = 'No Data'

        st.subheader(f"{title} - Yearly Performance")

        if current_performance is not None:
            if current_performance > historical_max:
                color = 'green'
            elif current_performance < historical_min:
                color = 'red'
            else:
                color = 'orange'
            st.markdown(f"<span style='color:{color}; font-size:18px;'><strong>Current Year Perfomance</strong>: {current_performance * 100:.2f}%</span>",unsafe_allow_html=True)
            #st.write(f"**Current Year Performance**: {current_performance * 100:.2f}%")
            st.write(f"**Historical Max Yearly Return**: {historical_max * 100:.2f}%")
            st.write(f"**Historical Min Yearly Return**: {historical_min * 100:.2f}%")
            # Display category with color
            st.markdown(f"<span style='color:{color}; font-size:18px;'>**Category**: {category}</span>", unsafe_allow_html=True)
        else:
            st.write("No data available for the current year.")


st.title("Market Performance Analysis - Last 10 Years")

# Display S&P 500 monthly performance in 2 columns expander
col1, col2 = st.columns(2)
with col1:
    with st.expander("📈 S&P 500 | Nasdaq 100 Monthly Performance", expanded=True):
        display_monthly_performance("^GSPC", "S&P 500")
        display_monthly_performance("^NDX", "Nasdaq 100")

with col2:
    with st.expander("📈 S&P 500 | Nasdaq 100 Yearly Performance", expanded=True):
        display_yearly_performance("^GSPC", "S&P 500")
        display_yearly_performance("^NDX", "Nasdaq 100")