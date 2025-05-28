import streamlit as st
import time
from utils.utils import get_vix_data, create_vix_gauge, login, get_last_thursday, load_aaii_sentiment
from PIL import Image

# Page setup
st.set_page_config(page_title="Finance Dashboard", layout="wide")

# Constants
SESSION_TIMEOUT_SECONDS = 600  # 10 minutes

# Get secrets (make sure your secrets are set in Streamlit Cloud)
USERNAME = st.secrets["login"]["username"]
PASSWORD = st.secrets["login"]["password"]

# Initialize session state keys if not present
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "last_activity" not in st.session_state:
    st.session_state["last_activity"] = time.time()

# Authentication & timeout check only on Home page
if st.session_state["authenticated"]:
    # Check session timeout
    now = time.time()
    if now - st.session_state["last_activity"] > SESSION_TIMEOUT_SECONDS:
        st.session_state["authenticated"] = False
        st.warning("Session expired. Please log in again.")
        st.experimental_rerun()
    else:
        st.session_state["last_activity"] = now

    # User is authenticated — show Home content
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
    
    with st.expander("🏢 Indicador AAII de Mercado", expanded=True):
        # Get key for caching
        thursday_key = get_last_thursday()

        # Load AAII data
        df = load_aaii_sentiment(thursday_key)

        # Display logic (chart, metrics, etc.)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        col1, col2, col3 = st.columns(3)
        col1.metric("📈 Bullish", f"{latest['Bullish']}%", f"{latest['Bullish'] - prev['Bullish']:+.1f}%")
        col2.metric("📊 Neutral", f"{latest['Neutral']}%", f"{latest['Neutral'] - prev['Neutral']:+.1f}%")
        col3.metric("📉 Bearish", f"{latest['Bearish']}%", f"{latest['Bearish'] - prev['Bearish']:+.1f}%")
else:
    # Not authenticated — show login and stop further execution
    st.write("🔐 Please log in to continue.")
    login(USERNAME, PASSWORD)
    st.stop()