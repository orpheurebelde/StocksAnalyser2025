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
    else:
        df["Symbol"] = df["Symbol"].str.upper().str.split('.').str[0]
        df["Investment"] = df["Quantity"] * df["Purchase Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain (€)"] = df["Market Value"] - df["Investment"]
        df["Unrealized Gain (%)"] = (df["Unrealized Gain (€)"] / df["Investment"]) * 100
        df["Year"] = df["Date"].dt.year

    # 📈 Fetch historical data for portfolio & benchmarks
        st.subheader("📈 Portfolio vs S&P 500 (VUAA) & Nasdaq-100 (EQQQ)")

        try:
            # Convert purchase dates to dictionary {Symbol: purchase_date}
            purchase_dates = df.groupby("Symbol")["Date"].min().to_dict()

            # Download benchmark data
            benchmarks = {
                "S&P 500 EUR (VUAA)": "VUAA.AS",   # Vanguard S&P 500 UCITS ETF EUR
                "Nasdaq-100 EUR (EQQQ)": "EQQQ.AS" # Invesco Nasdaq-100 UCITS ETF EUR
            }
            bench_data = {}
            for name, ticker in benchmarks.items():
                bench_data[name] = yf.download(ticker, start=min(purchase_dates.values()), progress=False)["Adj Close"]

            # Calculate portfolio value history
            all_dates = None
            port_history = None
            for symbol, start_date in purchase_dates.items():
                hist = yf.download(symbol + ".AS", start=start_date, progress=False)["Adj Close"]  # Adjust ticker suffix for exchange
                qty = df.loc[df["Symbol"] == symbol, "Quantity"].sum()
                value = hist * qty
                if port_history is None:
                    port_history = value
                else:
                    port_history = port_history.add(value, fill_value=0)
                if all_dates is None:
                    all_dates = hist.index
                else:
                    all_dates = all_dates.union(hist.index)

            port_history = port_history.reindex(all_dates).fillna(method="ffill")

            # Normalize for comparison (start = 100)
            port_norm = port_history / port_history.iloc[0] * 100
            bench_norm = {name: data / data.iloc[0] * 100 for name, data in bench_data.items()}

            # 📊 Plot
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(port_norm.index, port_norm, label="Portfolio", linewidth=2)
            for name, series in bench_norm.items():
                ax.plot(series.index, series, label=name, alpha=0.8)
            ax.legend()
            ax.set_title("Portfolio vs Benchmarks (Total Return, EUR)")
            ax.set_ylabel("Value (Start = 100)")
            st.pyplot(fig)

            # 📏 Performance metrics
            def perf_metrics(series):
                returns = series.pct_change().dropna()
                ann_return = (series.iloc[-1] / series.iloc[0]) ** (252/len(series)) - 1
                ann_vol = returns.std() * np.sqrt(252)
                sharpe = ann_return / ann_vol if ann_vol != 0 else np.nan
                max_dd = ((series / series.cummax()) - 1).min()
                return ann_return, ann_vol, sharpe, max_dd

            metrics = {}
            metrics["Portfolio"] = perf_metrics(port_history)
            for name, series in bench_data.items():
                metrics[name] = perf_metrics(series)

            st.write("📊 **Performance Metrics**")
            st.dataframe(pd.DataFrame(metrics, index=["Annualized Return", "Annualized Volatility", "Sharpe Ratio", "Max Drawdown (%)"]).T)

        except Exception as e:
            st.error(f"⚠️ Error fetching performance data: {e}")
    
        # Display the portfolio summary
        # 1. Transactions Table
        with st.expander("📄 Line-by-Line Transactions"):
            st.dataframe(
                df.sort_values(by="Date"),
                use_container_width=True,
                column_config={
                    "Purchase Price": st.column_config.NumberColumn("Purchase Price (€)", format="€%.2f"),
                    "Current Price": st.column_config.NumberColumn("Current Price (€)", format="€%.2f"),
                    "Investment": st.column_config.NumberColumn("Investment (€)", format="€%.2f"),
                    "Market Value": st.column_config.NumberColumn("Market Value (€)", format="€%.2f"),
                    "Unrealized Gain (€)": st.column_config.NumberColumn("Unrealized Gain (€)", format="€%.2f"),
                    "Unrealized Gain (%)": st.column_config.NumberColumn("Unrealized Gain (%)", format="%.2f%%")
                }
            )

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
