import streamlit as st
from utils import get_vix_data, create_vix_gauge

st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("📁 Welcome to Your Finance App")

# Refresh button
refresh = st.button("🔄 Refresh VIX Data")

# Cache for 24h unless manually refreshed
@st.cache_data(ttl=86400)
def fetch_vix_cached():
    return get_vix_data()

if refresh:
    st.cache_data.clear()

vix_value = fetch_vix_cached()

if vix_value is not None:
    st.plotly_chart(create_vix_gauge(vix_value), use_container_width=True)
    st.success(f"Current VIX: **{vix_value:.2f}**")
else:
    st.error("Could not load VIX data. Please try again later.")

# Zone legend
st.markdown("""
### Gauge Zones
- **0–12**: 🟢 *Extreme Greed*
- **12–20**: 🟡 *Greed*
- **20–28**: ⚪️ *Neutral*
- **28–35**: 🟠 *Fear*
- **35–50**: 🔴 *Extreme Fear*
""")
