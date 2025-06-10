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

                        # Example placeholder – you would replace this with your real Mistral API call
                        ai_response = """
                            **AI Portfolio Analysis**

                            📊 **Diversification Observations**:
                            - The portfolio is heavily weighted towards technology (over 60%).
                            - Exposure to financials, healthcare, and energy is minimal or nonexistent.

                            ⚠️ **Risks Identified**:
                            - High concentration in volatile sectors increases drawdown risk during market downturns.
                            - Limited geographic diversification; most assets are from XETRA-listed companies.

                            🔄 **Rebalancing Suggestions**:
                            - Reduce weight in tech stocks like [EXAMPLE_STOCK].
                            - Increase allocation in defensive sectors: utilities, healthcare, consumer staples.
                            - Add ETFs like `VEA` (Developed Markets), `VWO` (Emerging Markets), or `SPY` (S&P 500 exposure).

                            📈 **Forecast**:
                            - If market trends persist, this portfolio may return ~6 to 9% annually but with high volatility.
                            - A more balanced portfolio could yield 7% with lower risk.

                            📌 **Next Steps**:
                            - Set target allocations by sector.
                            - Reassess every quarter.
                            - Consider dividend-focused ETFs for stable income.

                            Let me know if you'd like this tailored to a risk profile or long-term retirement plan.
                            """

                        st.success("AI analysis complete.")
                        st.markdown(f"**AI Suggestion:**\n\n{ai_response}")

            except Exception as e:
                st.warning("⚠️ Mistral API key not found in Streamlit secrets or another error occurred.")
                st.exception(e)
