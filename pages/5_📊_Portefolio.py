import streamlit as st 
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="📊 Portfolio Analysis", layout="wide")
st.title("📊 Portfolio Analysis & AI Suggestions")

# Upload CSV
uploaded_file = st.file_uploader("📁 Upload Portfolio CSV", type=["csv"])

if uploaded_file:
    # Read and clean
    df = pd.read_csv(uploaded_file, parse_dates=["Date"], dayfirst=True, on_bad_lines='skip')
    df.columns = [col.strip() for col in df.columns]

    # Debug: show columns
    st.write("Columns found in CSV:", list(df.columns))

    # Required columns (now using your own 'Current Price' instead of Yahoo Finance)
    required_cols = {"Date", "Symbol", "Quantity", "Purchase Price", "Current Price"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        st.error(f"Missing required columns in CSV: {missing_cols}")
    else:
        # Normalize Symbol format
        df["Symbol"] = df["Symbol"].str.upper().str.split('.').str[0]

        # Compute investment metrics
        df["Investment"] = df["Quantity"] * df["Purchase Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain (€)"] = df["Market Value"] - df["Investment"]
        df["Unrealized Gain (%)"] = (df["Unrealized Gain (€)"] / df["Investment"]) * 100

        # Add Year column for grouping
        df["Year"] = df["Date"].dt.year

        # Show line-by-line transaction table
        st.subheader("📄 Line-by-Line Transactions")
        st.dataframe(df.sort_values(by="Date"), use_container_width=True)

        # Group by Symbol for overall summary
        summary = df.groupby("Symbol").agg({
            "Quantity": "sum",
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        summary["Unrealized Gain (%)"] = (summary["Unrealized Gain (€)"] / summary["Investment"]) * 100

        st.subheader("📌 Compiled Stock Summary")
        st.dataframe(summary, use_container_width=True)

        # Group by Year for annual summary
        annual = df.groupby("Year").agg({
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain (€)": "sum"
        }).reset_index()
        annual["Unrealized Gain (%)"] = (annual["Unrealized Gain (€)"] / annual["Investment"]) * 100

        st.subheader("📅 Annual Unrealized Performance Summary")
        st.dataframe(
            annual.rename(columns={
                "Year": "Year",
                "Investment": "Investment (€)",
                "Market Value": "Market Value (€)",
                "Unrealized Gain (€)": "Unrealized Gain (€)",
                "Unrealized Gain (%)": "Unrealized Gain (%)"
            }),
            use_container_width=True
        )

        # AI Analysis Trigger
        if st.button("🤖 Run AI Portfolio Analysis"):
            with st.spinner("Sending portfolio to Mistral AI..."):
                user_prompt = (
                    f"Analyze this portfolio:\n\n{summary.to_string(index=False)}\n\n"
                    "Suggest rebalancing and improvements using Modern Portfolio Theory."
                )
                # Replace with real call to Mistral API
                ai_response = "✅ Based on current metrics, consider reducing overweight positions in high-volatility sectors..."
                st.success("AI analysis complete.")
                st.markdown(f"**AI Suggestion:**\n\n{ai_response}")