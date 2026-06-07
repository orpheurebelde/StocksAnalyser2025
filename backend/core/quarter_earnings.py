import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import requests

from core.yfinance_client import get_ticker, get_ticker_info

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "quarter_earnings.sqlite")


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self):
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


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


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _series_to_records(series, limit=8):
    if series is None or getattr(series, "empty", True):
        return []
    records = []
    for idx, value in series.head(limit).items():
        records.append({"period": str(idx.date() if hasattr(idx, "date") else idx), "value": _safe_float(value)})
    return records


def fetch_report_url(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; StocksAnalyser2025/1.0; +https://github.com/orpheurebelde/StocksAnalyser2025)",
                "Accept": "text/html,application/xhtml+xml,application/xml,text/plain;q=0.9,*/*;q=0.8",
            },
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            "Could not read that report URL from the backend. "
            "The site may block automated requests, require login, or be unavailable. "
            "Paste the report text into Manual report text and try again."
        ) from exc
    content_type = response.headers.get("content-type", "")
    if "html" in content_type:
        parser = TextExtractor()
        parser.feed(response.text)
        return parser.text()[:60000]
    return response.text[:60000]


def fetch_quarter_payload(ticker: str, source_url: str | None = None, manual_text: str | None = None) -> dict[str, Any]:
    symbol = ticker.upper().strip()
    stock = get_ticker(symbol)
    info = get_ticker_info(symbol) or {}

    quarterly_financials = getattr(stock, "quarterly_financials", None)
    quarterly_cashflow = getattr(stock, "quarterly_cashflow", None)
    quarterly_balance = getattr(stock, "quarterly_balance", None)

    metrics = {
        "revenue": _series_to_records(quarterly_financials.loc["Total Revenue"] if quarterly_financials is not None and "Total Revenue" in quarterly_financials.index else None),
        "gross_profit": _series_to_records(quarterly_financials.loc["Gross Profit"] if quarterly_financials is not None and "Gross Profit" in quarterly_financials.index else None),
        "operating_income": _series_to_records(quarterly_financials.loc["Operating Income"] if quarterly_financials is not None and "Operating Income" in quarterly_financials.index else None),
        "net_income": _series_to_records(quarterly_financials.loc["Net Income"] if quarterly_financials is not None and "Net Income" in quarterly_financials.index else None),
        "free_cash_flow": _series_to_records(quarterly_cashflow.loc["Free Cash Flow"] if quarterly_cashflow is not None and "Free Cash Flow" in quarterly_cashflow.index else None),
        "cash": _series_to_records(quarterly_balance.loc["Cash And Cash Equivalents"] if quarterly_balance is not None and "Cash And Cash Equivalents" in quarterly_balance.index else None),
        "total_debt": _series_to_records(quarterly_balance.loc["Total Debt"] if quarterly_balance is not None and "Total Debt" in quarterly_balance.index else None),
        "yfinance_snapshot": {
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "forward_eps": info.get("forwardEps"),
            "trailing_eps": info.get("trailingEps"),
            "market_cap": info.get("marketCap"),
        },
    }

    latest_period = next((items[0]["period"] for items in metrics.values() if isinstance(items, list) and items), None)
    clean_manual_text = (manual_text or "").strip()
    report_text = clean_manual_text[:60000] if clean_manual_text else fetch_report_url(source_url) if source_url else ""
    source_type = "manual_report_text" if clean_manual_text else "web_report" if source_url else "yfinance_quarterly_financials"
    return {
        "ticker": symbol,
        "fiscal_quarter": latest_period,
        "report_date": latest_period,
        "source_url": source_url,
        "source_type": source_type,
        "company_name": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "metrics": metrics,
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
            "SELECT * FROM quarter_reports WHERE ticker = ? ORDER BY report_date DESC, id DESC LIMIT 20",
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
    def growth(metric):
        records = metrics.get(metric, [])
        if len(records) < 2 or not records[0].get("value") or not records[1].get("value"):
            return None
        prior = records[1]["value"]
        if prior == 0:
            return None
        return (records[0]["value"] - prior) / abs(prior)

    revenue_growth = growth("revenue")
    net_income_growth = growth("net_income")
    fcf_growth = growth("free_cash_flow")
    snapshot = metrics.get("yfinance_snapshot", {})

    rows = [
        ("Revenue Growth", revenue_growth, 25, 0.08, 0.00),
        ("Net Income Growth", net_income_growth, 20, 0.08, 0.00),
        ("Free Cash Flow Growth", fcf_growth, 20, 0.05, -0.05),
        ("Gross Margin", snapshot.get("gross_margins"), 15, 0.40, 0.25),
        ("Operating Margin", snapshot.get("operating_margins"), 10, 0.20, 0.10),
        ("Forward Guidance Proxy", snapshot.get("earnings_growth") or snapshot.get("revenue_growth"), 10, 0.08, 0.00),
    ]
    scored = []
    total = 0
    for label, value, weight, strong, neutral in rows:
        if value is None:
            points = round(weight * 0.35, 1)
            verdict = "Missing data"
        elif value >= strong:
            points = weight
            verdict = "Strong"
        elif value >= neutral:
            points = round(weight * 0.65, 1)
            verdict = "Mixed"
        else:
            points = round(weight * 0.25, 1)
            verdict = "Weak"
        total += points
        scored.append({"factor": label, "value": value, "weight": weight, "points": points, "verdict": verdict})

    if total >= 80:
        label = "Excellent"
    elif total >= 65:
        label = "Good"
    elif total >= 50:
        label = "Mixed"
    else:
        label = "Weak"
    return {"total": round(total, 1), "max": 100, "label": label, "rows": scored}
