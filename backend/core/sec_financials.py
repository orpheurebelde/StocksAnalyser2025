import json
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "sec"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "StocksAnalyser2025 contact@example.com")


def _load(url: str, path: Path, hours: int = 24):
    if path.exists() and datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) < timedelta(hours=hours):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)
    return payload


def _cik(symbol: str) -> str | None:
    payload = _load("https://www.sec.gov/files/company_tickers.json", CACHE_DIR / "company_tickers.json", 168)
    symbol = symbol.upper()
    for item in payload.values():
        if str(item.get("ticker") or "").upper() == symbol:
            return str(item["cik_str"]).zfill(10)
    return None


def _latest(facts: dict, concepts: tuple[str, ...], unit: str = "USD"):
    candidates = []
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for concept in concepts:
        rows = us_gaap.get(concept, {}).get("units", {}).get(unit, [])
        for row in rows:
            if row.get("form") in {"10-K", "10-Q", "20-F", "40-F"} and row.get("val") is not None:
                candidates.append(row)
    if not candidates:
        return None
    latest = max(candidates, key=lambda row: (str(row.get("filed") or ""), str(row.get("end") or "")))
    return float(latest["val"])


def _concept_rows(facts: dict, concepts, unit: str = "USD"):
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    rows = []
    for concept in concepts:
        for row in us_gaap.get(concept, {}).get("units", {}).get(unit, []):
            if row.get("form") in {"10-K", "10-Q", "20-F", "40-F"} and row.get("val") is not None:
                rows.append(row)
    return rows


def _capex_concepts(facts: dict) -> tuple[str, ...]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    return tuple(
        name for name in us_gaap
        if (name.startswith("PaymentsToAcquire") or name.startswith("PaymentsForAdditionsTo"))
        and ("PropertyPlantAndEquipment" in name or "ProductiveAssets" in name)
    )


def _latest_matching_pair(facts: dict, minuend_concepts, subtrahend_concepts):
    minuends = _concept_rows(facts, minuend_concepts)
    subtrahends = _concept_rows(facts, subtrahend_concepts)
    matches = []
    for left in minuends:
        period = (left.get("start"), left.get("end"))
        for right in subtrahends:
            if period == (right.get("start"), right.get("end")):
                matches.append((left, right))
    if not matches:
        return None
    return max(
        matches,
        key=lambda pair: (
            str(max(pair[0].get("filed") or "", pair[1].get("filed") or "")),
            str(pair[0].get("end") or ""),
        ),
    )


def _latest_matching_difference(facts: dict, minuend_concepts, subtrahend_concepts):
    pair = _latest_matching_pair(facts, minuend_concepts, subtrahend_concepts)
    if not pair:
        return None
    return float(pair[0]["val"]) - float(pair[1]["val"])


def get_sec_info_fields(symbol: str) -> dict:
    try:
        cik = _cik(symbol)
        if not cik:
            return {}
        facts = _load(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", CACHE_DIR / f"companyfacts_{cik}.json")
    except Exception:
        return {}

    revenue = _latest(facts, ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"))
    net_income = _latest(facts, ("NetIncomeLoss", "ProfitLoss"))
    operating_income = _latest(facts, ("OperatingIncomeLoss",))
    depreciation = _latest(facts, ("DepreciationDepletionAndAmortization", "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment"))
    cash = _latest(facts, ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"))
    debt = _latest(facts, ("LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtCurrent", "ShortTermBorrowings")) or 0
    debt += _latest(facts, ("LongTermDebtAndFinanceLeaseObligationsNoncurrent", "LongTermDebtNoncurrent")) or 0
    operating_cash_concepts = ("NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations")
    fcf_pair = _latest_matching_pair(facts, operating_cash_concepts, _capex_concepts(facts))
    free_cashflow = float(fcf_pair[0]["val"]) - float(fcf_pair[1]["val"]) if fcf_pair else None
    fcf_margin = None
    if fcf_pair:
        period = (fcf_pair[0].get("start"), fcf_pair[0].get("end"))
        matching_revenue = [
            row for row in _concept_rows(facts, ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"))
            if period == (row.get("start"), row.get("end")) and float(row["val"]) > 0
        ]
        if matching_revenue:
            latest_revenue = max(matching_revenue, key=lambda row: str(row.get("filed") or ""))
            fcf_margin = free_cashflow / float(latest_revenue["val"])
    fields = {
        "totalRevenue": revenue,
        "netIncomeToCommon": net_income,
        "ebitda": (operating_income + depreciation) if operating_income is not None and depreciation is not None else None,
        "totalCash": cash,
        "totalDebt": debt or None,
        "freeCashflow": free_cashflow,
        "freeCashflowMargin": fcf_margin,
        "shareBasedCompensation": _latest(facts, ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense")),
        "totalCashFromFinancingActivities": _latest(facts, ("NetCashProvidedByUsedInFinancingActivities",)),
    }
    return {key: value for key, value in fields.items() if value is not None}
