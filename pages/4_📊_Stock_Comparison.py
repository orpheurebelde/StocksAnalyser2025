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

# Helper functions
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_percent(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"
def format_ratio(val): return f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"

st.markdown("""
<style>
.custom-font {
    font-size: 24px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: white;
    font-weight: bold;
    text-align: right;
}
.rounded-box {
    background-color: transparent;
    border: 3px solid orange;
    border-radius: 14px;
    padding: 10px 14px;
    color: white;
    font-size: 20px;
    min-height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 18px;
}
.sticky-container {
    position: sticky;
    top: 3.5rem;
    background-color: #0e1117;
    z-index: 999;
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #444;
}
</style>
""", unsafe_allow_html=True)

# Sticky Search Bar
with st.expander("🔍 Search Stocks for Comparison", expanded=True):
    st.markdown("<div class='sticky-container'>", unsafe_allow_html=True)

    label_col, col1, col2, col3 = st.columns([2.5, 3, 3, 3])
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

    st.markdown("</div>", unsafe_allow_html=True)

# Comparison Metrics
with st.expander("🔍 Stocks Metrics and Valuations", expanded=True):
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

    for metric_name, value_func in metrics.items():
        label_col, c1, c2, c3 = st.columns([2.5, 3, 3, 3])

        label_col.markdown(
            f"<div class='custom-font'>{metric_name}</div>",
            unsafe_allow_html=True
        )

        for idx, col in enumerate([c1, c2, c3]):
            with col:
                val = "—"
                if len(selections) > idx and selections[idx]:
                    try:
                        val = value_func(selections[idx])
                    except Exception:
                        val = "N/A"

                st.markdown(
                    f"<div class='rounded-box'>{val}</div>",
                    unsafe_allow_html=True
                )

