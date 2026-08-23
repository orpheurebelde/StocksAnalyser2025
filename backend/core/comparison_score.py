def _scaled(value, weak: float, strong: float, *, positive_only: bool = False):
    if value is None or (positive_only and value <= 0):
        return None
    score = (float(value) - weak) / (strong - weak) * 100
    return max(0.0, min(100.0, score))


def score_company(info: dict) -> tuple[float | None, float]:
    debt = info.get("totalDebt")
    cash = info.get("totalCash")
    fcf_margin = info.get("freeCashflowMargin")
    cash_to_debt = cash / debt if cash is not None and debt and debt > 0 else (2.0 if cash is not None and debt == 0 else None)
    factors = [
        (10, _scaled(info.get("trailingPE"), 40, 12, positive_only=True)),
        (10, _scaled(info.get("forwardPE"), 35, 10, positive_only=True)),
        (5, _scaled(info.get("priceToBook"), 10, 2, positive_only=True)),
        (5, _scaled(info.get("priceToSalesTrailing12Months"), 12, 2, positive_only=True)),
        (10, _scaled(info.get("returnOnEquity"), 0, 0.30)),
        (5, _scaled(info.get("returnOnAssets"), 0, 0.15)),
        (5, _scaled(info.get("grossMargins"), 0.20, 0.70)),
        (7.5, _scaled(info.get("operatingMargins"), 0, 0.35)),
        (7.5, _scaled(info.get("profitMargins"), 0, 0.30)),
        (15, _scaled(fcf_margin, -0.05, 0.25)),
        (10, _scaled(info.get("currentRatio"), 0.75, 2.0)),
        (10, _scaled(cash_to_debt, 0.25, 1.5)),
    ]
    available = [(weight, score) for weight, score in factors if score is not None]
    covered_weight = sum(weight for weight, _ in available)
    if not covered_weight:
        return None, 0.0
    score = sum(weight * value for weight, value in available) / covered_weight
    return round(score, 1), round(covered_weight, 1)
