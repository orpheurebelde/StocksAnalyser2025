import streamlit as st
import yfinance as yf
import pandas as pd
from utils.utils import compute_fibonacci_level, compute_rsi, compute_macd
from datetime import datetime

# --- 1. Set page configuration ---
st.set_page_config(
    page_title="📊 Market Analysis",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. Custom CSS for the refresh button ---
st.markdown("""
<style>
    /* Position the button absolutely within the app's header for consistent placement */
    .stApp > header {
        position: relative; /* Ensure header is positioned for absolute children */
        display: flex;
        align-items: center;
        justify-content: space-between; /* This will push button to the right if title is also in header */
        padding-top: 20px; /* Adjust as needed */
        padding-bottom: 20px;
    }
    .stButton button {
        position: absolute;
        top: 10px; /* Adjust top position */
        right: 10px; /* Adjust right position */
        background-color: #4CAF50; /* Green */
        color: white;
        border: none;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 4px;
        z-index: 1000; /* Ensure button is above other content */
    }
    .stButton button:hover {
        background-color: #45a049; /* Darker green on hover */
    }
    /* Add some general padding to the main content area if elements are overlapping */
    .block-container {
        padding-top: 3rem; /* Adjust if your title/button are too close to content */
    }
</style>
""", unsafe_allow_html=True)

# --- 3. Refresh button logic ---
# This part is correct and will trigger a full app rerun.
if st.button("Refresh Indicators"):
    st.cache_data.clear()    # Clear the cache for data functions
    st.cache_resource.clear() # Clear the cache for resource functions (e.g., models)
    st.success("Indicators refreshed successfully! Rerunning application...")
    st.rerun() # Forces the entire Streamlit script to re-execute from the top

# --- 4. Main application title ---
st.title("📈 Market Analysis | Buy Signals")

# Define tickers (this is fine as it is)
tickers = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX"
    }
# --- 5. `show_indicators` function (now with proper `</span>` tags and a timestamp) ---
@st.cache_data(ttl=3600) # Cache for 1 hour; adjust as needed
def show_indicators(ticker, title):
    # This message will only appear if the cache is cleared or expires
    st.markdown(f"<p style='color: gray; font-size: 12px;'>Data last fetched/calculated for {title}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)
    
    data = yf.Ticker(ticker).history(period="10y") # Fetches 10 years of daily data
    if data.empty:
        st.error(f"Could not fetch data for {ticker}")
        return

    close = data["Close"]
    price = close.iloc[-1]
    high_52w = close[-252:].max()
    low_52w = close[-252:].min()

    # First trading day of the year (improved handling for timezone and empty data)
    try:
        current_year_start = pd.Timestamp(datetime.now().year, 1, 1, tz='UTC') # Use UTC for consistency
        # Find the first price at or after the start of the current year
        start_price_series = close.loc[close.index.tz_localize('UTC') >= current_year_start]
        start_price = start_price_series.iloc[0] if not start_price_series.empty else close.iloc[0]
    except Exception as e:
        st.error(f"Error determining YTD start price for {ticker}: {e}")
        start_price = close.iloc[0] # Fallback to first available price

    # YTD Return
    ytd = ((price / start_price) - 1) * 100 if start_price != 0 else 0

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
    if pd.isna(rsi): # Handle potential NaN from compute_rsi
        rsi_signal, rsi_color = "N/A", "gray"
    elif rsi < 30:
        rsi_signal, rsi_color = "Bullish", "green"
    elif rsi > 70:
        rsi_signal, rsi_color = "Bearish", "red"
    else:
        rsi_signal, rsi_color = "Neutral", "orange"
    rsi_display = round(rsi, 2) if isinstance(rsi, (int, float)) and not pd.isna(rsi) else "N/A"

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
    price_position = (price - low_52w) / (high_52w - low_52w) if (high_52w - low_52w) != 0 else 0
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

    # Helper function for color based on value
    def get_color(value):
        return "green" if value >= 0 else "red"

    # Calculate percentages once
    p1d = close.pct_change().iloc[-1] * 100 if len(close) > 1 else np.nan
    p5d = close.pct_change(5).iloc[-1] * 100 if len(close) > 5 else np.nan
    p1m = close.pct_change(21).iloc[-1] * 100 if len(close) > 21 else np.nan
    p6m = close.pct_change(126).iloc[-1] * 100 if len(close) > 126 else np.nan
    p1y = close.pct_change(252).iloc[-1] * 100 if len(close) > 252 else np.nan
    p5y = close.pct_change(1260).iloc[-1] * 100 if len(close) > 1260 else np.nan

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
    <div><strong>RSI</strong>: {rsi_display}
        (<span style='color:{rsi_color}; font-size:18px;'> {rsi_signal}</span>)
    </div>
    <div><strong>MACD Signal</strong>: {signal.iloc[-1]:.2f}
        (<span style='color:{macd_color}; font-size:18px;'> {macd_signal}</span>)
    </div>
    <hr style='border: 1px solid #444;' />
    <div>
    <strong>YTD %</strong>: <span style='color:{ytd_color};'>{ytd:.2f}%</span>
    (<span style='color:{ytd_color}; font-size:18px;'> {ytd_signal}</span>)
    </div>
    <div><strong>1D %</strong>: <span style="color: {get_color(p1d)};">{p1d:.2f}%</span></div>
    <div><strong>5D %</strong>: <span style="color: {get_color(p5d)};">{p5d:.2f}%</span></div> 
    <div><strong>1M %</strong>: <span style="color: {get_color(p1m)};">{p1m:.2f}%</span></div> 
    <div><strong>6M %</strong>: <span style="color: {get_color(p6m)};">{p6m:.2f}%</span></div>
    <div><strong>1Y %</strong>: <span style="color: {get_color(p1y)};">{p1y:.2f}%</span></div>
    <div><strong>5Y %</strong>: <span style="color: {get_color(p5y)};">{p5y:.2f}%</span></div>
    <hr style='border: 1px solid #444;' />
    <div><strong>Fibonacci Level (3Y Range)</strong>: {fib_level_3y:.2f}% - {fib_comment_3y}</div>
    <div><strong>Fibonacci Level (5Y Range)</strong>: {fib_level_5y:.2f}%</div>
    <div><strong>Fibonacci Level (10Y Range)</strong>: {fib_level_10y:.2f}%</div>
    <hr style='border: 1px solid #444;' />
    </div>
    """, unsafe_allow_html=True)


# --- 6. `fetch_monthly_returns` function (corrected `yf.download` caching) ---
@st.cache_data(ttl=3600) # Cache for 1 hour
def fetch_monthly_returns(ticker):
    st.markdown(f"<p style='color: gray; font-size: 12px;'>Monthly returns data last fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)
    
    data = yf.download(ticker, period="10y", interval="1d", progress=False) # Data fetching here
    
    if data.empty:
        st.error(f"Could not fetch data for {ticker}")
        return pd.DataFrame()

    monthly_data = data['Close'].resample('M').ffill()
    monthly_returns = monthly_data.pct_change().dropna()

    if isinstance(monthly_returns, pd.Series):
        df = monthly_returns.to_frame(name='Monthly Return')
    else:
        df = monthly_returns.rename(columns={monthly_returns.columns[0]: 'Monthly Return'})

    df['Year'] = df.index.year
    df['Month'] = df.index.month

    return df

# --- 7. `analyze_monthly_performance` (no caching needed here, it processes cached data) ---
def analyze_monthly_performance(monthly_returns):
    current_year = datetime.now().year
    current_month = datetime.now().month # This will be the month you are running the app in

    # Adjusting to get the last *complete* month's performance if running mid-month,
    # or the current month's performance if you expect it to update intraday.
    # For a refresh button, it makes sense to get the latest available.
    
    # Get the last entry that is not in the current future
    filtered_data = monthly_returns[monthly_returns.index <= pd.Timestamp.now().to_period('M').start_time]

    current_month_data = filtered_data[
        (filtered_data['Year'] == current_year) & 
        (filtered_data['Month'] == current_month)
    ]

    if current_month_data.empty:
        # If current month data is empty, try to get the last available full month
        if not filtered_data.empty:
            last_month_data = filtered_data.iloc[-1]
            current_performance = last_month_data['Monthly Return']
            # Optionally update category to reflect it's for the last complete month
            # category = 'Last Month'
        else:
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

# --- 8. `display_monthly_performance` (no caching needed here) ---
def display_monthly_performance(ticker, title):
    monthly_returns = fetch_monthly_returns(ticker) # Calls the cached function
    if monthly_returns.empty or 'Monthly Return' not in monthly_returns.columns:
        st.error(f"Could not fetch monthly data for {ticker}")
        return

    current_performance, historical_max, historical_min, category = analyze_monthly_performance(monthly_returns)

    st.subheader(f"{title} - Monthly Performance")
    if current_performance is not None:
        colorM = 'orange' # Default
        if current_performance > 0:
            colorM = 'green'
        elif current_performance < 0:
            colorM = 'red'

        st.markdown(f"<span style='color:{colorM}; font-size:18px;'><strong>Current Month Performance</strong>: {current_performance * 100:.2f}%</span>", unsafe_allow_html=True)
        st.write(f"**Historical Max Monthly Return**: {historical_max * 100:.2f}%")
        st.write(f"**Historical Min Monthly Return**: {historical_min * 100:.2f}%")
        
        # Display category with color
        cat_color = 'orange'
        if category == 'Highest':
            cat_color = 'green'
        elif category == 'Lowest':
            cat_color = 'red'
        st.markdown(f"<span style='color:{cat_color};'>**Category**: {category}</span>", unsafe_allow_html=True)
    else:
        st.write("No data available for the current month.")

# --- 9. `display_yearly_performance` function (Now with `@st.cache_data`) ---
@st.cache_data(ttl=3600) # Cache for 1 hour
def display_yearly_performance(ticker, title):
    st.markdown(f"<p style='color: gray; font-size: 12px;'>Yearly returns data last fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)
    
    # Fetch historical data for the past 10 years
    data = yf.download(ticker, period="10y", interval="1d", progress=False)
    if data.empty:
        st.error(f"Could not fetch data for {ticker}")
        return

    # Resample to yearly frequency and calculate yearly returns
    yearly_data = data['Close'].resample('Y').ffill()
    yearly_returns = yearly_data.pct_change().dropna()
    yearly_returns.index = yearly_returns.index.year

    if isinstance(yearly_returns, pd.Series):
        yearly_returns = yearly_returns.to_frame()
        yearly_returns.columns = ['Yearly Return']
    else:
        yearly_returns.columns = ['Yearly Return']

    current_year = datetime.now().year
    
    # Get current year's performance
    current_performance = None
    if current_year in yearly_returns.index:
        current_performance = yearly_returns.loc[current_year, 'Yearly Return']
    # If the current year's return is not fully available yet, calculate YTD explicitly
    elif not data.empty:
        start_of_current_year = pd.Timestamp(current_year, 1, 1)
        current_year_data = data['Close'][data['Close'].index >= start_of_current_year]
        if not current_year_data.empty and current_year_data.iloc[0] != 0:
            current_performance = (current_year_data.iloc[-1] / current_year_data.iloc[0]) - 1

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
        color = 'orange'
        if current_performance > 0:
            color = 'green'
        elif current_performance < 0:
            color = 'red'

        st.markdown(f"<span style='color:{color}; font-size:18px;'><strong>Current Year Performance</strong>: {current_performance * 100:.2f}%</span>", unsafe_allow_html=True)
        st.write(f"**Historical Max Yearly Return**: {historical_max * 100:.2f}%")
        st.write(f"**Historical Min Yearly Return**: {historical_min * 100:.2f}%")
        
        # Display category with color
        cat_color_y = 'orange'
        if category == 'Highest':
            cat_color_y = 'green'
        elif category == 'Lowest':
            cat_color_y = 'red'
        st.markdown(f"<span style='color:{cat_color_y};'>**Category**: {category}</span>", unsafe_allow_html=True)
    else:
        st.write("No data available for the current year.")


# --- 10. Displaying the indicators and performance sections ---
st.write("---") # Separator for better layout

# Display market indicators in columns
with st.expander("📈 Market Indicators (S&P 500 & Nasdaq 100)", expanded=True):
    col1_ind, col2_ind = st.columns(2)
    with col1_ind:
        show_indicators(tickers["S&P 500"], "S&P 500 Indicators")
    with col2_ind:
        show_indicators(tickers["Nasdaq 100"], "Nasdaq 100 Indicators")

st.write("---") # Another separator

st.title("Market Performance Analysis - Last 10 Years")

# Display monthly performance in columns
col1_mon, col2_mon = st.columns(2)
with col1_mon:
    with st.expander("📈 S&P 500 Monthly Performance", expanded=True):
        display_monthly_performance(tickers["S&P 500"], "S&P 500")

with col2_mon:
    with st.expander("📈 Nasdaq 100 Monthly Performance", expanded=True):
        display_monthly_performance(tickers["Nasdaq 100"], "Nasdaq 100")

st.write("---") # Another separator

# Display yearly performance in columns
col1_year, col2_year = st.columns(2)
with col1_year:
    with st.expander("📈 S&P 500 Yearly Performance", expanded=True):
        display_yearly_performance(tickers["S&P 500"], "S&P 500")

with col2_year:
    with st.expander("📈 Nasdaq 100 Yearly Performance", expanded=True):
        display_yearly_performance(tickers["Nasdaq 100"], "Nasdaq 100")