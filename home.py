import streamlit as st
from utils.utils import get_vix_data, create_vix_gauge

# Set page config early
st.set_page_config(page_title="Finance Dashboard", layout="wide")

# --- Login functionality ---

USERNAME = "stockanalyser"
PASSWORD = "stockanalyser"

def login():
    st.title("🔐 Please Log In")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state["logged_in"] = True
            st.success("Logged in successfully!")
            st.experimental_rerun()  # Rerun to load main page
        else:
            st.error("Incorrect username or password")

# Initialize login state
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    # --- Main app content ---
    st.title("📁 Welcome to Your Finance App")

    # VIX Data Section
    st.header("🧭 Market Sentiment Gauge (VIX)")

    # Refresh button
    refresh = st.button("🔄 Refresh VIX Data")

    # Cache for 24h unless manually refreshed
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
            # Show current VIX value inside left col
            st.success(f"**Current VIX: {vix_value:.2f}**")
        else:
            st.error("Could not load VIX data. Please try again later.")

    with right_col:
        st.markdown('<div style="height: 85px;"></div>', unsafe_allow_html=True)  # Adds 85px of vertical space
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