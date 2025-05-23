import streamlit as st
import time
from utils.utils import get_vix_data, create_vix_gauge, login

# Page setup
st.set_page_config(page_title="Finance Dashboard", layout="wide")

# Constants
SESSION_TIMEOUT_SECONDS = 600  # 10 minutes

# Get secrets
USERNAME = st.secrets["login"]["username"]
PASSWORD = st.secrets["login"]["password"]

# Initialize session tracking
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "last_activity" not in st.session_state:
    st.session_state["last_activity"] = time.time()

# Check for timeout if already logged in
if st.session_state["authenticated"]:
    now = time.time()
    if now - st.session_state["last_activity"] > SESSION_TIMEOUT_SECONDS:
        st.session_state["authenticated"] = False
        st.warning("Session expired. Please log in again.")
        st.experimental_rerun()
    else:
        st.session_state["last_activity"] = now

# Prompt login if not authenticated
if not st.session_state["authenticated"]:
    login(USERNAME, PASSWORD)
    st.stop()

# ---------------- Main App Content ---------------- #

st.title("📁 Home | Análise de Ações e Mercado")

# VIX Indicator Section
st.header("🧭 Indicador de Volatilidade (VIX)")
refresh = st.button("🔄 Refresh VIX")

@st.cache_data
def fetch_vix_cached():
    return get_vix_data()

if refresh:
    st.cache_data.clear()

vix_value = fetch_vix_cached()

with st.expander("🏢 Indicador de Sentimento de Mercado", expanded=True):
    left_col, right_col = st.columns([2, 1])

    with left_col:
        if vix_value is not None:
            st.plotly_chart(create_vix_gauge(vix_value), use_container_width=True)
        else:
            st.error("Could not load VIX data. Please try again later.")

    with right_col:
        st.markdown('<div style="height: 85px;"></div>', unsafe_allow_html=True)
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
# ---------------- End of App Content ---------------- #