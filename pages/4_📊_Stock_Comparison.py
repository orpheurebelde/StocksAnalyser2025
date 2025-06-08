import streamlit as st
import pandas as pd
import time
from utils.utils import get_stock_info

# Page config
st.set_page_config(page_title="Stock Comparison", layout="wide")

# Session management
SESSION_TIMEOUT_SECONDS = 3600
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "last_activity" not in st.session_state:
    st.session_state["last_activity"] = time.time()

if st.session_state["authenticated"]:
    now = time.time()
    if now - st.session_state["last_activity"] > SESSION_TIMEOUT_SECONDS:
        st.session_state["authenticated"] = False
        st.warning("Session expired.")
        st.rerun()
    else:
        st.session_state["last_activity"] = now

if not st.session_state["authenticated"]:
    st.error("Unauthorized. Please go to the home page and log in.")
    st.stop()

st.title("📊 Stock Comparison")

# Load stock list
@st.cache_data
def load_stock_list():
    df = pd.read_csv("stocks_list.csv", sep=";")
    df["Display"] = df["Ticker"] + " - " + df["Name"]
    return df.sort_values(by="Display")

stock_df = load_stock_list()
options = ["Select a stock..."] + stock_df["Display"].tolist()

# Format helpers
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_percent(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"
def format_ratio(val): return f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"

# Expander with 3 columns for stock comparison
with st.expander("🔍 Compare Stocks", expanded=True):
    col1, col2, col3 = st.columns(3)

    selections = []
    for col in [col1, col2, col3]:
        with col:
            selected = st.selectbox("Search", options)
            if selected != "Select a stock...":
                ticker = stock_df.loc[stock_df["Display"] == selected, "Ticker"].values[0]
                info = get_stock_info(ticker)
                selections.append(info)
            else:
                selections.append(None)

# Define the metrics to display
metrics = {
    "Trailing PE": lambda info: format_ratio(info.get("trailingPE")),
    "Forward PE": lambda info: format_ratio(info.get("forwardPE")),
    "PEG Ratio": lambda info: format_ratio(info.get("pegRatio")),
    "Price/Book": lambda info: format_ratio(info.get("priceToBook")),
    "Price/Sales": lambda info: format_ratio(info.get("priceToSalesTrailing12Months")),
    "Free Cash Flow": lambda info: format_currency(info.get("freeCashflow")),
    "ROE": lambda info: format_percent(info.get("returnOnEquity")),
    "ROA": lambda info: format_percent(info.get("returnOnAssets")),
    "EBITDA": lambda info: format_currency(info.get("ebitda")),
    "Trailing EPS": lambda info: format_currency_dec(info.get("trailingEps")),
    "Forward EPS": lambda info: format_currency_dec(info.get("forwardEps")),
    "Gross Margin": lambda info: format_percent(info.get("grossMargins")),
    "Operating Margin": lambda info: format_percent(info.get("operatingMargins")),
    "Profit Margin": lambda info: format_percent(info.get("profitMargins")),
    "Net Income": lambda info: format_currency(info.get("netIncomeToCommon")),
    "Total Revenue": lambda info: format_currency(info.get("totalRevenue")),
    "Total Cash": lambda info: format_currency(info.get("totalCash")),
    "Total Debt": lambda info: format_currency(info.get("totalDebt")),
    "Current Ratio": lambda info: format_ratio(info.get("currentRatio"))
}

# Display the metrics in aligned rows for each selected stock
if any(selections):
    st.markdown("### 📈 Financial Metrics Comparison")
    for metric_name, formatter in metrics.items():
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**{metric_name}**")
            st.write(formatter(selections[0]) if selections[0] else "-")
        with col2:
            st.write(" ")
            st.write(formatter(selections[1]) if selections[1] else "-")
        with col3:
            st.write(" ")
            st.write(formatter(selections[2]) if selections[2] else "-")
