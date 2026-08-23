from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.auth import ensure_analysis_quota, record_analysis_use

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
FORECAST_YEARS = 5


class DCFInput(BaseModel):
    ticker: str
    model_type: str = "Standard"
    starting_cf: float
    net_cash: float
    shares_outstanding: float
    growth_rates: List[float]
    discount_rates: Dict[str, float]
    terminal_growth: Optional[float] = 0.025
    exit_multiple: Optional[float] = None
    current_price: Optional[float] = None
    current_revenue: Optional[float] = None
    revenue_growth_rates: Optional[List[float]] = None
    revenue_growth: Optional[float] = None
    current_margin: Optional[float] = None
    target_margin: Optional[float] = None
    tax_rate: Optional[float] = 0.21


def _validate(data: DCFInput) -> None:
    if data.model_type not in {"Standard", "Revenue"}:
        raise HTTPException(status_code=422, detail="model_type must be Standard or Revenue.")
    if data.shares_outstanding <= 0:
        raise HTTPException(status_code=422, detail="Shares outstanding must be greater than zero.")
    if set(data.discount_rates) != {"Bull", "Base", "Bear"}:
        raise HTTPException(status_code=422, detail="Discount rates must contain Bull, Base and Bear.")
    if any(rate <= 0 or rate > 0.50 for rate in data.discount_rates.values()):
        raise HTTPException(status_code=422, detail="Discount rates must be between 0% and 50%.")
    if data.terminal_growth is not None and any(rate <= data.terminal_growth for rate in data.discount_rates.values()):
        raise HTTPException(status_code=422, detail="Every discount rate must exceed terminal growth.")
    if data.terminal_growth is None and (data.exit_multiple is None or data.exit_multiple <= 0):
        raise HTTPException(status_code=422, detail="Provide a positive exit multiple when terminal growth is disabled.")
    if data.model_type == "Standard" and len(data.growth_rates) != FORECAST_YEARS:
        raise HTTPException(status_code=422, detail="Provide exactly five annual FCF growth rates.")
    if data.model_type == "Revenue":
        rates = data.revenue_growth_rates or ([data.revenue_growth] * FORECAST_YEARS if data.revenue_growth is not None else [])
        if not data.current_revenue or data.current_revenue <= 0 or len(rates) != FORECAST_YEARS:
            raise HTTPException(status_code=422, detail="Revenue model requires positive revenue and five annual growth rates.")
        if data.current_margin is None or data.target_margin is None:
            raise HTTPException(status_code=422, detail="Revenue model requires current and target margins.")
    all_growth = data.growth_rates if data.model_type == "Standard" else (data.revenue_growth_rates or [data.revenue_growth] * FORECAST_YEARS)
    if any(rate is None or rate < -0.95 or rate > 3.0 for rate in all_growth):
        raise HTTPException(status_code=422, detail="Annual growth rates must be between -95% and 300%.")


def _forecast(data: DCFInput) -> List[dict]:
    rows = []
    if data.model_type == "Revenue":
        revenue = float(data.current_revenue)
        rates = data.revenue_growth_rates or [data.revenue_growth] * FORECAST_YEARS
        current_margin = float(data.current_margin)
        target_margin = float(data.target_margin)
        tax_rate = float(data.tax_rate if data.tax_rate is not None else 0.21)
        for year, growth in enumerate(rates, start=1):
            revenue *= 1 + growth
            margin = current_margin + (target_margin - current_margin) * year / FORECAST_YEARS
            fcf = revenue * margin * (1 - tax_rate)
            rows.append({"year": year, "growth_rate": growth, "revenue": revenue, "margin": margin, "fcf": fcf})
    else:
        fcf = data.starting_cf
        for year, growth in enumerate(data.growth_rates, start=1):
            fcf *= 1 + growth
            rows.append({"year": year, "growth_rate": growth, "revenue": None, "margin": None, "fcf": fcf})
    return rows


def dcf_from_fcf_list(fcf_list, discount_rate, terminal_growth=None, exit_multiple=None):
    pv_years = [fcf / ((1 + discount_rate) ** year) for year, fcf in enumerate(fcf_list, start=1)]
    if terminal_growth is not None:
        terminal = fcf_list[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    else:
        terminal = fcf_list[-1] * exit_multiple
    pv_terminal = terminal / ((1 + discount_rate) ** len(fcf_list))
    return {"pv_years": pv_years, "pv_terminal": pv_terminal, "ev": sum(pv_years) + pv_terminal, "terminal": terminal}


def _scenario(data: DCFInput, forecast: List[dict], rate: float) -> dict:
    result = dcf_from_fcf_list([row["fcf"] for row in forecast], rate, data.terminal_growth, data.exit_multiple)
    equity = result["ev"] + data.net_cash
    per_share = equity / data.shares_outstanding
    upside = ((per_share / data.current_price) - 1) if data.current_price and data.current_price > 0 else None
    terminal_share = result["pv_terminal"] / result["ev"] if result["ev"] else None
    return {**result, "equity": equity, "per_share": per_share, "upside": upside, "margin_of_safety": upside, "discount_rate": rate, "terminal_share": terminal_share}


def _sensitivity(data: DCFInput, forecast: List[dict]) -> dict:
    base_rate = data.discount_rates["Base"]
    base_growth = data.terminal_growth
    rates = [round(base_rate + step, 4) for step in (-0.02, -0.01, 0, 0.01, 0.02)]
    growths = [round(base_growth + step, 4) for step in (-0.01, -0.005, 0, 0.005, 0.01)]
    values = []
    for rate in rates:
        row = []
        for growth in growths:
            if rate <= growth:
                row.append(None)
                continue
            result = dcf_from_fcf_list([item["fcf"] for item in forecast], rate, growth, None)
            row.append((result["ev"] + data.net_cash) / data.shares_outstanding)
        values.append(row)
    return {"discount_rates": rates, "terminal_growth_rates": growths, "values": values}


def _warnings(data: DCFInput, scenarios: dict) -> List[str]:
    warnings = []
    if data.terminal_growth is not None and data.terminal_growth > 0.035:
        warnings.append("Terminal growth above 3.5% may exceed sustainable long-run economic growth.")
    selected_growth = data.growth_rates if data.model_type == "Standard" else (data.revenue_growth_rates or [data.revenue_growth] * FORECAST_YEARS)
    if any(abs(rate) > 0.40 for rate in selected_growth):
        warnings.append("At least one annual growth assumption exceeds 40% in absolute terms.")
    terminal_share = scenarios["Base"].get("terminal_share")
    if terminal_share is not None and terminal_share > 0.80:
        warnings.append("Terminal value exceeds 80% of enterprise value; result is highly assumption-sensitive.")
    if data.starting_cf <= 0 and data.model_type == "Standard":
        warnings.append("Standard FCF model starts with non-positive cash flow; Revenue model may be more informative.")
    return warnings


@router.post("/calculate")
@limiter.limit("20/minute")
def calculate_dcf(request: Request, data: DCFInput):
    try:
        ensure_analysis_quota(request.state.user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    _validate(data)
    forecast = _forecast(data)
    scenarios = {name: _scenario(data, forecast, rate) for name, rate in data.discount_rates.items()}
    response = {
        "ticker": data.ticker.upper(), "model_type": data.model_type, "scenarios": scenarios,
        "forecast": forecast, "sensitivity": _sensitivity(data, forecast) if data.terminal_growth is not None else None,
        "warnings": _warnings(data, scenarios),
    }
    record_analysis_use(request.state.user["id"], "dcf")
    return response
