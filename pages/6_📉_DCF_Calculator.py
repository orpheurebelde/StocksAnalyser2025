import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from utils.utils import load_stock_list, get_stock_info

st.set_page_config(page_title="DCF Calculator", layout="wide")
st.title("5-Year DCF Calculator — Streamlit")

# --- Safe numeric helpers ---
def safe_int(val, default=0):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return int(val)
    except:
        return default

def safe_float(val, default=0.0):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except:
        return default

# --- Load stock list ---
stock_df = load_stock_list()
stock_df = stock_df.sort_values(by="Display")
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

# --- Formatting helpers ---
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"

# --- DCF helpers ---
def discounted_cash_flows(cashflows, discount_rate):
    return sum(cf / ((1 + discount_rate) ** (i + 1)) for i, cf in enumerate(cashflows))

def safe_get_cashflow(ticker):
    try:
        cf = ticker.cashflow
        candidates = ['Free Cash Flow','FreeCashFlow','Free Cash Flow (USD)']
        for c in candidates:
            if c in cf.index:
                return safe_float(cf.loc[c].iloc[0])
        if 'Operating Cash Flow' in cf.index and 'Capital Expenditures' in cf.index:
            return safe_float(cf.loc['Operating Cash Flow'].iloc[0] + cf.loc['Capital Expenditures'].iloc[0])
    except:
        return None

def safe_get_balance_items(ticker):
    bs = ticker.balance_sheet
    cash = None
    debt = None
    try:
        for c in ['Cash', 'Cash And Cash Equivalents', 'Cash and cash equivalents']:
            if c in bs.index:
                cash = safe_float(bs.loc[c].iloc[0])
                break
        vals = []
        for k in ['Long Term Debt','Short Long Term Debt','Short Term Debt','Total Debt']:
            if k in bs.index:
                vals.append(bs.loc[k].iloc[0])
        if vals:
            debt = safe_float(np.nansum(vals))
    except:
        pass
    return {'cash': cash, 'totalDebt': debt}

def dcf_from_fcf_list(fcf_list, discount_rate, terminal_growth):
    pv_years = []
    for i, fcf in enumerate(fcf_list, start=1):
        pv_years.append(fcf / ((1 + discount_rate) ** i))
    terminal = fcf_list[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_terminal = terminal / ((1 + discount_rate) ** 5)
    ev = np.nansum(pv_years) + pv_terminal
    return {'pv_years': pv_years,'pv_terminal': pv_terminal,'ev': ev,'terminal': terminal}

# --- Main Flow ---
if selected_display != "Select a stock...":
    ticker_symbol = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    info = get_stock_info(ticker_symbol)

    # --- Safe numeric defaults ---
    shares_outstanding_safe = safe_int(info.get("sharesOutstanding"), 0)
    market_price_safe = safe_float(info.get("previousClose"), 0.0)
    market_cap_safe = safe_float(info.get("marketCap"), 0.0)
    long_name = info.get("longName", ticker_symbol)

    # --- Get yfinance ticker for balance sheet and cashflow ---
    ticker_yf = yf.Ticker(ticker_symbol)
    fcf_ttm = safe_get_cashflow(ticker_yf)
    bal = safe_get_balance_items(ticker_yf)
    cash_guess = safe_float(bal.get('cash'))
    debt_guess = safe_float(bal.get('totalDebt'))

    # --- Display metrics ---
    st.subheader(f"{ticker_symbol} — {long_name}")
    col3, col4, col5 = st.columns(3)
    with col3: st.metric("Shares Outstanding", format_number(shares_outstanding_safe))
    with col4: st.metric("Market Price", format_currency_dec(market_price_safe))
    with col5: st.metric("Market Cap", format_currency(market_cap_safe))

    # --- Number Inputs / Sliders ---
    shares_outstanding_input = st.number_input(
        "Shares Outstanding:", min_value=0, value=shares_outstanding_safe, step=1
    )
    market_price_input = st.number_input(
        "Market Price (USD):", min_value=0.0, value=market_price_safe, step=0.01, format="%.2f"
    )
    market_cap_input = st.number_input(
        "Market Cap (USD):", min_value=0.0, value=market_cap_safe, step=1.0, format="%.0f"
    )

    starting_fcf_default = fcf_ttm if fcf_ttm else 1_300_000_000
    starting_fcf_input = st.number_input(
        "Starting FCF (TTM) USD:", min_value=0.0, value=starting_fcf_default, step=1_000_000.0, format="%.0f"
    )

    # --- Growth rate sliders ---
    st.markdown("### 5-Year Growth Rate Assumptions")
    default_growths = [50.0, 30.0, 20.0, 15.0, 10.0]
    user_growth_rates = []
    cols = st.columns(5)
    for i in range(5):
        user_growth_rates.append(
            cols[i].slider(
                f"Year {i+1} Growth %",
                min_value=0.0,
                max_value=100.0,
                value=safe_float(default_growths[i]),
                step=1.0
            )
        )

    # --- FCF projections ---
    st.markdown("### 5-Year FCF Projections")
    projected_fcfs = [starting_fcf_input * (1 + g/100) for g in user_growth_rates]
    fcfs = []
    cols = st.columns(5)
    for i in range(5):
        fcfs.append(
            cols[i].number_input(
                f"Year {i+1} FCF USD",
                min_value=0.0,
                value=projected_fcfs[i],
                step=1_000_000.0,
                format="%.0f"
            )
        )

    # --- Discount rate sliders ---
    st.markdown("### Discount Rate Scenarios")
    col_a, col_b, col_c = st.columns(3)
    disc_bull = col_a.slider("Bull Discount Rate %", min_value=0.0, max_value=50.0, value=8.0, step=0.1)
    disc_base = col_b.slider("Base Discount Rate %", min_value=0.0, max_value=50.0, value=9.0, step=0.1)
    disc_bear = col_c.slider("Bear Discount Rate %", min_value=0.0, max_value=50.0, value=10.0, step=0.1)

    # --- Net cash ---
    net_cash_default = cash_guess - debt_guess if cash_guess and debt_guess else cash_guess or 0.0
    net_cash_input = st.number_input(
        "Net Cash (Cash - Debt) USD (override)",
        min_value=-1e12,
        value=net_cash_default,
        step=1_000_000.0,
        format="%.0f"
    )

    # --- DCF computation ---
    scenarios = {"Bull": disc_bull/100, "Base": disc_base/100, "Bear": disc_bear/100}
    def compute_scenario(d_rate):
        res = dcf_from_fcf_list(fcfs, d_rate, 0.03)
        equity = res['ev'] + net_cash_input
        per_share = equity / shares_outstanding_input if shares_outstanding_input else None
        return res, equity, per_share

    results = {name: compute_scenario(dr) for name, dr in scenarios.items()}

    # --- Results table ---
    st.subheader("Results")
    rows = []
    for name in ["Bull", "Base", "Bear"]:
        res, equity, per_share = results[name]
        rows.append({
            "Scenario": name,
            "Discount Rate %": scenarios[name]*100,
            "Enterprise Value (USD)": res['ev'],
            "PV Terminal (USD)": res['pv_terminal'],
            "Terminal Value (undiscounted)": res['terminal'],
            "Equity Value (USD)": equity,
            "Implied Value / Share (USD)": per_share if per_share else np.nan
        })

    df_results = pd.DataFrame(rows)
    for col in ["Enterprise Value (USD)","PV Terminal (USD)","Terminal Value (undiscounted)","Equity Value (USD)"]:
        df_results[col] = df_results[col].map(lambda x: f"{x:,.0f}")
    if shares_outstanding_input:
        df_results['Implied Value / Share (USD)'] = df_results['Implied Value / Share (USD)'].map(lambda x: f"{x:,.2f}")
    else:
        df_results['Implied Value / Share (USD)'] = 'n/a'
    st.table(df_results.set_index("Scenario"))

    # --- PV chart ---
    st.subheader("PV breakdown (Base scenario)")
    base_pv_years = results['Base'][0]['pv_years']
    base_pv_terminal = results['Base'][0]['pv_terminal']
    labels = [f"Year {i}" for i in range(1,6)] + ["Terminal"]
    values = base_pv_years + [base_pv_terminal]
    fig, ax = plt.subplots(figsize=(9,4))
    ax.bar(labels, values)
    ax.set_ylabel("Present Value (USD)")
    ax.set_title("PV of projected FCFs and terminal (Base)")
    ax.ticklabel_format(axis='y', style='plain')
    st.pyplot(fig)

    # --- CSV Download ---
    csv_buffer = BytesIO()
    out_df = pd.DataFrame({'Year':[f'Year {i}' for i in range(1,6)]+['Terminal'],
                           'Base PV USD':base_pv_years+[base_pv_terminal]})
    out_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    st.download_button('Download base PV CSV', data=csv_buffer, file_name=f'{ticker_symbol}_dcf_base_pv.csv', mime='text/csv')

    st.markdown('---')
    st.caption("Built with yfinance — results depend on inputs. Not investment advice.")