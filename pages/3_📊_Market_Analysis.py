import streamlit as st
import yfinance as yf
import pandas as pd
from utils.utils import compute_fibonacci_level, compute_rsi, compute_macd
from datetime import datetime
import plotly.graph_objects as go

# --- 1. Set page configuration ---
st.set_page_config(
    page_title="Market Analysis",
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
@st.cache_data(ttl=14400) # Cache for 1 hour; adjust as needed
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
        # 1. Define the start of the year in UTC
        current_year_start = pd.Timestamp(datetime.now().year, 1, 1, tz='UTC')

        # 2. Convert the 'close' index to UTC.
        #    If close.index is already tz-aware (which it is, causing your error),
        #    use .tz_convert() to change its timezone.
        #    If it happened to be naive (unlikely for yfinance.history), you'd use tz_localize first.
        #    Since it's already tz-aware, tz_convert is the correct method.
        close_index_utc = close.index.tz_convert('UTC')

        # 3. Use the UTC-converted index for your comparison
        start_price_series = close.loc[close_index_utc >= current_year_start]

        start_price = start_price_series.iloc[0] if not start_price_series.empty else close.iloc[0]
    except Exception as e:
        # Catching the specific error type can be more precise, but general Exception works.
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
    <div>
    <div style='height: 20px;'></div>
    </div>
    </div>
    """, unsafe_allow_html=True)


# --- 6. `fetch_monthly_returns` function (corrected `yf.download` caching) ---
# --- MODIFIED `fetch_monthly_returns` function ---
# Now returns both the full monthly_returns DataFrame AND the daily close prices
@st.cache_data(ttl=14400) # Cache for 1 hour; adjust as needed
def fetch_monthly_returns(ticker):
    st.markdown(f"<p style='color: gray; font-size: 12px;'>Monthly returns data last fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)
    
    # Fetch daily data for a sufficiently long period
    data = yf.download(ticker, period="10y", interval="1d", progress=False) 
    
    if data.empty:
        st.error(f"Could not fetch data for {ticker}")
        return pd.DataFrame(), pd.Series() # Return empty DataFrame and Series

    # Resample to monthly frequency (end-of-month prices) for historical monthly returns
    monthly_data = data['Close'].resample('M').ffill()
    monthly_returns = monthly_data.pct_change().dropna()

    if isinstance(monthly_returns, pd.Series):
        df = monthly_returns.to_frame(name='Monthly Return')
    else:
        df = monthly_returns.rename(columns={monthly_returns.columns[0]: 'Monthly Return'})

    df['Year'] = df.index.year
    df['Month'] = df.index.month

    # Return the DataFrame of historical monthly returns AND the daily close prices
    return df, data['Close']


# 7.--- MODIFIED `analyze_monthly_performance` function ---
# It now takes only the monthly_returns_df
def analyze_monthly_performance(monthly_returns_df):
    if monthly_returns_df.empty:
        return None, None, None, None, 'No Data' # current_perf, last_perf, hist_max, hist_min, category_current

    # The last entry in monthly_returns_df represents the performance
    # from the last day of the previous month to the latest available day of the current month.
    current_month_perf = monthly_returns_df.iloc[-1]['Monthly Return']

    # The second-to-last entry represents the last complete month's performance.
    # Ensure there are at least two months of data before trying to access iloc[-2]
    last_month_perf = None
    if len(monthly_returns_df) >= 2:
        last_month_perf = monthly_returns_df.iloc[-2]['Monthly Return']

    # Historical max/min (consider all fetched monthly data, including current partial)
    historical_max = monthly_returns_df['Monthly Return'].max()
    historical_min = monthly_returns_df['Monthly Return'].min()

    # Determine category for current month's performance
    category_current = 'No Data'
    if current_month_perf is not None:
        if current_month_perf > historical_max:
            category_current = 'Highest (Current Month)'
        elif current_month_perf < historical_min:
            category_current = 'Lowest (Current Month)'
        else:
            category_current = 'Neutral (Current Month)'

    # Return current month's performance, last month's performance, historical max/min, and current category
    return current_month_perf, last_month_perf, historical_max, historical_min, category_current


# 8.--- MODIFIED `display_monthly_performance` function ---
def display_monthly_performance(ticker, title):
    # Fetch only monthly_returns_df, we don't need daily_close_prices here anymore
    # Use _ to discard the second return value (daily_close_prices) if it's not used here
    monthly_returns_df, _ = fetch_monthly_returns(ticker)
    
    if monthly_returns_df.empty or 'Monthly Return' not in monthly_returns_df.columns:
        st.error(f"Could not fetch data for {ticker}")
        return

    # Call the modified analyze_monthly_performance
    current_performance, last_month_performance, historical_max, historical_min, category_current = analyze_monthly_performance(monthly_returns_df)

    st.subheader(f"{title} - Monthly Performance")

    # Display Last Month Performance
    if last_month_performance is not None:
        color_last_month = 'orange'
        if last_month_performance > 0:
            color_last_month = 'green'
        elif last_month_performance < 0:
            color_last_month = 'red'
        st.markdown(
            f"<span style='color:{color_last_month}; font-size:18px;'><strong>Last Month Performance</strong>: {last_month_performance * 100:.2f}%</span>",
            unsafe_allow_html=True
        )
    else:
        st.write("No data available for the last complete month.")

    # Display Current Month Performance
    if current_performance is not None:
        color_current_month = 'orange'
        if current_performance > 0:
            color_current_month = 'green'
        elif current_performance < 0:
            color_current_month = 'red'
        st.markdown(
            f"<span style='color:{color_current_month}; font-size:18px;'><strong>Current Month Performance</strong>: {current_performance * 100:.2f}%</span>",
            unsafe_allow_html=True
        )
        st.write(f"**Historical Max Monthly Return**: {historical_max * 100:.2f}%")
        st.write(f"**Historical Min Monthly Return**: {historical_min * 100:.2f}%")
        
        cat_color = 'orange'
        if 'Highest' in category_current:
            cat_color = 'green'
        elif 'Lowest' in category_current:
            cat_color = 'red'
        st.markdown(f"<span style='color:{cat_color};'>**Category**: {category_current}</span>", unsafe_allow_html=True)
    else:
        st.write("No data available for the current month.")

# 9.--- MODIFIED `display_yearly_performance` function ---
@st.cache_data(ttl=3600)
def display_yearly_performance(ticker, title):
    st.markdown(
        f"<p style='color: gray; font-size: 12px;'>Yearly returns data last fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        unsafe_allow_html=True
    )

    data = yf.download(ticker, period="10y", interval="1d", progress=False)
    if data.empty or 'Close' not in data.columns:
        st.error(f"Not enough data to calculate yearly performance for {ticker}.")
        return

    # Ensure timezone
    if data.index.tz is None:
        data.index = data.index.tz_localize('America/New_York')
    else:
        data.index = data.index.tz_convert('America/New_York')

    data = data.sort_index()

    #Calculate yearly returns
    # Resample to yearly frequency (end-of-year prices) for historical yearly returns
    # ✅ Calculate yearly returns as (last - first) / first for each year
    try:
        year_open = data['Close'].resample('Y').first()
        year_close = data['Close'].resample('Y').last()
        yearly_returns = (year_close - year_open) / year_open
        yearly_returns.index = yearly_returns.index.year  # Make sure the index is integer year
    except Exception as e:
        st.error(f"Failed to calculate yearly returns: {e}")
        return yearly_returns

    current_year = datetime.now().year
    last_year = current_year - 1

    # Calculate YTD performance
    current_performance = None
    ytd_data = data.loc[data.index >= pd.Timestamp(f"{current_year}-01-01", tz='America/New_York'), 'Close']
    if not ytd_data.empty:
        start_price = ytd_data.iloc[0]
        end_price = ytd_data.iloc[-1]
        try:
            start_price = float(start_price)
            end_price = float(end_price)
            if start_price != 0:
                current_performance = (end_price / start_price) - 1
                current_performance = float(current_performance)
        except Exception as e:
            st.error(f"Error calculating YTD performance values: {e}")

    # Fallback to yearly return if needed
    if current_performance is None and current_year in yearly_returns.index:
        current_performance = float(yearly_returns.loc[current_year])

    # Last year performance
    if last_year in yearly_returns.index:
        last_year_perf = float(yearly_returns.loc[last_year])
    else:
        last_year_perf = float('nan')
        st.warning(f"No data for last year ({last_year}).")

    # Historical stats (exclude current year)
    completed_years = yearly_returns[yearly_returns.index < current_year]
    historical_max = float(completed_years.max()) if not completed_years.empty else None
    historical_min = float(completed_years.min()) if not completed_years.empty else None

    # Classify category
    if current_performance is None:
        category = 'No Data'
    elif historical_max is not None and current_performance > historical_max:
        category = 'Highest'
    elif historical_min is not None and current_performance < historical_min:
        category = 'Lowest'
    else:
        category = 'Neutral'

    # --- Display Section ---
    st.subheader(f"{title} - Yearly Performance")

    if pd.notna(last_year_perf):
        color = 'green' if last_year_perf > 0 else 'red' if last_year_perf < 0 else 'orange'
        st.markdown(
            f"<span style='color:{color}; font-size:18px;'><strong>Last Year Performance ({last_year})</strong>: {last_year_perf * 100:.2f}%</span>",
            unsafe_allow_html=True
        )
    else:
        st.write(f"No data for last year ({last_year}).")

    if current_performance is not None:
        color = 'green' if current_performance > 0 else 'red' if current_performance < 0 else 'orange'
        cat_color = 'green' if category == 'Highest' else 'red' if category == 'Lowest' else 'orange'
        st.markdown(
            f"<span style='color:{color}; font-size:18px;'><strong>Current Year Performance ({current_year})</strong>: {current_performance * 100:.2f}%</span>",
            unsafe_allow_html=True
        )
        if historical_max is not None and historical_min is not None:
            st.write(f"**Historical Max Yearly Return**: {historical_max * 100:.2f}%")
            st.write(f"**Historical Min Yearly Return**: {historical_min * 100:.2f}%")
        st.markdown(f"<span style='color:{cat_color};'>**Category**: {category}</span>", unsafe_allow_html=True)
    else:
        st.write("No data available for the current year.")

# --- 10. Chart Returns
@st.cache_data
def get_yearly_returns(ticker: str) -> pd.Series | None:
    data = yf.download(ticker, period="max", interval="1d", progress=False)
    if data.empty:
        return None

    data = data.dropna()
    data.index = pd.to_datetime(data.index)

    year_open = data['Close'].resample('Y').first()
    year_close = data['Close'].resample('Y').last()
    yearly_returns = (year_close - year_open) / year_open
    yearly_returns.index = yearly_returns.index.year  # Convert datetime to int

    return yearly_returns

# --- 11. Displaying the indicators and performance sections ---
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

# Display yearly performance in columns
col1_year, col2_year = st.columns(2)
with col1_year:
    with st.expander("📈 S&P 500 Yearly Performance", expanded=True):
        display_yearly_performance(tickers["S&P 500"], "S&P 500")

with col2_year:
    with st.expander("📈 Nasdaq 100 Yearly Performance", expanded=True):
        display_yearly_performance(tickers["Nasdaq 100"], "Nasdaq 100")

#Plot Yearly Returns in a single chart
st.write("---")
st.subheader("📊 Yearly Returns Comparison")

sp500_yearly_returns = get_yearly_returns("^GSPC")
nasdaq_yearly_returns = get_yearly_returns("^NDX")

# Check both are valid Series
if isinstance(sp500_yearly_returns, pd.Series) and isinstance(nasdaq_yearly_returns, pd.Series):
    combined = pd.concat([
        sp500_yearly_returns.rename("S&P 500"),
        nasdaq_yearly_returns.rename("Nasdaq 100")
    ], axis=1).dropna()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=combined.index, y=combined['S&P 500'], name="S&P 500", marker_color="blue"))
    fig.add_trace(go.Bar(x=combined.index, y=combined['Nasdaq 100'], name="Nasdaq 100", marker_color="orange"))

    fig.update_layout(
        title="Yearly Returns Comparison",
        xaxis_title="Year",
        yaxis_title="Return (%)",
        barmode="group",
        template="plotly_white"
    )

    with st.expander("📈 Yearly Returns Chart"):
        st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("One of the return series is not valid.")
