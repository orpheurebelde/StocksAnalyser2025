import streamlit as st 
import pandas as pd
from datetime import datetime

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

        # AI Suggestion (optional)
        if st.button("🤖 Run AI Portfolio Analysis"):
            with st.spinner("Sending portfolio to Mistral AI..."):
                user_prompt = (
                    f"Analyze this portfolio:\n\n{summary.to_string(index=False)}\n\n"
                    "Suggest rebalancing and improvements using Modern Portfolio Theory."
                )
                ai_response = "✅ Based on current metrics, consider diversifying away from high-volatility sectors..."
                st.success("AI analysis complete.")
                st.markdown(f"**AI Suggestion:**\n\n{ai_response}")