import streamlit as st
import yfinance as yf
from utils.utils import get_vix_data, create_vix_gauge

# --- Set page config ---
st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("📁 Welcome to Your Finance App")

# --- Refresh button ---
refresh = st.button("🔄 Refresh VIX Data")

# Clear the cache if refresh button is clicked
if refresh:
    st.cache_data.clear()

# --- Get VIX index value ---
vix_value = get_vix_data()

# --- Show VIX gauge or error ---
if vix_value is not None:
    st.plotly_chart(create_vix_gauge(vix_value), use_container_width=True)
    st.success(f"Current VIX: **{vix_value:.2f}**")
else:
    st.error("Could not load VIX data. Please try again later.")

# --- Optional: Display guidance ---
st.markdown("""
### Gauge Zones
- **0–12**: 🟢 *Extreme Greed*
- **12–20**: 🟡 *Greed*
- **20–28**: ⚪️ *Neutral*
- **28–35**: 🟠 *Fear*
- **35–50**: 🔴 *Extreme Fear*
""")
