import pandas as pd
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from utils.utils import get_stock_info, monte_carlo_simulation, fetch_data
import time

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
        st.experimental_rerun()
    else:
        st.session_state["last_activity"] = now

if not st.session_state["authenticated"]:
    st.error("Unauthorized. Please go to the home page and log in.")
    st.stop()

# Load stock list
@st.cache_data
def load_stock_list():
    df = pd.read_csv("stocks_list.csv", sep=";")
    df["Display"] = df["Ticker"] + " - " + df["Name"]
    return df

# UI layout
st.title("📁 Stock Price Simulations")

stock_df = load_stock_list()
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

if selected_display != "Select a stock...":
    selected_ticker = selected_display.split(" - ")[0]
    data, info = fetch_data(selected_ticker)

    st.title(f"🎲 Monte Carlo Simulations - {selected_ticker}")

    # User inputs
    n_simulations = st.slider("Number of Simulations", 100, 10000, 5000)
    n_years = st.slider("Projection Period (Years)", 0, 10, 3)
    n_months = st.slider("Additional Months", 0, 11, 1)
    log_normal = st.checkbox("Use Log-Normal Distribution")
    manual_vol = st.checkbox("Manually Adjust Volatility")

    volatility = None
    if manual_vol:
        volatility = st.slider("Set Volatility (%)", 0.5, 5.0, data['Close'].pct_change().std() * 100) / 100

    total_days = (n_years * 252) + (n_months * 21)
    simulations = monte_carlo_simulation(data, n_simulations, total_days, log_normal, volatility)

    last_price = data['Close'].iloc[-1]
    final_prices = simulations[:, -1]

    # Scenario categorization
    mean_price = np.mean(final_prices)
    percentile_5 = np.percentile(final_prices, 5)
    percentile_25 = np.percentile(final_prices, 25)
    percentile_50 = np.percentile(final_prices, 50)
    percentile_95 = np.percentile(final_prices, 95)
    prob_price_increase = np.sum(final_prices > last_price) / len(final_prices) * 100

    st.markdown("### 📊 Simulation Results")
    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2.5, 2.5, 2])

    col1.metric("🔹 Current Price", f"${last_price:.2f}")
    col2.metric("📈 Mean Price", f"${mean_price:.2f}")
    col3.metric("🐻 Bear Case (5%)", f"${percentile_5:.2f}")
    col4.metric("📉 Discount Case (25%)", f"${percentile_25:.2f}")
    col5.metric("⚖️ Neutral Case (50%)", f"${percentile_50:.2f}")
    col6.metric("🚀 Bull Case (95%)", f"${percentile_95:.2f}")

    st.markdown(f"**📊 Probability of Price Increase: {prob_price_increase:.2f}%**")

    # Plotting simulations
    st.subheader("Simulated Price Paths")
    fig, ax = plt.subplots(figsize=(10, 6))
    sample_size = min(n_simulations, 100)
    sample_indices = np.random.choice(n_simulations, sample_size, replace=False)

    for i in sample_indices:
        ax.plot(simulations[i], alpha=0.3, linewidth=0.8)

    # Add average, bull, and bear curves
    mean_path = np.mean(simulations, axis=0)
    percentile_5_path = np.percentile(simulations, 5, axis=0)
    percentile_95_path = np.percentile(simulations, 95, axis=0)
    percentile_50_path = np.percentile(simulations, 50, axis=0)

    ax.plot(mean_path, color="black", linewidth=2, label="Mean Projection")
    ax.plot(percentile_50_path, color="orange", linestyle="--", linewidth=1.8, label="Neutral Scenario (50%)")
    ax.plot(percentile_95_path, color="green", linestyle="--", linewidth=1.8, label="Bull Scenario (95%)")
    ax.plot(percentile_5_path, color="red", linestyle="--", linewidth=1.8, label="Bear Scenario (5%)")

    ax.fill_between(range(simulations.shape[1]), percentile_5_path, percentile_95_path, color='gray', alpha=0.2, label="5%-95% Confidence Interval")
    ax.set_title("Monte Carlo Simulated Price Paths")
    ax.set_xlabel("Days")
    ax.set_ylabel("Price")
    ax.legend()

    with st.expander("📊 Click to Expand Simulation Chart"):
        st.pyplot(fig)
else:
    st.info("Please select a stock to begin the simulation.")