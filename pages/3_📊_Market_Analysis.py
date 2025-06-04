import streamlit as st
import yfinance as yf
import pandas as pd
from utils.utils import compute_fibonacci_level, compute_rsi, compute_macd
from datetime import datetime    

st.title("📈 Market Analysis | Buy Signals")

# Define tickers
tickers = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX"
}

@st.cache_data
def show_indicators(ticker, title):
    data = yf.Ticker(ticker).history(period="10y")
    if data.empty:
        st.error(f"Could not fetch data for {ticker}")
        return

    close = data["Close"]
    price = close.iloc[-1]
    high_52w = close[-252:].max()
    low_52w = close[-252:].min()

    # First trading day of the year
    try:
        start_of_year = pd.Timestamp.now(tz=close.index.tz).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        start_price = close.loc[close.index >= start_of_year].iloc[0] if not close.loc[close.index >= start_of_year].empty else close.iloc[0]
    except Exception as e:
        st.error(f"Error selecting start price: {e}")
        start_price = close.iloc[0]

    # YTD Return
    ytd = ((price / start_price) - 1) * 100

    # Indicators
    rsi = compute_rsi(close)
    macd, signal = compute_macd(close)
    fib_level_3y = compute_fibonacci_level(close[-252*3:])
    fib_level_5y = compute_fibonacci_level(close[-252*5:])
    fib_level_10y = compute_fibonacci_level(close)

    # MACD Classification
    macd_signal = "Bullish" if macd.iloc[-1] > signal.iloc[-1] else "Bearish"
    macd_color = "green" if macd_signal == "Bullish" else "red"

    # RSI Classification
    if rsi < 30:
        rsi_signal, rsi_color = "Bullish", "green"
    elif rsi > 70:
        rsi_signal, rsi_color = "Bearish", "red"
    else:
        rsi_signal, rsi_color = "Neutral", "orange"
    rsi = round(rsi, 2) if isinstance(rsi, (int, float)) else "N/A"

    # YTD Classification
    if ytd > 0:
        ytd_signal, ytd_color = "Bull Market", "green"
    elif -20 < ytd <= 0:
        ytd_signal, ytd_color = "Correction", "orange"
    elif -30 < ytd <= -20:
        ytd_signal, ytd_color = "Bear Market", "red"
    else:
        ytd_signal, ytd_color = "Crash", "darkred"

    # Price vs 52-week range
    price_position = (price - low_52w) / (high_52w - low_52w)
    if price_position > 0.85:
        price_category, price_color = "Near 52-Week High", "green"
    elif price_position < 0.15:
        price_category, price_color = "Near 52-Week Low", "red"
    else:
        price_category, price_color = "Mid Range", "orange"

    # Trend from Moving Averages
    sma_50 = close[-50:].mean()
    sma_200 = close[-200:].mean()
    if price > sma_50 and price > sma_200:
        trend, trend_color = "Uptrend", "green"
    elif price < sma_50 and price < sma_200:
        trend, trend_color = "Downtrend", "red"
    else:
        trend, trend_color = "Sideways", "orange"

    # Fibonacci context (3Y)
    fib_comment_3y = "Above 3Y Fib Level (Breakout)" if price > fib_level_3y else "Below 3Y Fib Level (Support)"

    # Define a helper function to get the color
    def get_color(value):
        return "green" if value >= 0 else "red"

    # Calculate percentages once to make the code cleaner
    p1d = close.pct_change().iloc[-1] * 100
    p5d = close.pct_change(5).iloc[-1] * 100
    p1m = close.pct_change(21).iloc[-1] * 100
    p6m = close.pct_change(126).iloc[-1] * 100
    p1y = close.pct_change(252).iloc[-1] * 100
    p5y = close.pct_change(1260).iloc[-1] * 100

    st.subheader(title)
    st.markdown(f"""
    <div style='font-size:16px; line-height:1.6;'>

    <div><strong>Ticker</strong>: {ticker}</div>
    <div><strong>Current Price</strong>: ${price:,.2f} 
        <span style='color:{price_color}; font-size:18px;'>({price_category})</span>
    </div>
    <div><strong>52 Week High</strong>: ${high_52w:,.2f}</div>
    <div><strong>52 Week Low</strong>: ${low_52w:,.2f}</div>
    <div><strong>Trend</strong>: 
        <span style='color:{trend_color}; font-size:18px;'>{trend}</span>
    </div>
    <div><strong>RSI</strong>: {rsi} 
        (<span style='color:{rsi_color}; font-size:18px;'> {rsi_signal}</span>)
    </div>
    <div><strong>MACD Signal</strong>: {signal.iloc[-1]:.2f} 
        (<span style='color:{macd_color}; font-size:18px;'> {macd_signal}</span>)
    </div>
    <hr style='border: 1px solid #444;' />
    <div><strong>YTD %</strong>: {ytd:.2f}% 
        (<span style='color:{ytd_color}; font-size:18px;'> {ytd_signal}</span>)
    </div>
    <div><strong>1D %</strong>: <span style="color: {get_color(p1d)};">{p1d:.2f}%</div>
    <div><strong>5D %</strong>: <span style="color: {get_color(p5d)};">{p5d:.2f}%</div>
    <div><strong>1M %</strong>: <span style="color: {get_color(p1m)};">{p1m:.2f}%</div>
    <div><strong>6M %</strong>: <span style="color: {get_color(p6m)};">{p6m:.2f}%</div>
    <div><strong>1Y %</strong>: <span style="color: {get_color(p1y)};">{p1y:.2f}%</div>
    <div><strong>5Y %</strong>: <span style="color: {get_color(p5y)};">{p5y:.2f}%</div>
    <hr style='border: 1px solid #444;' />
    <div><strong>Fibonacci Level (3Y Range)</strong>: {fib_level_3y:.2f}% - {fib_comment_3y}</div>
    <div><strong>Fibonacci Level (5Y Range)</strong>: {fib_level_5y:.2f}%</div>
    <div><strong>Fibonacci Level (10Y Range)</strong>: {fib_level_10y:.2f}%</div>

    </div>
    """, unsafe_allow_html=True)

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