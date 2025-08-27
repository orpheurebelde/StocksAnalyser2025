import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from utils.utils import load_stock_list, get_stock_info

st.set_page_config(page_title="DCF Calculator", layout="wide")
st.title("5-Year DCF Calculator — Streamlit (FCFF / EV-Exit Ready)")

# -----------------------------
# Safe helpers
# -----------------------------
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

def fmt0(x): return f"${x:,.0f}" if isinstance(x, (int, float, np.number)) else "N/A"
def fmt2(x): return f"${x:,.2f}" if isinstance(x, (int, float, np.number)) else "N/A"
def fmtn(x): return f"{x:,}" if isinstance(x, (int, float, np.number)) else "N/A"

# -----------------------------
# Shares & balance helpers
# -----------------------------
def choose_and_correct_shares(info: dict) -> int:
    """
    Prefer diluted shares when available.
    Sanity-check against MarketCap / Price if both present.
    """
    # Prefer diluted if present
    diluted = info.get("trailingDilutedSharesOutstanding")
    basic = info.get("sharesOutstanding") or info.get("shares_outstanding")
    shares = diluted or basic

    price = safe_float(info.get("previousClose")) or safe_float(info.get("market_price"))
    mcap = safe_float(info.get("marketCap")) or safe_float(info.get("market_cap"))

    # If any missing, just return safe int
    shares = safe_float(shares, 0.0)

    # Reconcile with implied if we have price & mcap
    if shares and price and mcap and price > 0:
        implied = mcap / price
        # If off by a big factor, trust implied
        ratio = implied / shares if shares else 1.0
        if ratio > 1.25 or ratio < 0.8:  # tolerant band
            shares = implied

    return safe_int(round(shares), 0)

def get_net_cash_guess(ticker_yf: yf.Ticker) -> float:
    """
    Cash - Total Debt from latest annual balance sheet (falls back to quarterly if needed).
    """
    cash = debt = None
    try:
        bs = ticker_yf.balance_sheet
        if bs is not None and not bs.empty:
            col = bs.columns[0]
            for key in ["Cash", "Cash And Cash Equivalents", "Cash and cash equivalents"]:
                if key in bs.index:
                    cash = safe_float(bs.loc[key, col])
                    break
            # Total Debt (or synthesize from LT + ST)
            if "Total Debt" in bs.index:
                debt = safe_float(bs.loc["Total Debt", col])
            else:
                parts = []
                for k in ["Short Long Term Debt", "Short Term Debt", "Long Term Debt"]:
                    if k in bs.index:
                        parts.append(safe_float(bs.loc[k, col]))
                if parts:
                    debt = float(np.nansum(parts))
    except:
        pass

    # Try quarterly if annual missing
    if (cash is None or debt is None):
        try:
            qbs = ticker_yf.quarterly_balance_sheet
            if qbs is not None and not qbs.empty:
                col = qbs.columns[0]
                if cash is None:
                    for key in ["Cash", "Cash And Cash Equivalents", "Cash and cash equivalents"]:
                        if key in qbs.index:
                            cash = safe_float(qbs.loc[key, col])
                            break
                if debt is None:
                    if "Total Debt" in qbs.index:
                        debt = safe_float(qbs.loc["Total Debt", col])
                    else:
                        parts = []
                        for k in ["Short Long Term Debt", "Short Term Debt", "Long Term Debt"]:
                            if k in qbs.index:
                                parts.append(safe_float(qbs.loc[k, col]))
                        if parts:
                            debt = float(np.nansum(parts))
        except:
            pass

    cash = safe_float(cash, 0.0)
    debt = safe_float(debt, 0.0)
    return cash - debt

# -----------------------------
# Cash flow helpers (FCFF / FCF)
# -----------------------------
def get_latest_val(df, keys):
    """Pick first existing key in df.index and return latest column value."""
    try:
        if df is None or df.empty:
            return None
        col = df.columns[0]
        for k in keys:
            if k in df.index:
                return safe_float(df.loc[k, col])
    except:
        pass
    return None

def compute_fcff_ttm(ticker_yf: yf.Ticker, tax_rate: float):
    """
    FCFF ≈ Operating Cash Flow + Interest*(1 - tax) - Capex
    Using latest annual; fallback to quarterly avg if annual missing.
    """
    ocf = capex = interest = None

    # Annual cashflow
    try:
        cf = ticker_yf.cashflow
        if cf is not None and not cf.empty:
            ocf = get_latest_val(cf, ["Operating Cash Flow"])
            capex = get_latest_val(cf, ["Capital Expenditures"])
            # interest (cash flow sign often negative for paid)
            interest = get_latest_val(cf, ["Interest Paid"])
            if interest is None:
                # Try income statement
                fin = ticker_yf.financials
                if fin is not None and not fin.empty:
                    interest = get_latest_val(fin, ["Interest Expense"])  # typically negative
    except:
        pass

    # Quarterly fallback if any missing
    if ocf is None or capex is None or interest is None:
        try:
            qcf = ticker_yf.quarterly_cashflow
            if qcf is not None and not qcf.empty:
                ocf_q = get_latest_val(qcf, ["Operating Cash Flow"])
                capex_q = get_latest_val(qcf, ["Capital Expenditures"])
                interest_q = get_latest_val(qcf, ["Interest Paid"])
                if ocf is None and ocf_q is not None: ocf = ocf_q * 4
                if capex is None and capex_q is not None: capex = capex_q * 4
                if interest is None and interest_q is not None: interest = interest_q * 4
        except:
            pass

    ocf = safe_float(ocf, None)
    capex = safe_float(capex, None)

    # If still missing, fall back to yfinance "Free Cash Flow" (levered)
    if ocf is None or capex is None:
        # FCFE approx
        try:
            cf = ticker_yf.cashflow
            if cf is not None and not cf.empty:
                for key in ["Free Cash Flow", "FreeCashFlow", "Free Cash Flow (USD)"]:
                    if key in cf.index:
                        fcfe = safe_float(cf.loc[key, cf.columns[0]], None)
                        if fcfe is not None:
                            return fcfe, "FCF"  # label for UI
        except:
            pass
        return None, "FCF"

    # Interest add-back (convert to expense if sign is negative)
    interest = safe_float(interest, 0.0)
    # Many sources store interest expense as negative outflow; we need +expense
    interest_expense = abs(interest)

    fcff = ocf + interest_expense * (1.0 - tax_rate) - capex
    return fcff, "FCFF"

def dcf_from_fcf_list(fcf_list, discount_rate, terminal_growth=None, exit_multiple=None, method="gordon"):
    """
    Returns pv_years, pv_terminal, ev, terminal (undiscounted).
    method: "gordon" or "exit_multiple"
    If "gordon": need terminal_growth.
    If "exit_multiple": need exit_multiple (EV/FCFF or EV/FCF).
    """
    # PV of explicit years
    pv_years = []
    for i, fcf in enumerate(fcf_list, start=1):
        pv_years.append(fcf / ((1 + discount_rate) ** i))

    # Terminal value at end of Year N (here N=len(fcf_list))
    if method == "gordon":
        g = terminal_growth or 0.0
        terminal = fcf_list[-1] * (1 + g) / (discount_rate - g)
    else:
        mult = exit_multiple or 10.0
        terminal = fcf_list[-1] * mult

    # Discount terminal back N years
    N = len(fcf_list)
    pv_terminal = terminal / ((1 + discount_rate) ** N)

    ev = float(np.nansum(pv_years)) + pv_terminal
    return {
        "pv_years": pv_years,
        "pv_terminal": pv_terminal,
        "ev": ev,
        "terminal": terminal
    }

# -----------------------------
# UI: stock picker
# -----------------------------
stock_df = load_stock_list().sort_values(by="Display")
options = ["Select a stock..."] + stock_df["Display"].tolist()
selected_display = st.selectbox("🔎 Search Stock by Ticker or Name", options, index=0)

# -----------------------------
# Main
# -----------------------------
if selected_display != "Select a stock...":
    ticker_symbol = stock_df.loc[stock_df["Display"] == selected_display, "Ticker"].values[0]
    info = get_stock_info(ticker_symbol)
    ticker_yf = yf.Ticker(ticker_symbol)

    # --- Core fields
    shares_auto = choose_and_correct_shares(info)
    price_auto = safe_float(info.get("previousClose"), 0.0)
    mcap_auto = safe_float(info.get("marketCap"), 0.0)
    long_name = info.get("longName", ticker_symbol)
    net_cash_auto = get_net_cash_guess(ticker_yf)

    st.subheader(f"{ticker_symbol} — {long_name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Shares Outstanding (auto)", fmtn(shares_auto))
    c2.metric("Market Price", fmt2(price_auto))
    c3.metric("Market Cap", fmt0(mcap_auto))

    # --- Inputs (you can override everything)
    st.markdown("### Inputs")
    ic1, ic2, ic3 = st.columns(3)
    shares_outstanding_input = ic1.number_input("Shares Outstanding (override, optional)", min_value=0, value=shares_auto, step=1, help="Auto = diluted or reconciled to MarketCap/Price")
    market_price_input = ic2.number_input("Market Price (USD)", min_value=0.0, value=price_auto, step=0.01, format="%.2f")
    market_cap_input = ic3.number_input("Market Cap (USD)", min_value=0.0, value=mcap_auto, step=1.0, format="%.0f")

    st.markdown("### Cash & Debt")
    nc1, nc2 = st.columns(2)
    net_cash_input = nc1.number_input("Net Cash (Cash - Total Debt) USD", value=float(net_cash_auto), step=1_000_000.0, format="%.0f")
    tax_rate_input = nc2.slider("Tax Rate for FCFF (%)", 0.0, 35.0, 18.0, 0.5) / 100.0

    # --- Starting cash flow (prefer FCFF)
    fcff_ttm, flow_label = compute_fcff_ttm(ticker_yf, tax_rate_input)
    if fcff_ttm is None:
        # last fallback: use 3y avg of FCF row if exists
        try:
            cf = ticker_yf.cashflow
            if cf is not None and not cf.empty:
                if "Free Cash Flow" in cf.index:
                    vals = cf.loc["Free Cash Flow"].dropna().values[:3]
                    if len(vals) > 0:
                        fcff_ttm = float(np.mean(vals))
                        flow_label = "FCF (avg)"
        except:
            pass

    fcff_ttm = safe_float(fcff_ttm, 1_000_000_000.0)  # never zero to keep the model alive

    st.markdown("### Starting Cash Flow")
    sc1, sc2 = st.columns(2)
    starting_cf = sc1.number_input(f"Starting {flow_label} (TTM) USD", min_value=0.0, value=fcff_ttm, step=1_000_000.0, format="%.0f",
                                   help="We use FCFF by default. If unavailable we fall back to FCF.")
    use_fcff = sc2.selectbox("Cash Flow Type", ["FCFF (enterprise)", "FCF (levered)"], index=0,
                             help="FCFF is preferred for DCF to EV. Choose FCF if you intentionally want levered FCF.")

    # --- 5-Year Growth (side-by-side)
    st.markdown("### 5-Year Growth Rate Assumptions")
    default_growths = [40.0, 25.0, 18.0, 12.0, 8.0]
    gcols = st.columns(5)
    user_growth_rates = []
    for i in range(5):
        user_growth_rates.append(
            gcols[i].slider(f"Year {i+1} Growth %", 0.0, 150.0, default_growths[i], 1.0, key=f"g_{i}")
        )

    # Build explicit CFs from the starting CF
    fcf_list = []
    prev = starting_cf
    for g in user_growth_rates:
        nxt = prev * (1.0 + g / 100.0)
        fcf_list.append(nxt)
        prev = nxt

    # --- Terminal assumption
    st.markdown("### Terminal Value Assumption")
    tcols = st.columns(5)
    method = tcols[0].selectbox("Method", ["Gordon Growth", "Exit EV/CF Multiple"], index=0)
    if method == "Gordon Growth":
        terminal_growth = tcols[1].slider("Terminal Growth Rate %", 0.0, 6.0, 3.0, 0.1) / 100.0
        exit_multiple = None
    else:
        terminal_growth = None
        exit_multiple = tcols[1].number_input("Exit EV/CF Multiple (x)", min_value=1.0, value=22.0, step=0.5,
                                              help="Enterprise multiple on final-year cash flow")

    # --- Discount rates (side-by-side)
    st.markdown("### Discount Rate Scenarios")
    dcols = st.columns(3)
    disc_bull = dcols[0].slider("Bull Discount Rate %", 0.0, 30.0, 8.0, 0.1)
    disc_base = dcols[1].slider("Base Discount Rate %", 0.0, 30.0, 9.0, 0.1)
    disc_bear = dcols[2].slider("Bear Discount Rate %", 0.0, 30.0, 10.0, 0.1)

    scenarios = {"Bull": disc_bull/100.0, "Base": disc_base/100.0, "Bear": disc_bear/100.0}

    # --- Compute scenarios
    def run_scenario(rate):
        res = dcf_from_fcf_list(
            fcf_list,
            discount_rate=rate,
            terminal_growth=terminal_growth,
            exit_multiple=exit_multiple,
            method="gordon" if method == "Gordon Growth" else "exit_multiple"
        )
        ev = res["ev"]
        equity = ev + net_cash_input  # EV + Net Cash = Equity (equity bridge)
        per_share = equity / shares_outstanding_input if shares_outstanding_input else None
        return res, ev, equity, per_share

    results = {name: run_scenario(r) for name, r in scenarios.items()}

    # --- Results table
    st.subheader("DCF Results")
    rows = []
    for name in ["Bull", "Base", "Bear"]:
        res, ev, eq, ps = results[name]
        rows.append({
            "Scenario": name,
            "Discount Rate %": scenarios[name]*100,
            "Enterprise Value (USD)": ev,
            "PV Terminal (USD)": res["pv_terminal"],
            "Terminal Value (undiscounted)": res["terminal"],
            "Equity Value (USD)": eq,
            "Implied Value / Share (USD)": ps if ps is not None else np.nan
        })

    df_results = pd.DataFrame(rows)
    for col in ["Enterprise Value (USD)", "PV Terminal (USD)", "Terminal Value (undiscounted)", "Equity Value (USD)"]:
        df_results[col] = df_results[col].map(lambda x: f"{x:,.0f}")
    df_results["Implied Value / Share (USD)"] = df_results["Implied Value / Share (USD)"].map(
        lambda x: f"{x:,.2f}" if isinstance(x, (int, float, np.number)) and not np.isnan(x) else "n/a"
    )
    st.table(df_results.set_index("Scenario"))

    # --- PV breakdown (Base)
    st.subheader("PV breakdown (Base scenario)")
    base_res, base_ev, base_eq, base_ps = results["Base"]
    labels = [f"Year {i}" for i in range(1, 1+len(base_res["pv_years"]))] + ["Terminal"]
    values = base_res["pv_years"] + [base_res["pv_terminal"]]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(labels, values)
    ax.set_ylabel("Present Value (USD)")
    ax.set_title("PV of projected cash flows and terminal (Base)")
    ax.ticklabel_format(axis='y', style='plain')
    st.pyplot(fig)

    # --- CSV Download of Base PV
    csv_buffer = BytesIO()
    out_df = pd.DataFrame({
        "Year": [f"Year {i}" for i in range(1, 1+len(base_res["pv_years"]))] + ["Terminal"],
        "Base PV USD": base_res["pv_years"] + [base_res["pv_terminal"]]
    })
    out_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    st.download_button('Download base PV CSV', data=csv_buffer, file_name=f'{ticker_symbol}_dcf_base_pv.csv', mime='text/csv')

    st.markdown("---")
    st.caption("This tool uses yfinance statements. FCFF preferred (enterprise DCF). Terminal can be Gordon Growth or Exit EV/CF multiple. Always sanity-check inputs.")