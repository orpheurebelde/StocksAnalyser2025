import streamlit as st 
import pandas as pd
from datetime import datetime
import yfinance as yf
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="📊 Portfolio Analysis", layout="wide")
st.title("📊 Portfolio Analysis & AI Suggestions")

uploaded_file = st.file_uploader("📁 Upload Portfolio CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file, parse_dates=["Date"], dayfirst=True, on_bad_lines='skip')
    df.columns = [col.strip() for col in df.columns]

    st.write("🧩 Columns detected in CSV:", list(df.columns))

    required_cols = {"Date", "Symbol", "Quantity", "Purchase Price", "Current Price"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
            st.error(f"Missing required columns in CSV: {missing_cols}")
            st.stop()

    # Ensure correct formats
    df["Symbol"] = df["Symbol"].str.upper().str.split('.').str[0]
    df["Investment"] = df["Quantity"] * df["Purchase Price"]
    df["Market Value"] = df["Quantity"] * df["Current Price"]
    df["Unrealized Gain (€)"] = df["Market Value"] - df["Investment"]
    df["Unrealized Gain (%)"] = (df["Unrealized Gain (€)"] / df["Investment"]) * 100
    df["Days Held"] = (pd.Timestamp.today() - df["Date"]).dt.days
    df["Year"] = df["Date"].dt.year

    # ---- Approximate Metrics ----
    df["Annualized Return"] = ((df["Current Price"] / df["Purchase Price"]) ** (365 / df["Days Held"])) - 1

    # Approximate volatility assumption (simplified: using return range as proxy)
    # You could replace this with sector average volatilities if known
    df["Approx. Volatility"] = abs(df["Annualized Return"]) * 0.6  # 60% of return as volatility proxy

    # Sharpe ratio approximation (risk-free = 0)
    df["Approx. Sharpe"] = np.where(df["Approx. Volatility"] > 0,
                                    df["Annualized Return"] / df["Approx. Volatility"],
                                    np.nan)

    # Max Drawdown estimate — without full time series, we approximate from returns
    df["Approx. Max Drawdown"] = -abs(df["Unrealized Gain (%)"]) * 0.5  # 50% of gain/loss as DD proxy

    # ---- Portfolio level metrics ----
    total_investment = df["Investment"].sum()
    weights = df["Market Value"] / df["Market Value"].sum()

    port_return = (weights * df["Annualized Return"]).sum()
    port_vol = np.sqrt((weights ** 2 * (df["Approx. Volatility"] ** 2)).sum())  # ignores correlations
    port_sharpe = port_return / port_vol if port_vol > 0 else np.nan
    port_dd = (weights * df["Approx. Max Drawdown"]).sum()

    port_metrics = pd.DataFrame({
        "Metric": ["Annualized Return", "Approx. Volatility", "Approx. Sharpe", "Approx. Max Drawdown"],
        "Portfolio Value": [port_return, port_vol, port_sharpe, port_dd]
    })

    # ---- Display ----
    with st.expander("📄 Transactions with Metrics", expanded=False):
        st.dataframe(df, use_container_width=True,
                    column_config={
                        "Purchase Price": st.column_config.NumberColumn(format="€%.2f"),
                        "Current Price": st.column_config.NumberColumn(format="€%.2f"),
                        "Investment": st.column_config.NumberColumn(format="€%.2f"),
                        "Market Value": st.column_config.NumberColumn(format="€%.2f"),
                        "Unrealized Gain (€)": st.column_config.NumberColumn(format="€%.2f"),
                        "Unrealized Gain (%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "Annualized Return": st.column_config.NumberColumn(format="%.2f%%"),
                        "Approx. Volatility": st.column_config.NumberColumn(format="%.2f%%"),
                        "Approx. Sharpe": st.column_config.NumberColumn(format="%.2f"),
                        "Approx. Max Drawdown": st.column_config.NumberColumn(format="%.2f%%")
                    })

    with st.expander("📌 Portfolio Level Approx. Metrics", expanded=True):
        st.dataframe(port_metrics, use_container_width=True,
                    column_config={"Portfolio Value": st.column_config.NumberColumn(format="%.2f")})

    st.info("ℹ️ Metrics are approximations based on purchase/current prices only — "
            "no historical price series used. Sharpe ratio and volatility are estimated, "
            "so treat them as relative indicators for rebalancing, not precise values.")

    # 2. Stock Summary Table
    summary = df.groupby("Symbol").agg({
        "Quantity": "sum",
        "Investment": "sum",
        "Market Value": "sum",
        "Unrealized Gain (€)": "sum"
    }).reset_index()
    summary["Unrealized Gain (%)"] = (summary["Unrealized Gain (€)"] / summary["Investment"]) * 100

    with st.expander("📌 Compiled Stock Summary"):
        st.dataframe(
            summary,
            use_container_width=True,
            column_config={
                "Investment": st.column_config.NumberColumn("Investment (€)", format="€%.2f"),
                "Market Value": st.column_config.NumberColumn("Market Value (€)", format="€%.2f"),
                "Unrealized Gain (€)": st.column_config.NumberColumn("Unrealized Gain (€)", format="€%.2f"),
                "Unrealized Gain (%)": st.column_config.NumberColumn("Unrealized Gain (%)", format="%.2f%%")
            }
        )

    # 3. Annual Performance Summary
    annual = df.groupby("Year").agg({
        "Investment": "sum",
        "Market Value": "sum",
        "Unrealized Gain (€)": "sum"
    }).reset_index()
    annual["Unrealized Gain (%)"] = (annual["Unrealized Gain (€)"] / annual["Investment"]) * 100

    with st.expander("📅 Annual Unrealized Performance Summary", expanded=True):
        st.dataframe(
            annual.rename(columns={
                "Investment": "Investment (€)",
                "Market Value": "Market Value (€)"
            }),
            use_container_width=True,
            column_config={
                "Investment (€)": st.column_config.NumberColumn("Investment (€)", format="€%.2f"),
                "Market Value (€)": st.column_config.NumberColumn("Market Value (€)", format="€%.2f"),
                "Unrealized Gain (€)": st.column_config.NumberColumn("Unrealized Gain (€)", format="€%.2f"),
                "Unrealized Gain (%)": st.column_config.NumberColumn("Unrealized Gain (%)", format="%.2f%%")
            }
        )

    with st.expander("💡 AI Analysis & Forecast"):
        try:
            MISTRAL_API_KEY = st.secrets["MISTRAL_API_KEY"]

            if st.button("🤖 Run Mistral AI Portfolio Analysis"):
                with st.spinner("Sending portfolio summary to Mistral AI..."):
                    user_prompt = f"""
    You are a financial advisor analyzing a portfolio. Use Modern Portfolio Theory and sound portfolio management principles.

    Here is the aggregated portfolio summary:

    {summary.to_string(index=False)}

    And here is the annual performance breakdown:

    {annual.to_string(index=False)}

    Please perform the following:
    1. Identify overexposed sectors or individual stocks.
    2. Highlight diversification gaps.
    3. Suggest rebalancing strategies.
    4. Recommend ETF or stock alternatives to reduce risk and increase stability.
    5. Provide a short-term (1 year) and medium-term (3–5 years) forecast based on current asset mix.
    6. Mention any red flags like concentrated risk, declining sectors, or underperformers.

    Be concise, professional, and use bullet points.
    """

                    import requests

                    headers = {
                        "Authorization": f"Bearer {MISTRAL_API_KEY}",
                        "Content-Type": "application/json"
                    }

                    payload = {
                        "model": "mistral-small",  # or mistral-medium / mistral-large
                        "messages": [
                            {"role": "system", "content": "You are a helpful financial analyst AI."},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.7
                    }

                    response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)

                    if response.status_code == 200:
                        ai_response = response.json()["choices"][0]["message"]["content"]
                    else:
                        ai_response = f"⚠️ API Error: {response.status_code} - {response.text}"

                    st.success("AI analysis complete.")
                    st.markdown(f"**AI Suggestion:**\n\n{ai_response}")

        except Exception as e:
            st.warning("⚠️ Mistral API key not found in Streamlit secrets or another error occurred.")
            st.exception(e)
