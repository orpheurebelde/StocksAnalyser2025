import streamlit as st
import time
from utils.utils import get_vix_data, create_vix_gauge, login, load_aaii_sentiment
import plotly.graph_objects as go

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
    
    with st.expander("📊 AAII Sentiment Survey"):
        # Select last 7 rows (dates) and keep necessary columns
        last_7 = load_aaii_sentiment()
        last_7 = last_7.tail(7).copy()

        # If 'Date' is index, reset it for plotting
        if last_7.index.name == 'Date' or 'Date' not in last_7.columns:
            last_7 = last_7.reset_index()

        # Make sure columns are floats (remove '%' if present, but you said it's already cleaned)
        # For safety:
        for col in ['Bullish', 'Neutral', 'Bearish']:
            last_7[col] = last_7[col].astype(float)

        # Create stacked bar chart
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=last_7['Date'],
            y=last_7['Bearish'],
            name='Bearish',
            marker_color='red'
        ))
        fig.add_trace(go.Bar(
            x=last_7['Date'],
            y=last_7['Neutral'],
            name='Neutral',
            marker_color='gray'
        ))
        fig.add_trace(go.Bar(
            x=last_7['Date'],
            y=last_7['Bullish'],
            name='Bullish',
            marker_color='green'
        ))

        fig.update_layout(
            barmode='stack',
            title='AAII Sentiment Survey - Last 7 Reports',
            yaxis=dict(title='Percentage (%)', ticksuffix='%'),
            xaxis=dict(title='Date'),
            legend=dict(title='Sentiment'),
            template='plotly_white',
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)
else:
    # Not authenticated — show login and stop further execution
    st.write("🔐 Please log in to continue.")
    login(USERNAME, PASSWORD)
    st.stop()