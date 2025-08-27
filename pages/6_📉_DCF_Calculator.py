import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from utils.utils import load_stock_list, get_stock_info

st.set_page_config(page_title="DCF Calculator", layout="wide")
st.title("5-Year DCF Calculator — Streamlit (Upgraded)")

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

def safe_get_cashflow_avg(ticker, years=3):
    """Compute average FCF over last `years`"""
    try:
        cf = ticker.cashflow
        candidates = ['Free Cash Flow','FreeCashFlow','Free Cash Flow (USD)']
        for c in candidates:
            if c in cf.index:
                vals = cf.loc[c].dropna().values[:years]
                return safe_float(np.mean(vals)) if len(vals) > 0 else None
        # fallback if no Free Cash Flow row
        if 'Operating Cash Flow' in cf.index and 'Capital Expenditures' in cf.index:
            vals = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditures']).dropna().values[:years]
            return safe_float(np.mean(vals)) if len(vals) > 0 else None
    except:
        return None

def get_adjusted_net_cash(ticker):
    """Calculate net cash automatically (cash - debt)"""
    cash, debt = 0.0, 0.0
    try:
        bs = ticker.balance_sheet
        for c in ['Cash', 'Cash And Cash Equivalents', 'Cash and cash equivalents']:
            if c in bs.index:
                cash = safe_float(bs.loc[c].iloc[0])
                break
        vals = []
        for k in ['Long Term Debt','Short Term Debt','Total Debt']:
            if k in bs.index:
                vals.append(bs.loc[k].iloc[0])
        if vals:
            debt = safe_float(np.nansum(vals))
    except:
        pass
    return cash - debt

def dcf_from_fcf_list(fcf_list, discount_rate, terminal_growth):
    pv_years = [cf / ((1 + discount_rate) ** (i+1)) for i, cf in enumerate(fcf_list)]
    terminal = fcf_list[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_terminal = terminal / ((1 + discount_rate) ** len(fcf_list))
    ev = np.nansum(pv_years) + pv_terminal
    return {'pv_years': pv_years,'pv_terminal': pv_terminal,'ev': ev,'terminal': terminal}

# --- Main Flow ---
if selected_display != "Select a stock...":
    ticker_symbol = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    info = get_stock_info(ticker_symbol)
    
    # --- yfinance ticker ---
    ticker_yf = yf.Ticker(ticker_symbol)
    
    # --- Defaults ---
    shares_outstanding_safe = safe_int(info.get("sharesOutstanding"), 0)
    market_price_safe = safe_float(info.get("previousClose"), 0.0)
    market_cap_safe = safe_float(info.get("marketCap"), 0.0)
    long_name = info.get("longName", ticker_symbol)
    
    # --- FCF & Net Cash ---
    fcf_avg = safe_get_cashflow_avg(ticker_yf, years=3) or 1_000_000_000
    net_cash = get_adjusted_net_cash(ticker_yf)
    
    # --- Display metrics ---
    st.subheader(f"{ticker_symbol} — {long_name}")
    col3, col4, col5 = st.columns(3)
    with col3: st.metric("Shares Outstanding", format_number(shares_outstanding_safe))
    with col4: st.metric("Market Price", format_currency_dec(market_price_safe))
    with col5: st.metric("Market Cap", format_currency(market_cap_safe))
    
    # --- Inputs ---
    shares_outstanding_input = st.number_input("Shares Outstanding:", min_value=0, value=shares_outstanding_safe, step=1)
    starting_fcf_input = st.number_input("Starting FCF (TTM) USD:", min_value=0.0, value=fcf_avg, step=1_000_000.0, format="%.0f")
    
    # --- Growth sliders ---
    st.markdown("### 5-Year Growth Rate Assumptions")
    default_growths = [50.0,30.0,20.0,15.0,10.0]
    growth_cols = st.columns(5)
    user_growth_rates = [growth_cols[i].slider(f"Year {i+1} Growth %", 0.0, 100.0, default_growths[i], step=1.0) for i in range(5)]
    fcfs = [starting_fcf_input * (1 + g/100) for g in user_growth_rates]
    
    # --- Terminal growth ---
    st.markdown("### Terminal Growth Assumption")
    term_cols = st.columns(5)
    terminal_growth = term_cols[2].slider("Terminal Growth Rate %", min_value=0.0, max_value=5.0, value=3.0, step=0.1)/100
    
    # --- Discount rates (dynamic base) ---
    st.markdown("### Discount Rate Scenarios")
    rf_rate = st.number_input("Risk-Free Rate %", 0.0, 10.0, 5.0, 0.1)/100
    beta = st.number_input("Beta", 0.0, 3.0, 1.1, 0.01)
    market_premium = st.number_input("Market Risk Premium %", 0.0, 20.0, 6.0, 0.1)/100
    disc_base = rf_rate + beta*market_premium
    disc_cols = st.columns(3)
    disc_bull = disc_cols[0].slider("Bull Discount Rate %", 0.0, 50.0, max(disc_base-0.02,0.05)*100)
    disc_base = disc_cols[1].slider("Base Discount Rate %", 0.0, 50.0, disc_base*100)
    disc_bear = disc_cols[2].slider("Bear Discount Rate %", 0.0, 50.0, min(disc_base+0.02,0.25)*100)
    
    # --- Compute scenarios ---
    scenarios = {"Bull": disc_bull/100, "Base": disc_base/100, "Bear": disc_bear/100}
    results = {}
    for name, dr in scenarios.items():
        res = dcf_from_fcf_list(fcfs, dr, terminal_growth)
        equity = res['ev'] + net_cash
        per_share = equity / shares_outstanding_input if shares_outstanding_input else None
        results[name] = {'res': res,'equity': equity,'per_share': per_share}
    
    # --- Display results ---
    st.subheader("DCF Results")
    rows = []
    for name in ["Bull","Base","Bear"]:
        r = results[name]
        rows.append({
            "Scenario": name,
            "Discount Rate %": scenarios[name]*100,
            "Enterprise Value (USD)": r['res']['ev'],
            "PV Terminal (USD)": r['res']['pv_terminal'],
            "Terminal Value (undiscounted)": r['res']['terminal'],
            "Equity Value (USD)": r['equity'],
            "Implied Value / Share (USD)": r['per_share']
        })
    df_results = pd.DataFrame(rows)
    for col in ["Enterprise Value (USD)","PV Terminal (USD)","Terminal Value (undiscounted)","Equity Value (USD)"]:
        df_results[col] = df_results[col].map(lambda x: f"{x:,.0f}")
    df_results['Implied Value / Share (USD)'] = df_results['Implied Value / Share (USD)'].map(lambda x: f"{x:,.2f}" if x else 'n/a')
    st.table(df_results.set_index("Scenario"))
    
    # --- PV chart ---
    st.subheader("PV Breakdown (Base scenario)")
    base_pv_years = results['Base']['res']['pv_years']
    base_pv_terminal = results['Base']['res']['pv_terminal']
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
    st.download_button('Download Base PV CSV', data=csv_buffer, file_name=f'{ticker_symbol}_dcf_base_pv.csv', mime='text/csv')
    
    st.markdown('---')
    st.caption("Built with yfinance — results depend on inputs. Not investment advice.")