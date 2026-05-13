import streamlit as st

def apply_theme():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@400;500;700&display=swap');

        /* Background and Typography */
        .stApp {
            background-color: #0a0a0f;
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(79, 172, 254, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 85% 30%, rgba(192, 132, 252, 0.08) 0%, transparent 50%);
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Inter', sans-serif;
        }

        /* Headers */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Outfit', sans-serif !important;
            letter-spacing: -0.02em;
            color: #ffffff;
        }

        h1 {
            background: linear-gradient(135deg, #00f2fe, #4facfe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            padding-bottom: 1rem;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: rgba(18, 18, 26, 0.6) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
        }

        /* Buttons */
        .stButton > button {
            background: linear-gradient(135deg, #4facfe, #c084fc) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-family: 'Outfit', sans-serif !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3) !important;
        }

        .stButton > button:hover {
            opacity: 0.9 !important;
            transform: scale(1.02) !important;
            box-shadow: 0 6px 20px rgba(192, 132, 252, 0.4) !important;
        }

        /* Expander (Glass Panels) */
        .streamlit-expanderHeader {
            background: rgba(18, 18, 26, 0.6) !important;
            backdrop-filter: blur(12px) !important;
            border-radius: 8px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: #ffffff !important;
        }

        [data-testid="stExpander"] {
            border: none !important;
            background: transparent !important;
        }

        /* Inputs */
        input, select, textarea, div[data-baseweb="select"] {
            background: rgba(0,0,0,0.3) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: white !important;
            border-radius: 8px !important;
        }
        
        div[data-baseweb="select"] > div {
            background: rgba(0,0,0,0.3) !important;
            color: white !important;
        }

        /* Metrics */
        [data-testid="stMetricValue"] {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 700 !important;
            color: #00f2fe !important;
        }
        
        [data-testid="stMetricLabel"] {
            color: #94a3b8 !important;
        }

        /* Dataframes */
        .stDataFrame {
            background: rgba(18, 18, 26, 0.6) !important;
            backdrop-filter: blur(12px) !important;
            border-radius: 8px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
        }
        </style>
    """, unsafe_allow_html=True)
