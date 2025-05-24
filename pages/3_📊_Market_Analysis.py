import streamlit as st
import yfinance as yf
import pandas as pd
from utils.utils import compute_rsi, compute_macd, compute_fibonacci_level
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

    def show_indicators(ticker, title):
        data = yf.Ticker(ticker).history(period="10y")
        if data.empty:
            st.error(f"Could not fetch data for {ticker}")
            return

        close = data["Close"]

        # Find the first available trading day of the year
        try:
            # Ensure start_of_year is timezone-aware and matches the timezone of close.index
            start_of_year = pd.Timestamp.now(tz=close.index.tz).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            start_price = close.loc[close.index >= start_of_year].iloc[0] if not close.loc[close.index >= start_of_year].empty else close.iloc[0]
        except Exception as e:
            st.error(f"Error during selection: {e}")
            start_price = close.iloc[0]

        # Calculate YTD % return
        ytd = ((close.iloc[-1] / start_price) - 1) * 100

        # Calculate RSI, MACD, and Fibonacci levels
        rsi = compute_rsi(close)
        macd, signal = compute_macd(close)
        fib_level_3y = compute_fibonacci_level(close[-252*3:])  # Last 3 years
        fib_level_5y = compute_fibonacci_level(close[-252*5:])  # Last 5 years
        fib_level_10y = compute_fibonacci_level(close)  # Last 10 years

        #Calculate and categorize MACD signal into a variable
        macd_signal = "Bullish" if macd.iloc[-1] > signal.iloc[-1] else "Bearish"
        macd_color = "green" if macd_signal == "Bullish" else "red"

        #Calculate and categorize RSI signal for markdown incorporation
        rsi_signal = None
        rsi_color = None
        if rsi < 30:
            rsi_signal = "Bullish"
            rsi_color = "green"
        elif rsi > 70:
            rsi_signal = "Bearish"
            rsi_color = "red"
        else:
            rsi_signal = "Neutral"
            rsi_color = "yellow"
        if isinstance(rsi, (int, float)):
            rsi = round(rsi, 2)
        else:
            rsi = "N/A"

        #Calculate and classify the YTD % if with Correction, Bear Market, Crash or Bull Market for markdown incorporation
        ytd_signal = None
        ytd_color = None
        if ytd > 0:
            ytd_signal = "Bull Market"
            ytd_color = "green"
        elif -20 < ytd <= 0:
            ytd_signal = "Correction"
            ytd_color = "orange"
        elif -30 < ytd <= -20:
            ytd_signal = "Bear Market"
            ytd_color = "red"
        elif ytd > -30:
            ytd_signal = "Crash"
            ytd_color = "darkred"
        else:
            ytd_signal = "N/A"
            ytd_color = "gray"

        st.subheader(title)
        st.markdown(f"""
        - **52 Week High**: ${close[-252:].max():,.2f}
        - **52 Week Low**: ${close[-252:].min():,.2f}
        - **RSI**: {rsi:.2f} (<span style='color:{rsi_color}; font-size:18px;'> {rsi_signal}</span>)
        - **MACD Signal**: {signal.iloc[-1]:.2f} (<span style='color:{macd_color}; font-size:18px;'> {macd_signal}</span>)
        - **YTD %**: {ytd:.2f}% (<span style='color:{ytd_color}; font-size:18px;'> {ytd_signal}</span>)
        - **1D %**: {close.pct_change().iloc[-1]*100:.2f}%
        - **5D %**: {close.pct_change(5).iloc[-1]*100:.2f}%
        - **1M %**: {close.pct_change(21).iloc[-1]*100:.2f}%
        - **6M %**: {close.pct_change(126).iloc[-1]*100:.2f}%
        - **1Y %**: {close.pct_change(252).iloc[-1]*100:.2f}%
        - **5Y %**: {close.pct_change(1260).iloc[-1]*100:.2f}%
        - **Fibonacci Level (3Y Range)**: {fib_level_3y:.2f}%
        - **Fibonacci Level (5Y Range)**: {fib_level_5y:.2f}%
        - **Fibonacci Level (10Y Range)**: {fib_level_10y:.2f}%
        """, unsafe_allow_html=True)

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
            if current_performance == historical_max:
                category = 'Highest'
            elif current_performance == historical_min:
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

        st.subheader(f"{title} - Monthly Performance")

        if current_performance is not None:
            st.write(f"**Current Month Performance**: {current_performance * 100:.2f}%")
            st.write(f"**Historical Max Monthly Return**: {historical_max * 100:.2f}%")
            st.write(f"**Historical Min Monthly Return**: {historical_min * 100:.2f}%")
            st.write(f"**Category**: {category}")
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
            if current_performance == historical_max:
                category = 'Highest'
            elif current_performance == historical_min:
                category = 'Lowest'
            else:
                category = 'Neutral'
        else:
            category = 'No Data'

        st.subheader(f"{title} - Yearly Performance")

        if current_performance is not None:
            st.write(f"**Current Year Performance**: {current_performance * 100:.2f}%")
            st.write(f"**Historical Max Yearly Return**: {historical_max * 100:.2f}%")
            st.write(f"**Historical Min Yearly Return**: {historical_min * 100:.2f}%")
            st.write(f"**Category**: {category}")
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