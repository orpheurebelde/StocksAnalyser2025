import io
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "quarter_earnings.sqlite")
MAX_TEXT_CHARS = 90000


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _safe_number(raw: str | None) -> float | None:
    if not raw:
        return None
    value = raw.replace(",", "").replace("$", "").strip()
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
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
            pages.append(page.extract_text() or "")
            if sum(len(text) for text in pages) >= MAX_TEXT_CHARS:
                break
        text = _clean_text("\n".join(pages))
    except Exception as exc:
        raise RuntimeError("Could not read PDF text. Upload a selectable 10-Q PDF, not a scanned image PDF.") from exc
    if not text:
        raise RuntimeError("PDF loaded, but no selectable text was found. Scanned 10-Q PDFs need OCR first.")
    return text[:MAX_TEXT_CHARS]


def _extract_company_name(text: str, ticker: str) -> str:
    match = re.search(r"Exact name of registrant as specified in its charter\)?\s*([A-Z0-9][A-Z0-9 .,&'/-]{3,120})", text, re.I)
    if match:
        return match.group(1).strip(" .")
    match = re.search(r"FORM 10-Q\s+([A-Z0-9][A-Z0-9 .,&'/-]{3,120})", text, re.I)
    return match.group(1).strip(" .") if match else ticker.upper()


def _extract_period(text: str) -> dict[str, str | None]:
    period_match = re.search(r"quarterly period ended\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    report_match = re.search(r"Commission File Number.*?(\d{4})", text, re.I)
    return {
        "fiscal_quarter": period_match.group(1) if period_match else None,
        "report_date": period_match.group(1) if period_match else report_match.group(1) if report_match else None,
    }


def _extract_line_item(text: str, labels: list[str]) -> dict[str, Any]:
    for label in labels:
        pattern = rf"{label}\s+\$?\(?([\d,]+(?:\.\d+)?)\)?\s+\$?\(?([\d,]+(?:\.\d+)?)\)?"
        match = re.search(pattern, text, re.I)
        if match:
            return {
                "label": label,
                "current": _safe_number(match.group(1)),
                "prior": _safe_number(match.group(2)),
                "confidence": "medium",
            }
    return {"label": labels[0], "current": None, "prior": None, "confidence": "missing"}


def _growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return (current - prior) / abs(prior)


def extract_10q_data(ticker: str, report_text: str, filename: str | None = None) -> dict[str, Any]:
    text = _clean_text(report_text)
    period = _extract_period(text)
    statements = {
        "revenue": _extract_line_item(text, ["Total revenues", "Total revenue", "Net sales", "Revenues"]),
        "gross_profit": _extract_line_item(text, ["Gross profit", "Gross margin"]),
        "operating_income": _extract_line_item(text, ["Operating income", "Income from operations"]),
        "net_income": _extract_line_item(text, ["Net income", "Net earnings"]),
        "cash": _extract_line_item(text, ["Cash and cash equivalents", "Cash, cash equivalents and restricted cash"]),
        "total_assets": _extract_line_item(text, ["Total assets"]),
        "total_liabilities": _extract_line_item(text, ["Total liabilities"]),
        "operating_cash_flow": _extract_line_item(text, ["Net cash provided by operating activities", "Net cash used in operating activities"]),
    }

    for item in statements.values():
        item["growth"] = _growth(item["current"], item["prior"])

    risk_terms = ["going concern", "material weakness", "impairment", "liquidity", "substantial doubt", "default", "restructuring"]
    risk_hits = [{"term": term, "count": len(re.findall(term, text, re.I))} for term in risk_terms]
    filing = {
        "filename": filename,
        "form_type": "10-Q" if re.search(r"form\s+10-q", text, re.I) else "PDF filing",
        "company_name": _extract_company_name(text, ticker),
        "ticker": ticker.upper(),
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
    return {
        "ticker": ticker.upper().strip(),
        "fiscal_quarter": filing.get("fiscal_quarter"),
        "report_date": filing.get("report_date"),
        "source_url": filename,
        "source_type": "uploaded_10q_pdf",
        "company_name": filing.get("company_name") or ticker.upper().strip(),
        "sector": None,
        "industry": None,
        "metrics": filing,
        "report_text": report_text,
    }


def save_report(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO quarter_reports (
                ticker, fiscal_quarter, report_date, source_url, source_type, company_name,
                sector, industry, metrics_json, report_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        report_id = cur.lastrowid
    return {**payload, "id": report_id}


def list_reports(ticker: str) -> list[dict[str, Any]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM quarter_reports WHERE ticker = ? ORDER BY id DESC LIMIT 20",
            (ticker.upper(),),
        ).fetchall()
    return [{**dict(row), "metrics": json.loads(row["metrics_json"])} for row in rows]


def get_report(report_id: int) -> dict[str, Any] | None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM quarter_reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["metrics"] = json.loads(data.pop("metrics_json"))
    return data


def score_report(metrics: dict[str, Any]) -> dict[str, Any]:
    statements = metrics.get("statements", {})
    rows = [
        ("Revenue Trend", statements.get("revenue", {}).get("growth"), 25, 0.08, 0.00),
        ("Gross Profit Trend", statements.get("gross_profit", {}).get("growth"), 15, 0.06, 0.00),
        ("Operating Income Trend", statements.get("operating_income", {}).get("growth"), 20, 0.06, 0.00),
        ("Net Income Trend", statements.get("net_income", {}).get("growth"), 20, 0.06, 0.00),
        ("Operating Cash Flow Trend", statements.get("operating_cash_flow", {}).get("growth"), 10, 0.05, 0.00),
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
    label = "Excellent" if total >= 80 else "Good" if total >= 65 else "Mixed" if total >= 50 else "Weak"
    return {"total": round(total, 1), "max": 100, "label": label, "rows": scored}
