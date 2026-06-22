from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.auth import ensure_analysis_quota, record_analysis_use

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class DCFInput(BaseModel):
    ticker: str
    model_type: str = "Standard"
    starting_cf: float
    net_cash: float
    shares_outstanding: int
    growth_rates: List[float]
    discount_rates: Dict[str, float]  # Bull, Base, Bear as decimals
    terminal_growth: Optional[float] = None
    exit_multiple: Optional[float] = None
    # For Revenue model
    current_revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    current_margin: Optional[float] = None
    target_margin: Optional[float] = None
    tax_rate: Optional[float] = 0.21

def dcf_from_fcf_list(fcf_list, discount_rate, terminal_growth=None, exit_multiple=None):
    pv_years = []
    for i, fcf in enumerate(fcf_list, start=1):
        pv_years.append(fcf / ((1 + discount_rate) ** i))

    if terminal_growth is not None:
        g = terminal_growth
        terminal = fcf_list[-1] * (1 + g) / (discount_rate - g)
    else:
        mult = exit_multiple or 10.0
        terminal = fcf_list[-1] * mult

    N = len(fcf_list)
    pv_terminal = terminal / ((1 + discount_rate) ** N)
    ev = sum(pv_years) + pv_terminal
    return {"pv_years": pv_years, "pv_terminal": pv_terminal, "ev": ev, "terminal": terminal}

@router.post("/calculate")
@limiter.limit("20/minute")
def calculate_dcf(request: Request, data: DCFInput):
    try:
        ensure_analysis_quota(request.state.user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    fcf_list = []
    
    if data.model_type == "Revenue":
        prev_rev = data.current_revenue or 0.0
        c_margin = data.current_margin or 0.0
        t_margin = data.target_margin or 0.15
        rev_g = data.revenue_growth or 0.10
        tax = data.tax_rate or 0.21
        
        for i in range(1, 6): # 5 years
            nxt_rev = prev_rev * (1.0 + rev_g)
            # Interpolate margin linearly over 5 years
            margin = c_margin + (t_margin - c_margin) * (i / 5.0)
            ebit = nxt_rev * margin
            fcf = ebit * (1.0 - tax)
            fcf_list.append(fcf)
            prev_rev = nxt_rev
    else:
        # Standard
        prev = data.starting_cf
        for g in data.growth_rates:
            nxt = prev * (1.0 + g)
            fcf_list.append(nxt)
            prev = nxt

    results = {}
    for name, rate in data.discount_rates.items():
        res = dcf_from_fcf_list(fcf_list, rate, data.terminal_growth, data.exit_multiple)
        ev = res["ev"]
        equity = ev + data.net_cash
        per_share = equity / data.shares_outstanding if data.shares_outstanding else None
        
        results[name] = {
            "ev": ev,
            "equity": equity,
            "per_share": per_share,
            "pv_terminal": res["pv_terminal"],
            "terminal": res["terminal"],
            "pv_years": res["pv_years"]
        }
        
    record_analysis_use(request.state.user["id"], "dcf")
    return results
