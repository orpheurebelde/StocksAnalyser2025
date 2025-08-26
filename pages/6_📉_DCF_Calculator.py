import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from utils.utils import load_stock_list, get_stock_info

st.set_page_config(page_title="DCF Calculator", layout="wide")
st.title("5-Year DCF Calculator — Streamlit")

# --- Load stock list and prepare selector ---
stock_df = load_stock_list()
stock_df = stock_df.sort_values(by="Display")
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

# --- Formatting helpers ---
def format_currency(val): return f"${val:,.0f}" if isinstance(val, (int, float)) else "N/A"
def format_currency_dec(val): return f"${val:,.2f}" if isinstance(val, (int, float)) else "N/A"
def format_percent(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "N/A"
def format_number(val): return f"{val:,}" if isinstance(val, (int, float)) else "N/A"

def discounted_cash_flows(cashflows, discount_rate):
    return sum(cf / ((1 + discount_rate) ** (i + 1)) for i, cf in enumerate(cashflows))

# --- Helper functions ---
def safe_get_cashflow(ticker):
    try:
        cf = ticker.cashflow
        candidates = ['Free Cash Flow','FreeCashFlow','Free Cash Flow (USD)']
        for c in candidates:
            if c in cf.index:
                val = cf.loc[c].iloc[0]
                return float(val)
        if 'Operating Cash Flow' in cf.index and 'Capital Expenditures' in cf.index:
            val = cf.loc['Operating Cash Flow'].iloc[0] + cf.loc['Capital Expenditures'].iloc[0]
            return float(val)
    except Exception:
        pass
    return None

def safe_get_balance_items(ticker):
    bs = ticker.balance_sheet
    result = {'cash': None, 'totalDebt': None}
    try:
        if 'Cash' in bs.index:
            result['cash'] = float(bs.loc['Cash'].iloc[0])
        elif 'Cash And Cash Equivalents' in bs.index:
            result['cash'] = float(bs.loc['Cash And Cash Equivalents'].iloc[0])
        elif 'Cash and cash equivalents' in bs.index:
            result['cash'] = float(bs.loc['Cash and cash equivalents'].iloc[0])
        vals = []
        for k in ['Long Term Debt','Short Long Term Debt','Short Term Debt']:
            if k in bs.index:
                vals.append(bs.loc[k].iloc[0])
        if vals:
            result['totalDebt'] = float(np.nansum(vals))
        if result['totalDebt'] is None and 'Total Debt' in bs.index:
            result['totalDebt'] = float(bs.loc['Total Debt'].iloc[0])
    except Exception:
        pass
    return result

def dcf_from_fcf_list(fcf_list, discount_rate, terminal_growth):
    pv_years = []
    for i, fcf in enumerate(fcf_list, start=1):
        pv = fcf / ((1 + discount_rate) ** i)
        pv_years.append(pv)
    terminal = fcf_list[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_terminal = terminal / ((1 + discount_rate) ** 5)
    ev = np.nansum(pv_years) + pv_terminal
    return {'pv_years': pv_years,'pv_terminal': pv_terminal,'ev': ev,'terminal': terminal}

# --- Main Flow ---
if selected_display != "Select a stock...":
    ticker_symbol = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    ticker_yf = yf.Ticker(ticker_symbol)

    # --- Fetch info from cache or yfinance ---
    info = get_stock_info(ticker_symbol)
    shares_outstanding = info.get("shares_outstanding")
    market_price = info.get("market_price")
    market_cap = info.get("market_cap")

    # --- Manual fallback if any info missing ---
    if shares_outstanding is None:
        shares_outstanding = st.number_input("Enter Shares Outstanding:", min_value=0, value=0)
    if market_price is None:
        market_price = st.number_input("Enter Current Market Price:", min_value=0.0, value=0.0, format="%.2f")
    if market_cap is None:
        market_cap = st.number_input("Enter Market Cap:", min_value=0.0, value=0.0, format="%.2f")

    fcf_ttm = safe_get_cashflow(ticker_yf)
    bal = safe_get_balance_items(ticker_yf)
    cash_guess = bal['cash']
    debt_guess = bal['totalDebt']

    st.subheader(f"{ticker_symbol}")
    col3, col4, col5 = st.columns(3)
    with col3:
        st.metric('Shares outstanding', format_number(shares_outstanding))
    with col4:
        st.metric('Market price (latest)', format_currency_dec(market_price))
    with col5:
        st.metric('Market Cap', format_currency(market_cap))

    st.markdown('---')

    # --- Starting FCF input ---
    if fcf_ttm is None:
        st.warning('Could not find a reliable Free Cash Flow (TTM). Enter manually:')
        starting_fcf = st.number_input('Starting FCF (TTM) in USD', value=1_300_000_000.0, step=1_000_000.0, format="%.0f")
    else:
        starting_fcf = st.number_input('Starting FCF (TTM) in USD', value=float(fcf_ttm), format="%.0f")

    if starting_fcf < 0:
        st.warning(f"⚠️ Warning: The Free Cash Flow (FCF) for {ticker_symbol} is negative ({starting_fcf:,.0f}). DCF results may not be reliable.")

    st.markdown('### Growth rate assumptions')
    default_growths = [50.0, 30.0, 20.0, 15.0, 10.0]
    user_growth_rates = []
    cols = st.columns(5)
    for i in range(5):
        user_growth_rates.append(cols[i].number_input(f'Year {i+1} Growth %', value=default_growths[i], step=1.0, format="%.1f", key=f'growth{i}'))

    st.markdown('### 5-Year FCF projections')
    projected_fcfs = [starting_fcf * (1 + g/100) for g in user_growth_rates]
    fcfs = []
    cols = st.columns(5)
    for i in range(5):
        fcfs.append(cols[i].number_input(f'Year {i+1} FCF (USD)', value=float(projected_fcfs[i]), format="%.0f", key=f'fcf{i}'))

    st.markdown('---')
    st.subheader('Discount rate scenarios')
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        disc_bull = st.number_input('Bull Discount Rate (WACC) %', value=8.0, min_value=0.0, max_value=50.0, step=0.1)
    with col_b:
        disc_base = st.number_input('Base Discount Rate (WACC) %', value=9.0, min_value=0.0, max_value=50.0, step=0.1)
    with col_c:
        disc_bear = st.number_input('Bear Discount Rate (WACC) %', value=10.0, min_value=0.0, max_value=50.0, step=0.1)

    st.markdown('---')
    net_cash_default = None
    if cash_guess is not None:
        if debt_guess is not None:
            net_cash_default = float(cash_guess - debt_guess)
        else:
            net_cash_default = float(cash_guess)
    net_cash = st.number_input('Net Cash (Cash - Debt) USD (override)', value=float(net_cash_default) if net_cash_default is not None else 0.0, format="%.0f")

    st.markdown('---')
    scenarios = {
        'Bull': float(disc_bull) / 100.0,
        'Base': float(disc_base) / 100.0,
        'Bear': float(disc_bear) / 100.0
    }

    def compute_for_scenario(d_rate):
        res = dcf_from_fcf_list(fcfs, d_rate, 0.03)
        ev = res['ev']
        equity = ev + float(net_cash)
        per_share = equity / float(shares_outstanding) if shares_outstanding else None
        return res, equity, per_share

    results = {name: compute_for_scenario(dr) for name, dr in scenarios.items()}

    st.subheader('Results')
    rows = []
    for name in ['Bull','Base','Bear']:
        res, equity, per_share = results[name]
        rows.append({
            'Scenario': name,
            'Discount Rate %': scenarios[name]*100,
            'Enterprise Value (USD)': res['ev'],
            'PV Terminal (USD)': res['pv_terminal'],
            'Terminal Value (undiscounted)': res['terminal'],
            'Equity Value (USD)': equity,
            'Implied Value / Share (USD)': per_share if per_share is not None else np.nan
        })

    df_results = pd.DataFrame(rows)
    for col in ['Enterprise Value (USD)','PV Terminal (USD)','Terminal Value (undiscounted)','Equity Value (USD)']:
        df_results[col] = df_results[col].map(lambda x: f"{x:,.0f}")
    if shares_outstanding:
        df_results['Implied Value / Share (USD)'] = df_results['Implied Value / Share (USD)'].map(lambda x: f"{x:,.2f}")
    else:
        df_results['Implied Value / Share (USD)'] = 'n/a'

    st.table(df_results.set_index('Scenario'))

    st.subheader('PV breakdown (Base scenario)')
    base_pv_years = results['Base'][0]['pv_years']
    base_pv_terminal = results['Base'][0]['pv_terminal']
    labels = [f'Year {i}' for i in range(1,6)] + ['Terminal']
    values = base_pv_years + [base_pv_terminal]
    fig, ax = plt.subplots(figsize=(9,4))
    ax.bar(labels, values)
    ax.set_ylabel('Present Value (USD)')
    ax.set_title('PV of projected FCFs and terminal (Base)')
    ax.ticklabel_format(axis='y', style='plain')
    st.pyplot(fig)

    csv_buffer = BytesIO()
    out_df = pd.DataFrame({'Year':[f'Year {i}' for i in range(1,6)]+['Terminal'],
                           'Base PV USD':list(base_pv_years)+[base_pv_terminal]})
    out_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    st.download_button('Download base PV CSV', data=csv_buffer, file_name=f'{ticker_symbol}_dcf_base_pv.csv', mime='text/csv')

    st.markdown('---')
    st.caption('Built with yfinance — results depend on inputs. Not investment advice.')