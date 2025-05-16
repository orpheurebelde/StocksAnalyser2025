import streamlit as st
from utils.utils import get_vix_data, create_vix_gauge

st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("📁 Welcome to Your Finance App")

# VIX Data Section
st.header("🧭 Market Sentiment Gauge (VIX)")

# Refresh button
refresh = st.button("🔄 Refresh VIX Data")

# Cache for 24h unless manually refreshed
@st.cache_data(ttl=86400)
def fetch_vix_cached():
    return get_vix_data()

if refresh:
    st.cache_data.clear()

vix_value = fetch_vix_cached()

# Create layout
left_col, right_col = st.columns([2, 1])  # Wider for chart

with left_col:
    if vix_value is not None:
        st.plotly_chart(create_vix_gauge(vix_value), use_container_width=True)
        st.success(f"**Current VIX: {vix_value:.2f}**")  # ✅ moved inside left_col
    else:
        st.error("Could not load VIX data. Please try again later.")

with right_col:
    st.markdown(
        """
        <div style="
            display: flex;
            flex-direction: column;
            justify-content: center;
            height: 100%;
        ">
            <div style="
                margin: auto;
                text-align: justify;
                max-width: 250px;
            ">
                <h4 style="text-align: center;">Gauge Zones</h4>
                <p><b>00–12</b>: 🟢 <i>Extreme Greed</i></p>
                <p><b>12–20</b>: 🟡 <i>Greed</i></p>
                <p><b>20–28</b>: ⚪️ <i>Neutral</i></p>
                <p><b>28–35</b>: 🟠 <i>Fear</i></p>
                <p><b>35–50</b>: 🔴 <i>Extreme Fear</i></p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )