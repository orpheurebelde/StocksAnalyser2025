import io
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from core.yfinance_client import get_statement

DB_ENV_NAME = "QUARTER_EARNINGS_DB_PATH"
POSTGRES_ENV_NAMES = ("DATABASE_URL", "POSTGRES_URL")
POSTGRES_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
DB_PATH = os.getenv(DB_ENV_NAME) or os.path.join(os.path.dirname(os.path.dirname(__file__)), "quarter_earnings.sqlite")
MAX_TEXT_CHARS = 90000
FINANCIAL_NUMBER_RE = re.compile(r"\(?-?\$?\s*\d[\d,]*(?:\.\d+)?\)?")

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
        SELECT id, ticker, source_url, report_text
        FROM quarter_reports
        WHERE report_text IS NOT NULL AND report_text != ''
        ORDER BY id DESC
    """
    params: tuple[Any, ...] = ()
    if ticker:
        query = """
            SELECT id, ticker, source_url, report_text
            FROM quarter_reports
            WHERE ticker = {ph} AND report_text IS NOT NULL AND report_text != ''
            ORDER BY id DESC
        """.format(ph=ph)
        params = (ticker.upper(),)
    updated = 0
    skipped = 0
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        for report_id, row_ticker, source_url, report_text in rows:
            try:
                metrics = extract_10q_data(row_ticker, report_text, source_url)
            except Exception:
                skipped += 1
                continue
            conn.execute(
                f"""
                UPDATE quarter_reports
                SET ticker = {ph}, fiscal_quarter = {ph}, report_date = {ph}, company_name = {ph}, metrics_json = {ph}
                WHERE id = {ph}
                """,
                (
                    metrics.get("ticker") or row_ticker,
                    metrics.get("fiscal_quarter"),
                    metrics.get("report_date"),
                    metrics.get("company_name") or row_ticker,
                    json.dumps(metrics),
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
    statements = {
        "revenue": _extract_line_item(text, ["Total revenues", "Total revenue", "Revenue", "Net sales", "Net revenue", "Revenues"]),
        "gross_profit": _extract_line_item(text, ["Gross profit", "Gross margin"]),
        "operating_income": _extract_line_item(text, ["Income from operations", "Loss from operations", "Operating income", "Operating loss"]),
        "net_income": _extract_line_item(text, ["Net income", "Net loss", "Net earnings", "Net income (loss)", "Net loss attributable"]),
        "cash": _extract_line_item(text, ["Cash and cash equivalents", "Cash, cash equivalents and restricted cash"]),
        "total_assets": _extract_line_item(text, ["Total assets"]),
        "total_liabilities": _extract_line_item(text, ["Total liabilities"]),
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
        "statements": statements,
        "risk_terms": risk_hits,
        "text_stats": {
            "characters": len(text),
            "words": len(text.split()),
        },
    }
    return filing


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
            f"SELECT * FROM quarter_reports WHERE ticker = {ph} ORDER BY id DESC LIMIT 20",
            (ticker.upper(),),
        ).fetchall()
    return [{**_row_to_dict(row), "metrics": json.loads(row["metrics_json"])} for row in rows]


def list_all_reports(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    backfill_missing_operating_cash_flow()
    ph = _placeholder()
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            f"SELECT * FROM quarter_reports ORDER BY id DESC LIMIT {ph}",
            (limit,),
        ).fetchall()
    return [{**_row_to_dict(row), "metrics": json.loads(row["metrics_json"])} for row in rows]


def list_tickers() -> list[dict[str, Any]]:
    init_db()
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            """
            SELECT ticker, COUNT(*) AS filing_count, MAX(id) AS latest_id, MAX(created_at) AS latest_created_at
            FROM quarter_reports
            GROUP BY ticker
            ORDER BY latest_id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


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


def _statement_value(metrics: dict[str, Any], key: str) -> float | None:
    return metrics.get("statements", {}).get(key, {}).get("current")


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
    if total >= 80 and risk_count < 5:
        label = "Excellent"
        suggestion = "STRONG BUY"
    elif total >= 65:
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
        "legend": legend,
        "rows": scored,
    }
