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

st.markdown(
    """
    <style>
    .custom-font {
        font-size: 24px;  /* Adjust this value to your preferred font size */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #333333;
    }
    .divider {
        border-left: 3px solid orange;
        height: 24px;
        margin: 6px 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Format helpers
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_percent(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"
def format_ratio(val): return f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"

with st.expander("🔍 Compare Stocks", expanded=True):
    # Select stocks first in 3 columns
    label_col, col1, col2, col3 = st.columns([3, 3, 3, 3])
    selections = []

    for i, col in enumerate([col1, col2, col3]):
        with col:
            selected = st.selectbox("Search", options, key=f"search_{i}")
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

    # Now render comparison rows, one row per metric, 4 columns (label + 3 stocks)
    for metric_name, value_func in metrics.items():
        label_col, c1, c2, c3 = st.columns([3, 3, 3, 3])  # label column wider

        # Label with white font and bold
        label_col.markdown(
            f"<div class='custom-font' style='font-weight:bold; color:white;'>{metric_name}</div>",
            unsafe_allow_html=True
        )

        # Iterate through selected stocks columns
        for idx, col in enumerate([c1, c2, c3]):
            with col:
                val = "—"
                if len(selections) > idx and selections[idx]:
                    try:
                        val = value_func(selections[idx])
                    except Exception:
                        val = "N/A"

                # Show val with orange left border as divider and white font color
                st.markdown(
                    f"""
                    <div style='
                        background-color: transparent;
                        border-left: 4px solid orange;
                        border-right: 4px solid orange;
                        border-top: 4px solid orange;
                        border-bottom: 4px solid orange;
                        border-radius: 12px;
                        padding: 6px 12px;
                        color: white;
                        font-size: 24px;
                        min-height: 32px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin-bottom: 12px;
                    '>{val}</div>
                    """,
                    unsafe_allow_html=True
                )

