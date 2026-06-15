import io
import json
import os
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone
from typing import Any

from core.yfinance_client import get_statement

DB_ENV_NAME = "QUARTER_EARNINGS_DB_PATH"
POSTGRES_ENV_NAMES = ("DATABASE_URL", "POSTGRES_URL")
POSTGRES_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
DB_PATH = os.getenv(DB_ENV_NAME) or os.path.join(os.path.dirname(os.path.dirname(__file__)), "quarter_earnings.sqlite")
MAX_TEXT_CHARS = 90000
FINANCIAL_NUMBER_RE = re.compile(r"\(?-?\$?\s*\d[\d,]*(?:\.\d+)?\)?")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "StocksAnalyser2025 quarter-earnings almeida1976marco@gmail.com")
XBRL_TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "research_development": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentInProcess",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
        "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost",
        "ResearchAndDevelopmentExpenseSoftware",
        "ResearchDevelopmentAndEngineeringExpense",
    ],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "total_debt": ["LongTermDebtAndFinanceLeaseObligations", "LongTermDebt", "DebtCurrent", "LongTermDebtAndFinanceLeaseObligationsCurrent"],
}
XBRL_TAG_PATTERNS = {
    "research_development": [
        re.compile(r"research.*development.*expense", re.I),
        re.compile(r"research.*development.*in.*process", re.I),
        re.compile(r"research.*development.*engineering", re.I),
        re.compile(r"product.*development.*expense", re.I),
    ],
    "total_debt": [
        re.compile(r"(longterm|long.term|shortterm|short.term|current).*debt", re.I),
        re.compile(r"debt.*(obligation|liabilit|current)", re.I),
    ],
}
SEC_FORMS = {"10-Q", "10-K"}
FLOW_STATEMENT_KEYS = {"revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "research_development"}

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


def _using_postgres() -> bool:
    return bool(POSTGRES_URL)


def _placeholder() -> str:
    return "%s" if _using_postgres() else "?"


def _connect(row_factory: bool = False):
    if _using_postgres():
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set, but psycopg is not installed. Add psycopg[binary] to backend requirements.")
        return psycopg.connect(POSTGRES_URL, row_factory=dict_row if row_factory else None)
    conn = sqlite3.connect(DB_PATH)
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: Any) -> dict[str, Any]:
    return row if isinstance(row, dict) else dict(row)


def init_db():
    if _using_postgres():
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quarter_reports (
                    id SERIAL PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    fiscal_quarter TEXT,
                    report_date TEXT,
                    source_url TEXT,
                    source_type TEXT NOT NULL,
                    company_name TEXT,
                    sector TEXT,
                    industry TEXT,
                    metrics_json TEXT NOT NULL,
                    report_text TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quarter_analyses (
                    id SERIAL PRIMARY KEY,
                    report_id INTEGER NOT NULL REFERENCES quarter_reports(id),
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    score_json TEXT NOT NULL,
                    analysis_markdown TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        return

    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quarter_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                fiscal_quarter TEXT,
                report_date TEXT,
                source_url TEXT,
                source_type TEXT NOT NULL,
                company_name TEXT,
                sector TEXT,
                industry TEXT,
                metrics_json TEXT NOT NULL,
                report_text TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quarter_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                score_json TEXT NOT NULL,
                analysis_markdown TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(report_id) REFERENCES quarter_reports(id)
            )
            """
        )


def get_db_status() -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        report_count = conn.execute("SELECT COUNT(*) FROM quarter_reports").fetchone()[0]
        analysis_count = conn.execute("SELECT COUNT(*) FROM quarter_analyses").fetchone()[0]
    if _using_postgres():
        configured_env = "DATABASE_URL" if os.getenv("DATABASE_URL") else "POSTGRES_URL"
        return {
            "backend": "postgres",
            "env_name": configured_env,
            "env_configured": True,
            "exists": True,
            "directory_writable": True,
            "report_count": report_count,
            "analysis_count": analysis_count,
            "persistence": "postgres_configured",
        }

    db_dir = os.path.dirname(DB_PATH) or "."
    env_configured = bool(os.getenv(DB_ENV_NAME))
    return {
        "backend": "sqlite",
        "path": DB_PATH,
        "directory": db_dir,
        "env_name": DB_ENV_NAME,
        "env_configured": env_configured,
        "exists": os.path.exists(DB_PATH),
        "directory_writable": os.access(db_dir, os.W_OK),
        "report_count": report_count,
        "analysis_count": analysis_count,
        "persistence": "persistent_disk_configured" if env_configured else "default_ephemeral_path",
    }


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clean_pdf_text(text: str) -> str:
    text = text.replace("\r", "\n").replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _safe_number(raw: str | None) -> float | None:
    if not raw:
        return None
    value = raw.replace(",", "").replace("$", "").replace(" ", "").strip()
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    if value.startswith("-"):
        negative = True
        value = value[1:]
    try:
        parsed = float(value)
    except ValueError:
        return None
    return -parsed if negative else parsed


def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text(extraction_mode="layout") or "")
            except TypeError:
                pages.append(page.extract_text() or "")
            if sum(len(text) for text in pages) >= MAX_TEXT_CHARS:
                break
        text = _clean_pdf_text("\n".join(pages))
    except Exception as exc:
        raise RuntimeError("Could not read PDF text. Upload a selectable 10-Q PDF, not a scanned image PDF.") from exc
    if not text:
        raise RuntimeError("PDF loaded, but no selectable text was found. Scanned 10-Q PDFs need OCR first.")
    return text[:MAX_TEXT_CHARS]


def _extract_company_name(text: str, ticker: str | None) -> str:
    match = re.search(r"Exact name of registrant as specified in its charter\)?[ \t]*([A-Z0-9][A-Z0-9 .,&'/-]{3,120})", text, re.I)
    if match:
        return match.group(1).strip(" .")
    return (ticker or "UNKNOWN").upper()


def _extract_ticker(text: str, filename: str | None = None, ticker_hint: str | None = None) -> str:
    if ticker_hint and ticker_hint.upper() not in {"AUTO", "UNKNOWN"}:
        return ticker_hint.upper().strip()
    ignored = {"FORM", "NYSE", "LLC", "INC", "THE", "PDF"}
    symbol_table = re.search(r"Trading\s+Symbol\(s\).*?([A-Z]{1,5})\s+(?:The\s+)?(?:Nasdaq|NYSE|New York Stock Exchange|Nasdaq Stock Market|NYSE American)", text, re.I)
    if symbol_table:
        symbol = symbol_table.group(1).upper()
        if symbol not in ignored:
            return symbol
    exchange_table = re.search(r"\b([A-Z]{1,5})\s+(?:The\s+)?(?:Nasdaq Stock Market|Nasdaq|New York Stock Exchange|NYSE|NYSE American)\b", text, re.I)
    if exchange_table:
        symbol = exchange_table.group(1).upper()
        if symbol not in ignored:
            return symbol
    inline_symbol = re.search(r"(?:ticker|trading symbol)\s*[:\-]?\s*([A-Z]{1,5})\b", text, re.I)
    if inline_symbol:
        symbol = inline_symbol.group(1).upper()
        if symbol not in ignored:
            return symbol
    if filename:
        file_symbol = re.search(r"\b([A-Z]{1,5})\b", filename.upper().replace("10-Q", " "))
        if file_symbol:
            symbol = file_symbol.group(1)
            if symbol not in ignored:
                return symbol
    return "UNKNOWN"


def _extract_period(text: str) -> dict[str, str | None]:
    period_match = re.search(r"quarterly period ended\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    report_match = re.search(r"Commission File Number.*?(\d{4})", text, re.I)
    return {
        "fiscal_quarter": period_match.group(1) if period_match else None,
        "report_date": period_match.group(1) if period_match else report_match.group(1) if report_match else None,
    }


def _extract_accession(filename: str | None, text: str) -> str | None:
    source = f"{filename or ''} {text[:5000]}"
    match = re.search(r"(?<!\d)(\d{10})-(\d{2})-(\d{6})(?!\d)", source)
    if match:
        return "-".join(match.groups())
    compact = re.search(r"(?<!\d)(\d{10})(\d{2})(\d{6})(?!\d)", source)
    if compact:
        return f"{compact.group(1)}-{compact.group(2)}-{compact.group(3)}"
    return None


def _cik_from_accession(accession: str | None) -> str | None:
    if not accession:
        return None
    cik = accession.split("-")[0].lstrip("0")
    return cik or None


def _date_iso(value: str | None) -> str | None:
    parsed = _parse_period_date(value)
    return parsed.strftime("%Y-%m-%d") if parsed else None


def _load_sec_companyfacts(cik: str) -> dict[str, Any] | None:
    padded = cik.zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def _cik_from_ticker(ticker: str | None) -> str | None:
    if not ticker or ticker == "UNKNOWN":
        return None
    try:
        request = urllib.request.Request(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    target = ticker.upper()
    for item in data.values():
        if str(item.get("ticker", "")).upper() == target:
            return str(item.get("cik_str"))
    return None


def _find_accession_for_period(companyfacts: dict[str, Any], report_date: str | None) -> str | None:
    if not report_date:
        return None
    counts: dict[str, int] = {}
    for tags in XBRL_TAGS.values():
        for tag in tags:
            fact = companyfacts.get("facts", {}).get("us-gaap", {}).get(tag)
            if not fact:
                continue
            for unit_rows in fact.get("units", {}).values():
                for row in unit_rows:
                    if row.get("form") == "10-Q" and row.get("end") == report_date and row.get("accn"):
                        counts[row["accn"]] = counts.get(row["accn"], 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _xbrl_facts_for_tag(companyfacts: dict[str, Any], tag: str, accession: str) -> list[dict[str, Any]]:
    fact = companyfacts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not fact:
        return []
    rows = []
    for unit_rows in fact.get("units", {}).values():
        rows.extend(row for row in unit_rows if row.get("accn") == accession and row.get("val") is not None)
    return rows


def _xbrl_facts_all_accessions(companyfacts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    fact = companyfacts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not fact:
        return []
    rows = []
    for unit_rows in fact.get("units", {}).values():
        rows.extend(row for row in unit_rows if row.get("val") is not None)
    return rows


def _iter_companyfacts_concepts(companyfacts: dict[str, Any]):
    for taxonomy, concepts in companyfacts.get("facts", {}).items():
        if not isinstance(concepts, dict):
            continue
        for tag, fact in concepts.items():
            yield taxonomy, tag, fact


def _matching_xbrl_tags(companyfacts: dict[str, Any], key: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    seen = set()
    facts = companyfacts.get("facts", {})
    for tag in XBRL_TAGS.get(key, []):
        for taxonomy, concepts in facts.items():
            if isinstance(concepts, dict) and tag in concepts and (taxonomy, tag) not in seen:
                matches.append((taxonomy, tag))
                seen.add((taxonomy, tag))
    for pattern in XBRL_TAG_PATTERNS.get(key, []):
        for taxonomy, tag, fact in _iter_companyfacts_concepts(companyfacts):
            if (taxonomy, tag) in seen:
                continue
            label = " ".join(str(fact.get(field) or "") for field in ("label", "description"))
            haystack = f"{tag} {label}"
            if pattern.search(haystack):
                matches.append((taxonomy, tag))
                seen.add((taxonomy, tag))
    return matches


def _xbrl_facts_for_concept(companyfacts: dict[str, Any], taxonomy: str, tag: str, accession: str) -> list[dict[str, Any]]:
    fact = companyfacts.get("facts", {}).get(taxonomy, {}).get(tag)
    if not fact:
        return []
    rows = []
    for unit_rows in fact.get("units", {}).values():
        rows.extend(row for row in unit_rows if row.get("accn") == accession and row.get("val") is not None)
    return rows


def _duration_days(row: dict[str, Any]) -> int | None:
    if not row.get("start") or not row.get("end"):
        return None
    try:
        return (datetime.fromisoformat(row["end"]) - datetime.fromisoformat(row["start"])).days
    except ValueError:
        return None


def _derive_10k_q4_statements(companyfacts: dict[str, Any], statements: dict[str, Any]) -> dict[str, Any]:
    updated = dict(statements)
    for key in FLOW_STATEMENT_KEYS:
        item = statements.get(key)
        if not item or item.get("current") is None or not item.get("xbrl_start") or not item.get("xbrl_end"):
            continue
        annual_start = item["xbrl_start"]
        annual_end = item["xbrl_end"]
        annual_days = _duration_days({"start": annual_start, "end": annual_end})
        if annual_days is None or annual_days < 300:
            continue
        tag = item.get("label")
        if not tag:
            continue
        taxonomy = item.get("taxonomy") or "us-gaap"
        fact = companyfacts.get("facts", {}).get(taxonomy, {}).get(tag)
        all_rows = []
        if fact:
            for unit_rows in fact.get("units", {}).values():
                all_rows.extend(row for row in unit_rows if row.get("val") is not None)
        if not all_rows:
            all_rows = _xbrl_facts_all_accessions(companyfacts, tag)
        q3_candidates = [
            row for row in all_rows
            if row.get("form") == "10-Q"
            and row.get("start") == annual_start
            and row.get("end")
            and row["end"] < annual_end
            and _duration_days(row) is not None
            and _duration_days(row) >= 180
        ]
        if not q3_candidates:
            continue
        q3_row = max(q3_candidates, key=lambda row: row["end"])
        current = float(item["current"]) - float(q3_row["val"])

        prior = None
        prior_annual = _select_xbrl_prior(all_rows, {"start": annual_start, "end": annual_end, "val": item["current"]}, True)
        if prior_annual and prior_annual.get("start") and prior_annual.get("end"):
            prior_q3_candidates = [
                row for row in all_rows
                if row.get("form") == "10-Q"
                and row.get("start") == prior_annual.get("start")
                and row.get("end")
                and row["end"] < prior_annual.get("end")
                and _duration_days(row) is not None
                and _duration_days(row) >= 180
            ]
            if prior_q3_candidates:
                prior_q3_row = max(prior_q3_candidates, key=lambda row: row["end"])
                prior = float(prior_annual["val"]) - float(prior_q3_row["val"])

        updated[key] = {
            **item,
            "current": current,
            "prior": prior,
            "growth": _growth(current, prior),
            "confidence": "xbrl_sec_companyfacts_q4_derived",
            "derived_from": "10-K FY value minus latest 10-Q YTD value",
            "xbrl_start": q3_row["end"],
            "xbrl_end": annual_end,
            "annual_value": item["current"],
            "ytd_subtracted": float(q3_row["val"]),
        }
    return updated


def _select_xbrl_current(rows: list[dict[str, Any]], report_date: str | None, prefer_longest: bool) -> dict[str, Any] | None:
    if not rows:
        return None
    ended = [row for row in rows if row.get("end") == report_date] if report_date else rows
    candidates = ended or rows
    duration_rows = [(row, _duration_days(row)) for row in candidates if _duration_days(row) is not None]
    if duration_rows:
        key = (lambda item: item[1]) if prefer_longest else (lambda item: -item[1])
        return max(duration_rows, key=key)[0]
    instant_rows = [row for row in candidates if not row.get("start")]
    return instant_rows[-1] if instant_rows else candidates[-1]


def _select_xbrl_prior(rows: list[dict[str, Any]], current: dict[str, Any], prefer_longest: bool) -> dict[str, Any] | None:
    current_end = current.get("end")
    current_days = _duration_days(current)
    prior_rows = [row for row in rows if row is not current and row.get("end") != current_end]
    if not prior_rows:
        return None
    if current_days is None:
        before = [row for row in prior_rows if row.get("end") and current_end and row["end"] < current_end]
        return max(before, key=lambda row: row["end"]) if before else prior_rows[-1]
    candidates = [(row, _duration_days(row)) for row in prior_rows if _duration_days(row) is not None]
    if candidates:
        same_profile = [item for item in candidates if (item[1] >= 180) == prefer_longest]
        pool = same_profile or candidates
        return min(pool, key=lambda item: (abs(item[1] - current_days), item[0].get("end", "")))[0]
    return None


def _xbrl_item(companyfacts: dict[str, Any], accession: str, key: str, report_date: str | None) -> dict[str, Any] | None:
    prefer_longest = key == "operating_cash_flow"
    for taxonomy, tag in _matching_xbrl_tags(companyfacts, key):
        rows = _xbrl_facts_for_concept(companyfacts, taxonomy, tag, accession)
        current = _select_xbrl_current(rows, report_date, prefer_longest)
        if not current:
            continue
        prior = _select_xbrl_prior(rows, current, prefer_longest)
        current_value = float(current["val"])
        prior_value = float(prior["val"]) if prior else None
        return {
            "label": tag,
            "current": current_value,
            "prior": prior_value,
            "growth": _growth(current_value, prior_value),
            "confidence": "xbrl_sec_companyfacts",
            "accession": accession,
            "taxonomy": taxonomy,
            "xbrl_end": current.get("end"),
            "xbrl_start": current.get("start"),
        }
    return None


def _xbrl_statements(accession: str | None, ticker: str | None, report_date: str | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    cik = _cik_from_accession(accession) or _cik_from_ticker(ticker)
    if not cik:
        return {}, None
    companyfacts = _load_sec_companyfacts(cik)
    if not companyfacts:
        return {}, {"accession": accession, "cik": cik, "available": False}
    report_date_iso = _date_iso(report_date)
    accession = accession or _find_accession_for_period(companyfacts, report_date_iso)
    if not accession:
        return {}, {"accession": None, "cik": cik, "available": False, "source": "sec_companyfacts"}
    statements = {}
    for key in XBRL_TAGS:
        item = _xbrl_item(companyfacts, accession, key, report_date_iso)
        if item:
            statements[key] = item
    return statements, {
        "accession": accession,
        "cik": cik,
        "available": bool(statements),
        "source": "sec_companyfacts",
    }


def _number_tokens(fragment: str) -> list[str]:
    pattern = r"(?<![A-Za-z])\$?\s*\(?-?\d[\d,]*(?:\.\d+)?\)?"
    return [match.group(0) for match in re.finditer(pattern, fragment)]


def _label_regex(label: str) -> str:
    words = [re.escape(part) for part in label.split()]
    return r"\b" + r"\s+".join(words) + r"\b"


def _extract_line_item(text: str, labels: list[str]) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for label in labels:
        line_pattern = re.compile(_label_regex(label), re.I)
        for line_index, line in enumerate(lines):
            match = line_pattern.search(line)
            if not match:
                continue
            fragment = line[match.end():]
            tokens = _number_tokens(fragment)
            if len(tokens) < 2 and line_index + 1 < len(lines):
                tokens = tokens + _number_tokens(lines[line_index + 1])
            if not tokens:
                continue
            current = _safe_number(tokens[0])
            prior = _safe_number(tokens[1]) if len(tokens) > 1 else None
            if current is not None:
                scale = _statement_scale(lines, line_index)
                return {
                    "label": label,
                    "current": current * scale,
                    "prior": prior * scale if prior is not None else None,
                    "growth": _growth(current * scale, prior * scale if prior is not None else None),
                    "confidence": "high_line_match" if len(tokens) > 1 else "medium_single_value",
                    "scale": scale,
                }

    flat_text = _clean_text(text)
    for label in labels:
        flexible_label = re.escape(label).replace(r"\ ", r"\s+")
        pattern = rf"{flexible_label}\s+\$?\(?([\d,]+(?:\.\d+)?)\)?\s+\$?\(?([\d,]+(?:\.\d+)?)\)?"
        match = re.search(pattern, flat_text, re.I)
        if match:
            current = _safe_number(match.group(1))
            prior = _safe_number(match.group(2))
            return {
                "label": label,
                "current": current,
                "prior": prior,
                "growth": _growth(current, prior),
                "confidence": "low_flat_match",
            }
    return {"label": labels[0], "current": None, "prior": None, "confidence": "missing"}


def _financial_lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]


def _line_has_label(line: str, label: str) -> bool:
    normalized_line = re.sub(r"\s+", " ", line).lower()
    normalized_label = re.sub(r"\s+", " ", label).lower()
    return normalized_line.startswith(normalized_label) or re.search(rf"\b{re.escape(normalized_label)}\b", normalized_line) is not None


def _numbers_after_label(line: str, label: str) -> list[str]:
    match = re.search(re.escape(label).replace(r"\ ", r"\s+"), line, re.I)
    search_area = line[match.end():] if match else line
    return FINANCIAL_NUMBER_RE.findall(search_area)


def _statement_scale(lines: list[str], line_index: int) -> int:
    context_start = max(0, line_index - 12)
    context = " ".join(lines[context_start:line_index + 1]).lower()
    if re.search(r"\bin\s+millions\b|amounts\s+in\s+millions|dollars\s+in\s+millions", context):
        return 1_000_000
    if re.search(r"\bin\s+thousands\b|amounts\s+in\s+thousands|dollars\s+in\s+thousands", context):
        return 1_000
    return 1


def _calculate_operating_cash_flow_from_10q(text: str) -> dict[str, Any] | None:
    component_groups = [
        ["Net income", "Net earnings"],
        ["Depreciation and amortization", "Depreciation", "Amortization"],
        ["Stock-based compensation", "Share-based compensation"],
        ["Deferred income taxes", "Deferred taxes"],
        ["Accounts receivable", "Receivables"],
        ["Inventories", "Inventory"],
        ["Prepaid expenses and other assets", "Other current assets"],
        ["Accounts payable"],
        ["Accrued expenses", "Accrued liabilities"],
        ["Other operating activities", "Other assets and liabilities"],
    ]
    current_total = 0.0
    prior_total = 0.0
    used = []
    for labels in component_groups:
        item = _extract_line_item(text, labels)
        if item.get("current") is None:
            continue
        current_total += item["current"]
        prior_total += item["prior"] or 0
        used.append(item["label"])
    if len(used) < 3:
        return None
    prior = prior_total if prior_total != 0 else None
    return {
        "label": "Calculated Operating Cash Flow",
        "current": current_total,
        "prior": prior,
        "growth": _growth(current_total, prior),
        "confidence": "calculated_from_10q_components",
        "components": used,
    }


def _growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return (current - prior) / abs(prior)


def _is_missing_value(item: dict[str, Any] | None) -> bool:
    return not item or item.get("current") is None


def _parse_period_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _select_statement_column(columns, report_date: str | None):
    if not columns:
        return None, None
    dated_columns = []
    for column in columns:
        try:
            dated_columns.append((column, datetime.fromisoformat(str(getattr(column, "date", lambda: column)()))))
        except Exception:
            try:
                dated_columns.append((column, datetime.fromisoformat(str(column)[:10])))
            except Exception:
                continue
    dated_columns.sort(key=lambda item: item[1], reverse=True)
    if not dated_columns:
        return columns[0], columns[1] if len(columns) > 1 else None
    target = _parse_period_date(report_date)
    if not target:
        return None, None
    matches = [(idx, column, abs((date_value - target).days)) for idx, (column, date_value) in enumerate(dated_columns)]
    idx, column, distance = min(matches, key=lambda item: item[2])
    if idx != 0 or distance > 75:
        return None, None
    prior = dated_columns[idx + 1][0] if idx + 1 < len(dated_columns) else None
    return column, prior


def _yfinance_operating_cash_flow(ticker: str, report_date: str | None = None) -> dict[str, Any] | None:
    if not ticker or ticker == "UNKNOWN":
        return None
    try:
        cashflow = get_statement(ticker, "quarterly_cashflow")
    except Exception:
        return None
    if cashflow is None or getattr(cashflow, "empty", True):
        return None
    labels = [
        "Operating Cash Flow",
        "Total Cash From Operating Activities",
        "Net Cash Provided By Operating Activities",
        "Cash Flow From Continuing Operating Activities",
    ]
    row = None
    for label in labels:
        if label in cashflow.index:
            row = cashflow.loc[label]
            break
    if row is None:
        for idx in cashflow.index:
            if "operating" in str(idx).lower() and "cash" in str(idx).lower():
                row = cashflow.loc[idx]
                break
    if row is None:
        return None
    current_col, prior_col = _select_statement_column(list(cashflow.columns), report_date)
    if current_col is None:
        return None
    current_raw = row.get(current_col)
    prior_raw = row.get(prior_col) if prior_col is not None else None
    if current_raw is None or str(current_raw) == "nan":
        return None
    current = float(current_raw)
    prior = None if prior_raw is None or str(prior_raw) == "nan" else float(prior_raw)
    return {
        "label": "Operating Cash Flow",
        "current": current,
        "prior": prior,
        "growth": _growth(current, prior),
        "confidence": "yfinance_period_fallback",
    }


def enrich_missing_operating_cash_flow(metrics: dict[str, Any], ticker: str, report_date: str | None = None) -> tuple[dict[str, Any], bool]:
    statements = metrics.setdefault("statements", {})
    if not _is_missing_value(statements.get("operating_cash_flow")):
        return metrics, False
    fallback = _yfinance_operating_cash_flow(ticker, report_date)
    if not fallback:
        return metrics, False
    statements["operating_cash_flow"] = fallback
    return metrics, True


def backfill_missing_operating_cash_flow(ticker: str | None = None) -> int:
    init_db()
    ph = _placeholder()
    query = """
        SELECT id, ticker, metrics_json, report_date, report_text
        FROM quarter_reports
        WHERE id IN (SELECT MAX(id) FROM quarter_reports GROUP BY ticker)
    """
    params: tuple[Any, ...] = ()
    if ticker:
        query = f"""
            SELECT id, ticker, metrics_json, report_date, report_text
            FROM quarter_reports
            WHERE ticker = {ph}
            ORDER BY id DESC
            LIMIT 1
        """
        params = (ticker.upper(),)
    changed = 0
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        for report_id, row_ticker, metrics_json, report_date, report_text in rows:
            try:
                metrics = json.loads(metrics_json)
            except Exception:
                continue
            if _is_missing_value(metrics.get("statements", {}).get("operating_cash_flow")) and report_text:
                calculated = _calculate_operating_cash_flow_from_10q(_clean_pdf_text(report_text))
                if calculated:
                    metrics.setdefault("statements", {})["operating_cash_flow"] = calculated
                    updated = True
                else:
                    metrics, updated = enrich_missing_operating_cash_flow(metrics, row_ticker, report_date)
            else:
                metrics, updated = enrich_missing_operating_cash_flow(metrics, row_ticker, report_date)
            if updated:
                conn.execute(f"UPDATE quarter_reports SET metrics_json = {ph} WHERE id = {ph}", (json.dumps(metrics), report_id))
                changed += 1
    return changed


def reprocess_stored_reports(ticker: str | None = None) -> dict[str, int]:
    init_db()
    ph = _placeholder()
    query = """
        SELECT id, ticker, source_url, source_type, report_date, metrics_json, report_text
        FROM quarter_reports
        ORDER BY id DESC
    """
    params: tuple[Any, ...] = ()
    if ticker:
        query = """
            SELECT id, ticker, source_url, source_type, report_date, metrics_json, report_text
            FROM quarter_reports
            WHERE ticker = {ph}
            ORDER BY id DESC
        """.format(ph=ph)
        params = (ticker.upper(),)
    updated = 0
    skipped = 0
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        for report_id, row_ticker, source_url, source_type, report_date, metrics_json, report_text in rows:
            try:
                stored_metrics = json.loads(metrics_json)
                xbrl = stored_metrics.get("xbrl") or {}
                accession = stored_metrics.get("accession") or xbrl.get("accession")
                cik = xbrl.get("cik") or _cik_from_accession(accession) or _cik_from_ticker(row_ticker)
                if source_type == "sec_xbrl_import" and accession and cik:
                    companyfacts = _load_sec_companyfacts(cik)
                    if not companyfacts:
                        raise RuntimeError("SEC companyfacts unavailable.")
                    form_type = stored_metrics.get("form_type", "")
                    form = "10-K" if str(form_type).startswith("10-K") else "10-Q"
                    payload = _sec_payload_from_filing(
                        row_ticker,
                        cik,
                        companyfacts,
                        {
                            "accession": accession,
                            "form": form,
                            "report_date": report_date or stored_metrics.get("report_date"),
                            "primary_document": stored_metrics.get("filename") or "",
                        },
                    )
                    metrics = payload["metrics"]
                    report_text = payload["report_text"]
                    source_url = payload["source_url"]
                elif report_text:
                    metrics = extract_10q_data(row_ticker, report_text, source_url)
                else:
                    skipped += 1
                    continue
            except Exception:
                skipped += 1
                continue
            conn.execute(
                f"""
                UPDATE quarter_reports
                SET ticker = {ph}, fiscal_quarter = {ph}, report_date = {ph}, source_url = {ph}, company_name = {ph}, metrics_json = {ph}, report_text = {ph}
                WHERE id = {ph}
                """,
                (
                    metrics.get("ticker") or row_ticker,
                    metrics.get("fiscal_quarter"),
                    metrics.get("report_date"),
                    source_url,
                    metrics.get("company_name") or row_ticker,
                    json.dumps(metrics),
                    report_text,
                    report_id,
                ),
            )
            updated += 1
    return {"updated_reports": updated, "skipped_reports": skipped}


def extract_10q_data(ticker: str, report_text: str, filename: str | None = None) -> dict[str, Any]:
    text = _clean_pdf_text(report_text)
    search_text = _clean_text(report_text)
    extracted_ticker = _extract_ticker(search_text, filename, ticker)
    period = _extract_period(search_text)
    accession = _extract_accession(filename, search_text)
    statements = {
        "revenue": _extract_line_item(text, ["Total revenues", "Total revenue", "Revenue", "Net sales", "Net revenue", "Revenues"]),
        "gross_profit": _extract_line_item(text, ["Gross profit", "Gross margin"]),
        "operating_income": _extract_line_item(text, ["Income from operations", "Loss from operations", "Operating income", "Operating loss"]),
        "net_income": _extract_line_item(text, ["Net income", "Net loss", "Net earnings", "Net income (loss)", "Net loss attributable"]),
        "research_development": _extract_line_item(text, ["Research and development", "Research and development expense", "Research & development", "R&D"]),
        "cash": _extract_line_item(text, ["Cash and cash equivalents", "Cash, cash equivalents and restricted cash"]),
        "total_assets": _extract_line_item(text, ["Total assets"]),
        "total_liabilities": _extract_line_item(text, ["Total liabilities"]),
        "total_debt": _extract_line_item(text, ["Total debt", "Long-term debt", "Short-term debt", "Debt"]),
        "operating_cash_flow": _extract_line_item(text, [
            "Net cash provided by operating activities",
            "Net cash used in operating activities",
            "Net cash provided by (used in) operating activities",
            "Net cash provided by operating activities from continuing operations",
            "Cash provided by operating activities",
            "Cash used in operating activities",
            "Net cash from operating activities",
        ]),
    }
    calculated_ocf = _calculate_operating_cash_flow_from_10q(text)
    if _is_missing_value(statements.get("operating_cash_flow")) and calculated_ocf:
        statements["operating_cash_flow"] = calculated_ocf
    metrics_holder = {"statements": statements}
    metrics_holder, _ = enrich_missing_operating_cash_flow(metrics_holder, extracted_ticker, period["report_date"])
    statements = metrics_holder["statements"]
    xbrl_statements, xbrl_meta = _xbrl_statements(accession, extracted_ticker, period["report_date"])
    if xbrl_meta and xbrl_meta.get("accession"):
        accession = xbrl_meta["accession"]
    statements.update(xbrl_statements)
    statements = _merge_statement_fallbacks(statements, report_text)

    for item in statements.values():
        item["growth"] = _growth(item["current"], item["prior"])

    risk_terms = ["going concern", "material weakness", "impairment", "liquidity", "substantial doubt", "default", "restructuring"]
    risk_hits = [{"term": term, "count": len(re.findall(term, search_text, re.I))} for term in risk_terms]
    filing = {
        "filename": filename,
        "form_type": "10-Q" if re.search(r"form\s+10-q", search_text, re.I) else "PDF filing",
        "company_name": _extract_company_name(text, extracted_ticker),
        "ticker": extracted_ticker,
        "fiscal_quarter": period["fiscal_quarter"],
        "report_date": period["report_date"],
        "accession": accession,
        "xbrl": xbrl_meta,
        "statements": statements,
        "risk_terms": risk_hits,
        "text_stats": {
            "characters": len(text),
            "words": len(text.split()),
        },
    }
    return filing


def _text_statement_fallbacks(report_text: str) -> dict[str, dict[str, Any]]:
    text = _clean_pdf_text(report_text)
    return {
        "research_development": _extract_line_item(text, [
            "Research and development",
            "Research and development expense",
            "Research and product development",
            "Product development",
            "Technology and development",
            "Research & development",
            "R&D",
        ]),
        "total_debt": _extract_line_item(text, [
            "Total debt",
            "Total borrowings",
            "Long-term debt",
            "Short-term debt",
            "Current portion of debt",
            "Debt",
        ]),
    }


def _merge_statement_fallbacks(statements: dict[str, Any], report_text: str) -> dict[str, Any]:
    if not report_text:
        return statements
    updated = dict(statements)
    for key, item in _text_statement_fallbacks(report_text).items():
        if _is_missing_value(updated.get(key)) and not _is_missing_value(item):
            updated[key] = {
                **item,
                "confidence": "filing_text_fallback",
                "source_note": "Extracted from filing text because SEC companyfacts did not expose a matching XBRL concept.",
            }
    return updated


def _sec_get_text(url: str) -> str | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _load_sec_submissions(cik: str) -> dict[str, Any] | None:
    padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    text = _sec_get_text(url)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _recent_filing_rows(submissions: dict[str, Any]) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    rows = []
    for index, form in enumerate(forms):
        if form not in SEC_FORMS:
            continue
        accession = recent.get("accessionNumber", [None])[index]
        report_date = recent.get("reportDate", [None])[index]
        if not accession or not report_date:
            continue
        rows.append(
            {
                "accession": accession,
                "form": form,
                "filing_date": recent.get("filingDate", [None])[index],
                "report_date": report_date,
                "primary_document": recent.get("primaryDocument", [None])[index],
            }
        )
    return rows


def _select_sec_filings(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda item: item["report_date"], reverse=True)
    quarter_rows = [item for item in rows if item["form"] == "10-Q"]
    if mode == "last_quarter":
        return quarter_rows[:1]
    if mode == "last_8_quarters":
        return quarter_rows[:8]
    if mode == "last_12_quarters":
        return quarter_rows[:12]
    if mode == "all_available_quarters":
        return quarter_rows[:20]
    if mode == "this_year_quarters":
        latest_year = quarter_rows[0]["report_date"][:4] if quarter_rows else ""
        return [item for item in quarter_rows if item["report_date"].startswith(latest_year)][:4]
    if mode == "last_year_quarters":
        years = sorted({item["report_date"][:4] for item in quarter_rows}, reverse=True)
        target_year = years[1] if len(years) > 1 else (years[0] if years else "")
        return [item for item in quarter_rows if item["report_date"].startswith(target_year)][:4]
    if mode == "last_4_quarters_plus_10k":
        selected = quarter_rows[:4]
        latest_10k = next((item for item in rows if item["form"] == "10-K"), None)
        if latest_10k and all(item["accession"] != latest_10k["accession"] for item in selected):
            selected.append(latest_10k)
        return sorted(selected, key=lambda item: item["report_date"], reverse=True)
    return quarter_rows[:4]


def _filing_archive_text(cik: str, accession: str) -> str:
    compact_accession = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{compact_accession}/{accession}.txt"
    text = _sec_get_text(url) or ""
    return _clean_pdf_text(text)[:MAX_TEXT_CHARS]


def get_sec_filing_text(cik: str | None, accession: str | None) -> str:
    if not cik or not accession:
        return ""
    return _filing_archive_text(cik, accession)


def _sec_payload_from_filing(ticker: str, cik: str, companyfacts: dict[str, Any], filing: dict[str, Any]) -> dict[str, Any]:
    accession = filing["accession"]
    report_date = filing["report_date"]
    report_text = _filing_archive_text(cik, accession)
    statements = {}
    for key in XBRL_TAGS:
        item = _xbrl_item(companyfacts, accession, key, report_date)
        if item:
            statements[key] = item
    if filing["form"] == "10-K":
        statements = _derive_10k_q4_statements(companyfacts, statements)
    statements = _merge_statement_fallbacks(statements, report_text)
    for item in statements.values():
        item["growth"] = _growth(item["current"], item["prior"])

    search_text = _clean_text(report_text)
    risk_terms = ["going concern", "material weakness", "impairment", "liquidity", "substantial doubt", "default", "restructuring"]
    risk_hits = [{"term": term, "count": len(re.findall(term, search_text, re.I))} for term in risk_terms]
    company_name = companyfacts.get("entityName") or ticker.upper()
    source_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{filing.get('primary_document') or ''}"
    metrics = {
        "filename": filing.get("primary_document") or accession,
        "form_type": "10-K (Q4 derived)" if filing["form"] == "10-K" else filing["form"],
        "company_name": company_name,
        "ticker": ticker.upper(),
        "fiscal_quarter": report_date,
        "report_date": report_date,
        "accession": accession,
        "xbrl": {"accession": accession, "cik": cik, "available": bool(statements), "source": "sec_companyfacts"},
        "statements": statements,
        "risk_terms": risk_hits,
        "text_stats": {"characters": len(report_text), "words": len(report_text.split())},
    }
    return {
        "ticker": ticker.upper(),
        "fiscal_quarter": report_date,
        "report_date": report_date,
        "source_url": source_url,
        "source_type": "sec_xbrl_import",
        "company_name": company_name,
        "sector": None,
        "industry": None,
        "metrics": metrics,
        "report_text": report_text,
    }


def import_sec_filings(ticker: str, mode: str = "last_4_quarters") -> dict[str, Any]:
    ticker = ticker.upper().strip()
    cik = _cik_from_ticker(ticker)
    if not cik:
        raise RuntimeError(f"Could not find SEC CIK for ticker {ticker}.")
    companyfacts = _load_sec_companyfacts(cik)
    submissions = _load_sec_submissions(cik)
    if not companyfacts or not submissions:
        raise RuntimeError(f"Could not load SEC filings for ticker {ticker}.")
    filings = _select_sec_filings(_recent_filing_rows(submissions), mode)
    if not filings:
        raise RuntimeError(f"No SEC 10-Q/10-K filings found for ticker {ticker}.")
    saved = []
    for filing in reversed(filings):
        payload = _sec_payload_from_filing(ticker, cik, companyfacts, filing)
        saved.append(save_report(payload))
    return {
        "ticker": ticker,
        "cik": cik,
        "mode": mode,
        "imported": len(saved),
        "reports": saved,
    }


def build_pdf_payload(ticker: str, file_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
    report_text = extract_pdf_text(file_bytes)
    filing = extract_10q_data(ticker, report_text, filename)
    extracted_ticker = filing.get("ticker") or "UNKNOWN"
    return {
        "ticker": extracted_ticker,
        "fiscal_quarter": filing.get("fiscal_quarter"),
        "report_date": filing.get("report_date"),
        "source_url": filename,
        "source_type": "uploaded_10q_pdf",
        "company_name": filing.get("company_name") or extracted_ticker,
        "sector": None,
        "industry": None,
        "metrics": filing,
        "report_text": report_text,
    }


def save_report(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    ph = _placeholder()
    returning = " RETURNING id" if _using_postgres() else ""
    with _connect() as conn:
        existing = None
        if payload.get("fiscal_quarter"):
            existing = conn.execute(
                f"SELECT id FROM quarter_reports WHERE ticker = {ph} AND fiscal_quarter = {ph} ORDER BY id DESC LIMIT 1",
                (payload["ticker"], payload.get("fiscal_quarter")),
            ).fetchone()
        if not existing and payload.get("report_date"):
            existing = conn.execute(
                f"SELECT id FROM quarter_reports WHERE ticker = {ph} AND report_date = {ph} ORDER BY id DESC LIMIT 1",
                (payload["ticker"], payload.get("report_date")),
            ).fetchone()
        if not existing and payload.get("source_url"):
            existing = conn.execute(
                f"SELECT id FROM quarter_reports WHERE ticker = {ph} AND source_url = {ph} ORDER BY id DESC LIMIT 1",
                (payload["ticker"], payload.get("source_url")),
            ).fetchone()

        if existing:
            report_id = existing[0]
            conn.execute(
                f"""
                UPDATE quarter_reports
                SET fiscal_quarter = {ph},
                    report_date = {ph},
                    source_url = {ph},
                    source_type = {ph},
                    company_name = {ph},
                    sector = {ph},
                    industry = {ph},
                    metrics_json = {ph},
                    report_text = {ph},
                    created_at = {ph}
                WHERE id = {ph}
                """,
                (
                    payload.get("fiscal_quarter"),
                    payload.get("report_date"),
                    payload.get("source_url"),
                    payload["source_type"],
                    payload.get("company_name"),
                    payload.get("sector"),
                    payload.get("industry"),
                    json.dumps(payload["metrics"]),
                    payload.get("report_text"),
                    _now(),
                    report_id,
                ),
            )
            return {**payload, "id": report_id, "updated": True}

        cur = conn.execute(
            f"""
            INSERT INTO quarter_reports (
                ticker, fiscal_quarter, report_date, source_url, source_type, company_name,
                sector, industry, metrics_json, report_text, created_at
            ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}){returning}
            """,
            (
                payload["ticker"],
                payload.get("fiscal_quarter"),
                payload.get("report_date"),
                payload.get("source_url"),
                payload["source_type"],
                payload.get("company_name"),
                payload.get("sector"),
                payload.get("industry"),
                json.dumps(payload["metrics"]),
                payload.get("report_text"),
                _now(),
            ),
        )
        report_id = cur.fetchone()[0] if _using_postgres() else cur.lastrowid
    return {**payload, "id": report_id, "updated": False}


def list_reports(ticker: str) -> list[dict[str, Any]]:
    init_db()
    backfill_missing_operating_cash_flow(ticker)
    ph = _placeholder()
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            f"SELECT * FROM quarter_reports WHERE ticker = {ph} ORDER BY id DESC LIMIT 100",
            (ticker.upper(),),
        ).fetchall()
    reports = [{**_row_to_dict(row), "metrics": json.loads(row["metrics_json"])} for row in rows]
    return sorted(reports, key=_report_date_key, reverse=True)[:20]


def list_all_reports(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    backfill_missing_operating_cash_flow()
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            "SELECT * FROM quarter_reports ORDER BY id DESC LIMIT 200",
        ).fetchall()
    reports = [{**_row_to_dict(row), "metrics": json.loads(row["metrics_json"])} for row in rows]
    return sorted(reports, key=_report_date_key, reverse=True)[:limit]


def list_tickers() -> list[dict[str, Any]]:
    init_db()
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            """
            SELECT * FROM quarter_reports
            ORDER BY ticker ASC, id DESC
            """
        ).fetchall()

    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        data = _row_to_dict(row)
        try:
            data["metrics"] = json.loads(data.get("metrics_json") or "{}")
        except Exception:
            data["metrics"] = {}
        ticker = str(data.get("ticker") or "").upper()
        if ticker:
            by_ticker.setdefault(ticker, []).append(data)

    items = []
    for ticker, reports in by_ticker.items():
        sorted_reports = sorted(reports, key=_report_date_key, reverse=True)
        latest = sorted_reports[0]
        latest_group = _metrics_form_group(latest.get("metrics") or {})
        previous = next(
            (
                item for item in sorted_reports[1:]
                if _metrics_form_group(item.get("metrics") or {}) == latest_group
            ),
            None,
        )
        score = score_report(latest.get("metrics") or {}, previous.get("metrics") if previous else None)
        items.append(
            {
                "ticker": ticker,
                "filing_count": len(reports),
                "latest_id": latest.get("id"),
                "latest_created_at": latest.get("created_at"),
                "latest_period": latest.get("fiscal_quarter"),
                "company_name": latest.get("company_name"),
                "score": score,
                "score_total": score.get("total"),
                "score_label": score.get("label"),
                "score_suggestion": score.get("suggestion"),
            }
        )
    return sorted(items, key=lambda item: item.get("score_total") or -1, reverse=True)


def delete_all_reports() -> dict[str, int]:
    init_db()
    with _connect() as conn:
        analysis_count = conn.execute("SELECT COUNT(*) FROM quarter_analyses").fetchone()[0]
        report_count = conn.execute("SELECT COUNT(*) FROM quarter_reports").fetchone()[0]
        conn.execute("DELETE FROM quarter_analyses")
        conn.execute("DELETE FROM quarter_reports")
    return {"deleted_reports": report_count, "deleted_analyses": analysis_count}


def get_report(report_id: int) -> dict[str, Any] | None:
    init_db()
    ph = _placeholder()
    with _connect(row_factory=True) as conn:
        row = conn.execute(f"SELECT * FROM quarter_reports WHERE id = {ph}", (report_id,)).fetchone()
    if not row:
        return None
    data = _row_to_dict(row)
    data["metrics"] = json.loads(data.pop("metrics_json"))
    return data


def _report_date_key(report: dict[str, Any]) -> str:
    value = report.get("report_date") or report.get("fiscal_quarter") or report.get("created_at") or ""
    parsed = _parse_period_date(value)
    if parsed:
        return parsed.strftime("%Y-%m-%d")
    return str(value)


def _metrics_form_group(metrics: dict[str, Any]) -> str:
    form = str(metrics.get("form_type") or "")
    if form.startswith("10-Q") or form.startswith("10-K (Q4 derived)"):
        return "quarter"
    return form


def _statement_value(metrics: dict[str, Any], key: str) -> float | None:
    return metrics.get("statements", {}).get(key, {}).get("current")


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / abs(denominator)


def _quality_points(value: float | None, weight: int, strong: float, neutral: float, reverse: bool = False) -> tuple[float, str]:
    if value is None:
        return round(weight * 0.35, 1), "Needs review"
    if reverse:
        if value <= strong:
            return weight, "Strong"
        if value <= neutral:
            return round(weight * 0.65, 1), "Acceptable"
        return round(weight * 0.25, 1), "Weak"
    if value >= strong:
        return weight, "Strong"
    if value >= neutral:
        return round(weight * 0.65, 1), "Acceptable"
    return round(weight * 0.25, 1), "Weak"


def _business_quality_score(metrics: dict[str, Any], previous_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    statements = metrics.get("statements", {})
    revenue = _statement_value(metrics, "revenue")
    r_and_d = _statement_value(metrics, "research_development")
    cash = _statement_value(metrics, "cash")
    total_assets = _statement_value(metrics, "total_assets")
    total_liabilities = _statement_value(metrics, "total_liabilities")
    total_debt = _statement_value(metrics, "total_debt")
    operating_cash_flow = _statement_value(metrics, "operating_cash_flow")
    no_debt_reported = total_debt in (None, 0) and cash is not None and total_assets is not None

    revenue_growth = statements.get("revenue", {}).get("growth")
    r_and_d_growth = statements.get("research_development", {}).get("growth")
    if previous_metrics:
        revenue_growth = _growth(revenue, _statement_value(previous_metrics, "revenue"))
        r_and_d_growth = _growth(r_and_d, _statement_value(previous_metrics, "research_development"))

    r_and_d_intensity = _ratio(r_and_d, revenue)
    r_and_d_efficiency = None
    if revenue_growth is not None and r_and_d_growth is not None:
        r_and_d_efficiency = revenue_growth - r_and_d_growth
    debt_to_assets = 0.0 if no_debt_reported else _ratio(total_debt, total_assets)
    cash_to_debt = None if no_debt_reported else _ratio(cash, total_debt)
    ocf_to_debt = None if no_debt_reported else _ratio(operating_cash_flow, total_debt)
    liability_to_assets = _ratio(total_liabilities, total_assets)

    rows = []
    factors: list[tuple[str, Any, int, float, float, bool, str]] = [
        ("R&D intensity", r_and_d_intensity, 15, 0.10, 0.04, False, "R&D / revenue"),
        ("R&D efficiency spread", r_and_d_efficiency, 15, 0.00, -0.10, False, "Revenue growth minus R&D growth"),
        ("Debt to assets", debt_to_assets, 20, 0.10, 0.35, True, "Total debt / assets"),
        ("Liabilities to assets", liability_to_assets, 15, 0.45, 0.70, True, "Balance sheet leverage"),
    ]
    total = 0.0
    for factor, value, weight, strong, neutral, reverse, meaning in factors:
        points, verdict = _quality_points(value, weight, strong, neutral, reverse)
        total += points
        rows.append({"factor": factor, "value": value, "weight": weight, "points": points, "verdict": verdict, "meaning": meaning})
    if no_debt_reported:
        debt_rows = [
            ("Cash to debt", "No debt reported", 20, 20, "Strong", "Cash coverage not stressed because no debt fact is reported"),
            ("Operating cash flow to debt", "No debt reported", 15, 15, "Strong", "Debt service not stressed because no debt fact is reported"),
        ]
    else:
        debt_rows = [
            ("Cash to debt", cash_to_debt, 20, *_quality_points(cash_to_debt, 20, 1.50, 0.75, False), "Cash coverage of debt"),
            ("Operating cash flow to debt", ocf_to_debt, 15, *_quality_points(ocf_to_debt, 15, 0.25, 0.08, False), "OCF debt service capacity"),
        ]
    for factor, value, weight, points, verdict, meaning in debt_rows:
        total += points
        rows.append({"factor": factor, "value": value, "weight": weight, "points": points, "verdict": verdict, "meaning": meaning})

    if total >= 80:
        label = "Durable"
        suggestion = "QUALITY SUPPORT"
    elif total >= 65:
        label = "Healthy"
        suggestion = "WATCH"
    elif total >= 50:
        label = "Mixed"
        suggestion = "REVIEW"
    else:
        label = "Fragile"
        suggestion = "RISK"
    return {
        "total": round(total, 1),
        "max": 100,
        "label": label,
        "suggestion": suggestion,
        "basis": "R&D productivity, debt burden, liquidity, and operating cash coverage",
        "rows": rows,
    }


def _confidence_score(metrics: dict[str, Any], previous_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    statements = metrics.get("statements", {})
    required = ["revenue", "operating_income", "net_income", "operating_cash_flow", "cash", "total_assets", "total_liabilities"]
    present = [key for key in required if statements.get(key, {}).get("current") is not None]
    xbrl = [key for key in required if statements.get(key, {}).get("confidence") == "xbrl_sec_companyfacts"]
    comparable = [key for key in required if statements.get(key, {}).get("prior") is not None]
    previous_comparable = []
    if previous_metrics:
        previous_comparable = [
            key for key in required
            if _statement_value(metrics, key) is not None and _statement_value(previous_metrics, key) is not None
        ]
    completeness_points = (len(present) / len(required)) * 40
    source_points = (len(xbrl) / len(required)) * 35
    comparability_base = previous_comparable if previous_metrics else comparable
    comparability_points = (len(comparability_base) / len(required)) * 20
    identity_points = 5 if metrics.get("ticker") and (metrics.get("accession") or metrics.get("xbrl", {}).get("accession")) else 0
    total = round(completeness_points + source_points + comparability_points + identity_points, 1)
    if total >= 85:
        level = "High"
    elif total >= 70:
        level = "Medium"
    else:
        level = "Low"
    return {
        "score": total,
        "level": level,
        "method": "data completeness + SEC XBRL source quality + prior-period comparability",
        "coverage": {
            "required_metrics": len(required),
            "present_metrics": len(present),
            "xbrl_metrics": len(xbrl),
            "comparable_metrics": len(comparability_base),
        },
        "warnings": [] if total >= 70 else ["Low confidence: do not use rating without manual review."],
    }


def score_report(metrics: dict[str, Any], previous_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    statements = metrics.get("statements", {})
    def trend(key: str):
        if previous_metrics:
            return _growth(_statement_value(metrics, key), _statement_value(previous_metrics, key))
        return statements.get(key, {}).get("growth")

    rows = [
        ("Revenue Trend", trend("revenue"), 25, 0.08, 0.00),
        ("Gross Profit Trend", trend("gross_profit"), 15, 0.06, 0.00),
        ("Operating Income Trend", trend("operating_income"), 20, 0.06, 0.00),
        ("Net Income Trend", trend("net_income"), 20, 0.06, 0.00),
        ("Operating Cash Flow Trend", trend("operating_cash_flow"), 10, 0.05, 0.00),
    ]
    risk_count = sum(item.get("count", 0) for item in metrics.get("risk_terms", []))
    risk_points = 10 if risk_count == 0 else 6 if risk_count < 5 else 2
    scored = []
    total = risk_points
    for label, value, weight, strong, neutral in rows:
        if value is None:
            points = round(weight * 0.35, 1)
            verdict = "Needs review"
        elif value >= strong:
            points = weight
            verdict = "Strong"
        elif value >= neutral:
            points = round(weight * 0.65, 1)
            verdict = "Stable"
        else:
            points = round(weight * 0.25, 1)
            verdict = "Weak"
        total += points
        scored.append({"factor": label, "value": value, "weight": weight, "points": points, "verdict": verdict})
    scored.append({"factor": "Risk Language", "value": risk_count, "weight": 10, "points": risk_points, "verdict": "Clean" if risk_count == 0 else "Review"})
    confidence = _confidence_score(metrics, previous_metrics)
    quality_score = _business_quality_score(metrics, previous_metrics)
    missing_trends = sum(1 for _, value, *_ in rows if value is None)
    cap = 97.0
    if previous_metrics is None:
        cap = min(cap, 88.0)
    if missing_trends:
        cap = min(cap, max(58.0, 90.0 - (missing_trends * 7.0)))
    if confidence["score"] < 90:
        cap = min(cap, 92.0)
    if quality_score["total"] < 80:
        cap = min(cap, 89.0)
    total = min(total, cap)
    if confidence["score"] < 70:
        label = "Needs Review"
        suggestion = "HOLD"
    elif total >= 85 and risk_count < 5 and confidence["score"] >= 80:
        label = "Excellent"
        suggestion = "STRONG BUY"
    elif total >= 70:
        label = "Good"
        suggestion = "BUY"
    elif total >= 50:
        label = "Mixed"
        suggestion = "HOLD"
    else:
        label = "Weak"
        suggestion = "SELL"
    if risk_count >= 10 and suggestion in {"STRONG BUY", "BUY"}:
        suggestion = "HOLD"
    legend = [
        {"range": "80-100", "label": "Excellent", "suggestion": "STRONG BUY", "meaning": "Strong extracted trends and limited tracked risk language."},
        {"range": "65-79", "label": "Good", "suggestion": "BUY", "meaning": "Positive filing trend, but still needs valuation and sector review."},
        {"range": "50-64", "label": "Mixed", "suggestion": "HOLD", "meaning": "Balanced or incomplete filing signals; watch next quarter."},
        {"range": "0-49", "label": "Weak", "suggestion": "SELL", "meaning": "Weak extracted trends or elevated filing risk language."},
    ]
    return {
        "total": round(total, 1),
        "max": 100,
        "label": label,
        "suggestion": suggestion,
        "basis": "stored-quarter comparison" if previous_metrics else "filing internal comparison",
        "quality_score": quality_score,
        "confidence": confidence,
        "legend": legend,
        "rows": scored,
    }
