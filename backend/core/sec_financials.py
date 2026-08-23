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
    operating_cash = _latest(facts, ("NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"))
    capex = _latest(facts, ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForAdditionsToPropertyPlantAndEquipment"))
    fields = {
        "totalRevenue": revenue,
        "netIncomeToCommon": net_income,
        "ebitda": (operating_income + depreciation) if operating_income is not None and depreciation is not None else None,
        "totalCash": cash,
        "totalDebt": debt or None,
        "freeCashflow": (operating_cash - capex) if operating_cash is not None and capex is not None else None,
        "shareBasedCompensation": _latest(facts, ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense")),
        "totalCashFromFinancingActivities": _latest(facts, ("NetCashProvidedByUsedInFinancingActivities",)),
    }
    return {key: value for key, value in fields.items() if value is not None}
