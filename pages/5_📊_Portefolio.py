import streamlit as st 
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="📊 Portfolio Analysis", layout="wide")
st.title("📊 Portfolio Analysis & AI Suggestions")

# Upload CSV
uploaded_file = st.file_uploader("📁 Upload Portfolio CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file, parse_dates=["Date"], dayfirst=True, on_bad_lines='skip')
    df.columns = [col.strip() for col in df.columns]
    st.write("Columns found in CSV:", list(df.columns))

    # Required columns except no yfinance price needed
    required_cols = {"Date", "Symbol", "Quantity", "Purchase Price", "Current Price"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        st.error(f"Missing required columns in CSV: {missing_cols}")
    else:
        # Handle Transaction Type missing/empty
        if "Transaction Type" not in df.columns or df["Transaction Type"].isnull().all() or df["Transaction Type"].eq("").all():
            st.warning("⚠️ 'Transaction Type' missing or empty. Please classify each transaction.")

            user_choices = []
            for i, row in df.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{row['Date'].date()} | {row['Symbol']} | Qty: {row['Quantity']} @ {row['Purchase Price']}")
                with col2:
                    choice = st.radio(
                        f"Row {i+1}",
                        options=["Buy", "Sell"],
                        key=f"txn_type_{i}",
                        horizontal=True
                    )
                user_choices.append(choice)
            df["Transaction Type"] = user_choices

        # Clean symbol column
        df["Symbol"] = df["Symbol"].str.upper().str.split('.').str[0]

        # Financial calculations based on CSV Current Price
        df["Investment"] = df["Quantity"] * df["Purchase Price"]
        df["Market Value"] = df["Quantity"] * df["Current Price"]
        df["Unrealized Gain"] = df["Market Value"] - df["Investment"]

        # Separate buys and sells
        buys = df[df["Transaction Type"].str.lower() == "buy"]
        sells = df[df["Transaction Type"].str.lower() == "sell"]

        # Summary per symbol
        summary = df.groupby("Symbol").agg({
            "Quantity": "sum",
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain": "sum"
        }).reset_index()

        st.subheader("📌 Compiled Stock Summary")
        st.dataframe(summary, use_container_width=True)

        st.subheader("📄 Line-by-Line Transactions")
        st.dataframe(df.sort_values(by="Date"), use_container_width=True)

        # Realized Gains Calculation by Year
        if not buys.empty and not sells.empty:
            # Average buy price per symbol for sell transactions
            avg_buy_price_per_symbol = buys.groupby("Symbol")["Purchase Price"].mean()

            # Calculate realized gain for sells using avg buy price
            sells = sells.copy()
            sells["Realized Gain"] = sells.apply(
                lambda row: (row["Purchase Price"] - avg_buy_price_per_symbol.get(row["Symbol"], row["Purchase Price"])) * row["Quantity"], axis=1
            )

            st.subheader("💰 Realized Gains per Transaction")
            st.dataframe(sells[["Date", "Symbol", "Quantity", "Purchase Price", "Realized Gain"]], use_container_width=True)

            # Aggregate realized gains/losses by year
            sells["Year"] = sells["Date"].dt.year
            annual_realized = sells.groupby("Year")["Realized Gain"].sum().reset_index()

            st.subheader("📅 Annual Realized Gains/Losses")
            st.dataframe(annual_realized, use_container_width=True)

        # Annual performance summary for unrealized gains
        df["Year"] = df["Date"].dt.year
        annual_summary = df.groupby(["Symbol", "Year"]).agg({
            "Investment": "sum",
            "Market Value": "sum",
            "Unrealized Gain": "sum"
        }).reset_index()

        st.subheader("📈 Annual Performance (Unrealized Gains)")
        st.dataframe(annual_summary, use_container_width=True)

        # AI Trigger
        if st.button("🤖 Run AI Portfolio Analysis"):
            with st.spinner("Sending portfolio to Mistral AI..."):
                user_prompt = (
                    f"Analyze this portfolio:\n\n{summary.to_string(index=False)}\n\n"
                    "Suggest rebalancing and improvements using Modern Portfolio Theory."
                )
                # Placeholder for AI call
                ai_response = "✅ Based on current metrics, consider rebalancing away from overexposed tech stocks..."
                st.success("AI analysis complete.")
                st.markdown(f"**AI Suggestion:**\n\n{ai_response}")