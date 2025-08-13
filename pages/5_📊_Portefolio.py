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

        # —— Cached helpers
        @st.cache_data(ttl=3600, show_spinner=False)
        def _safe_download_adjclose(ticker: str, start):
            try:
                df_y = yf.download(ticker, start=start, progress=False, auto_adjust=False)
                if isinstance(df_y, pd.DataFrame) and "Adj Close" in df_y:
                    s = df_y["Adj Close"].dropna()
                    s.index = pd.to_datetime(s.index)
                    return s
                return pd.Series(dtype=float)
            except Exception:
                return pd.Series(dtype=float)

        @st.cache_data(ttl=3600, show_spinner=False)
        def detect_yahoo_symbol_xetra_first(base_symbol: str, start):
            """
            Detects Yahoo Finance symbol for a Xetra (.DE) portfolio, 
            falling back to other exchanges if needed.
            Uses a fixed early start date for detection so it won't fail if purchase date is recent.
            """
            test_start = "2000-01-01"  # Always use an early date for detection

            # If the user already provided a suffix, test it directly
            if "." in base_symbol:
                s = _safe_download_adjclose(base_symbol, test_start)
                if not s.empty:
                    return base_symbol
                return None  # Provided ticker is invalid

            # Try .DE first
            s = _safe_download_adjclose(base_symbol + ".DE", test_start)
            if not s.empty:
                return base_symbol + ".DE"

            # Fall back to other suffixes
            suffixes = [".F", ".BE", ".AS", ".PA", ".BR", ".MI", ".SW", ".VI",
                        ".ST", ".HE", ".CO", ".OL", ".LS", ".MC", ".L", ".TO", ".IE"]
            for suf in suffixes:
                t = base_symbol + suf
                s = _safe_download_adjclose(t, test_start)
                if not s.empty:
                    return t
            return None

        def _normalize_to_100(series: pd.Series) -> pd.Series:
            s = series.dropna()
            if len(s) == 0:
                return s
            base = s.iloc[0]
            if base == 0:
                s = s[s != 0]
                if len(s) == 0:
                    return s
                base = s.iloc[0]
            return (s / base) * 100

        def perf_metrics_from_prices(price_series: pd.Series, risk_free_annual: float = 0.0):
            s = price_series.dropna()
            if len(s) < 2:
                return np.nan, np.nan, np.nan, np.nan, np.nan
            rets = s.pct_change().dropna()
            cagr = (s.iloc[-1] / s.iloc[0]) ** (252 / len(s)) - 1
            vol = rets.std() * np.sqrt(252)
            downside = rets[rets < 0].std() * np.sqrt(252)
            sharpe = np.nan if vol == 0 else (cagr - risk_free_annual) / vol
            sortino = np.nan if downside == 0 else (cagr - risk_free_annual) / downside
            max_dd = ((s / s.cummax()) - 1).min()
            return cagr, vol, sharpe, sortino, max_dd

        # —— Main processing
        try:
            required_cols = {"Date", "Symbol", "Quantity"}
            if not required_cols.issubset(df.columns):
                st.error(f"CSV must include columns: {required_cols}")
                st.stop()

            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")

            base_start = df["Date"].min()
            unique_symbols = sorted(df["Symbol"].astype(str).str.strip().str.upper().unique())

            # Map each base symbol to Yahoo symbol
            symbol_map = {sym: detect_yahoo_symbol_xetra_first(sym, base_start) for sym in unique_symbols}

            map_df = pd.DataFrame(
                [{"CSV Symbol": k, "Yahoo Symbol": v if v else "❌ not found"} for k, v in symbol_map.items()]
            )
            with st.expander("🔍 Symbol mapping (CSV → Yahoo)"):
                st.dataframe(map_df, use_container_width=True)

            # Build portfolio value history
            port_history = pd.Series(dtype=float)
            for _, row in df.iterrows():
                base_sym = str(row["Symbol"]).strip().upper()
                yahoo_sym = symbol_map.get(base_sym)
                qty = float(row["Quantity"]) if pd.notna(row["Quantity"]) else 0.0
                lot_start = pd.to_datetime(row["Date"])

                if yahoo_sym is None or pd.isna(yahoo_sym) or qty == 0:
                    continue

                hist = _safe_download_adjclose(yahoo_sym, lot_start)
                if hist.empty:
                    st.warning(f"No data for lot: {base_sym} ({yahoo_sym}) from {lot_start.date()}")
                    continue

                lot_value = hist * qty
                port_history = lot_value if port_history.empty else port_history.add(lot_value, fill_value=0.0)

            if port_history.empty or len(port_history) < 2:
                st.error("No usable price data for the portfolio (after mapping). Check tickers/dates.")
                st.stop()

            # Benchmarks
            benchmarks = {
                "S&P 500 (^GSPC)": "^GSPC",
                "Nasdaq-100 (^NDX)": "^NDX",
            }
            bench_data = {}
            bench_warnings = []
            bench_start = port_history.index.min()
            for name, ticker in benchmarks.items():
                s = _safe_download_adjclose(ticker, bench_start)
                if len(s) < 2:
                    bench_warnings.append(name)
                    continue
                s = s.reindex(port_history.index).ffill().dropna()
                bench_data[name] = s

            for name in bench_warnings:
                st.warning(f"Benchmark had no usable data: {name}")

            # Chart
            port_norm = _normalize_to_100(port_history)
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(port_norm.index, port_norm, label="Portfolio", linewidth=2)
            for name, series in bench_data.items():
                ax.plot(series.index, _normalize_to_100(series), label=name)
            ax.set_title("Portfolio vs Benchmarks (price-only, start = 100)")
            ax.set_ylabel("Indexed Value")
            ax.legend()
            st.pyplot(fig)

            # Metrics
            rf = 0.0
            metrics = {}
            metrics["Portfolio"] = perf_metrics_from_prices(port_history, risk_free_annual=rf)
            for name, s in bench_data.items():
                metrics[name] = perf_metrics_from_prices(s, risk_free_annual=rf)

            metrics_df = pd.DataFrame(
                metrics,
                index=["Annualized Return", "Annualized Volatility", "Sharpe Ratio", "Sortino Ratio", "Max Drawdown"]
            ).T
            with st.expander("📊 Performance Metrics", expanded=True):
                st.dataframe(metrics_df, use_container_width=True)

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
