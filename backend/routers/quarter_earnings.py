import json
import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.quarter_earnings import (
    build_pdf_payload,
    delete_all_reports,
    get_db_status,
    get_report,
    import_sec_filings,
    list_all_reports,
    list_reports,
    list_tickers,
    reprocess_stored_reports,
    save_report,
    score_report,
)

load_dotenv()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def attach_evolution_scores(items: list[dict]) -> list[dict]:
    scored = []
    for index, item in enumerate(items):
        previous = next((candidate for candidate in items[index + 1:] if candidate.get("ticker") == item.get("ticker")), None)
        scored.append({**item, "score": score_report(item["metrics"], previous["metrics"] if previous else None)})
    return scored


class AnalyzeRequest(BaseModel):
    provider: str = "unified"
    model: str | None = None


class SecImportRequest(BaseModel):
    ticker: str
    mode: str = "last_4_quarters"


def build_prompt(report: dict, score: dict, prior_reports: list[dict] | None = None) -> str:
    prior_context = [
        {
            "id": item.get("id"),
            "period": item.get("fiscal_quarter"),
            "company": item.get("company_name"),
            "metrics": item.get("metrics", {}),
        }
        for item in (prior_reports or [])[:4]
        if item.get("id") != report.get("id")
    ]
    return f"""
You are the 10-Q Filing Analyst agent for StocksAnalyser2025.
Interpret the SEC filing using only supplied filing text and extracted filing metrics.

Required final structure:
1. Executive summary.
2. Filing identity: company, period, form type, extraction limits.
3. Financial statement interpretation: revenue, profit, operating income, net income, cash, assets, liabilities, operating cash flow.
4. Risk and disclosure interpretation: material weakness, liquidity, impairment, going concern, restructuring, default, legal exposure.
5. Deterministic score and confidence: explain total score, confidence.score, confidence.level, coverage, and limits.
6. Score table in Markdown with Factor, Evidence from 10-Q, Score, Risk, Analyst view.
7. Quarter-to-quarter comparison using prior stored filings when available.
8. Management discussion and future guidance if present in the filing text.
9. Analyst guidance: bullish case, bearish case, watchlist, conclusion.

Rating guardrail:
- Treat deterministic score and confidence as source of truth.
- If confidence.level is Low, final action must be HOLD / REVIEW, never BUY or SELL.
- If confidence.score is below 70, state that manual review is required before any trade action.

Company: {report.get("company_name")} ({report.get("ticker")})
Quarter: {report.get("fiscal_quarter")}
Source: SEC/PDF filing {report.get("source_url") or ""}

Deterministic score:
{json.dumps(score, indent=2)}

Extracted filing data:
{json.dumps(report.get("metrics"), indent=2)}

Prior stored 10-Q filings for comparison:
{json.dumps(prior_context, indent=2)}

10-Q filing text:
{(report.get("report_text") or "No full web report text supplied.")[:25000]}
""".strip()


def build_groq_score_prompt(report: dict, score: dict, prior_reports: list[dict] | None = None) -> str:
    prior_context = [
        {
            "id": item.get("id"),
            "period": item.get("fiscal_quarter"),
            "score": score_report(item.get("metrics", {})),
            "statements": item.get("metrics", {}).get("statements", {}),
            "risk_terms": item.get("metrics", {}).get("risk_terms", []),
        }
        for item in (prior_reports or [])[:4]
        if item.get("id") != report.get("id")
    ]
    compact = {
        "company": report.get("company_name"),
        "ticker": report.get("ticker"),
        "quarter": report.get("fiscal_quarter"),
        "score": score,
        "statements": report.get("metrics", {}).get("statements", {}),
        "risk_terms": report.get("metrics", {}).get("risk_terms", []),
        "prior_filings": prior_context,
    }
    return f"""
You are validating a 10-Q score, not reading the full filing.
Use only this compact extracted dataset.

Return:
1. Score validation summary.
2. Any score rows that look inconsistent with extracted values.
3. Quarter-to-quarter comparison highlights.
4. Final rating: VALID, REVIEW, or REJECT.

Data:
{json.dumps(compact, indent=2)}
""".strip()


def build_unified_optimization_prompt(report: dict, score: dict, prior_reports: list[dict] | None, mistral_analysis: str) -> str:
    compact = {
        "company": report.get("company_name"),
        "ticker": report.get("ticker"),
        "quarter": report.get("fiscal_quarter"),
        "score": score,
        "statements": report.get("metrics", {}).get("statements", {}),
        "prior_filings": [
            {
                "id": item.get("id"),
                "period": item.get("fiscal_quarter"),
                "statements": item.get("metrics", {}).get("statements", {}),
            }
            for item in (prior_reports or [])[:4]
            if item.get("id") != report.get("id")
        ],
    }
    return f"""
You are the final optimizer for a quarter earnings AI analysis.
Use the SEC/XBRL dataset as the source of truth. Review the Mistral draft, correct weak reasoning, remove unsupported claims, and return one unified analyst report.

Return Markdown only:
1. Unified rating: STRONG BUY, BUY, HOLD, SELL, or STRONG SELL.
2. Confidence score: 0-100, level, and whether data is good enough for action.
3. Executive summary.
4. Financial trend analysis.
5. Quarter-to-quarter comparison.
6. Bull case.
7. Bear case.
8. Watchlist.
9. Final conclusion.

Strict guardrail:
- SEC/XBRL data and deterministic score override Mistral draft.
- Never upgrade to BUY/STRONG BUY when confidence.score < 70.
- Never issue a high-conviction rating without naming the specific metrics that support it.

SEC/XBRL dataset:
{json.dumps(compact, indent=2)}

Mistral draft:
{mistral_analysis}
""".strip()


def call_mistral(prompt: str, model: str | None):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY not configured on server.")
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model or "mistral-small-latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.35,
            "max_tokens": 8000,
        },
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip(), model or "mistral-small-latest"


def call_groq(prompt: str, model: str | None):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured on server.")
    selected = model or "llama-3.3-70b-versatile"
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": selected,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.35,
            "max_tokens": 8000,
        },
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip(), selected


@router.post("/{ticker}/ingest-pdf")
@limiter.limit("6/minute")
async def ingest_quarter_pdf(
    request: Request,
    ticker: str,
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF 10-Q file.")
    try:
        pdf_bytes = await file.read()
        payload = build_pdf_payload(ticker, pdf_bytes, file.filename)
        saved = save_report(payload)
        history = attach_evolution_scores(list_reports(saved["ticker"]))
        saved_from_history = next((item for item in history if item["id"] == saved["id"]), None)
        saved["score"] = saved_from_history["score"] if saved_from_history else score_report(saved["metrics"])
        saved["history"] = history
        return saved
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest-pdf")
@limiter.limit("6/minute")
async def ingest_quarter_pdf_auto(request: Request, file: UploadFile = File(...)):
    return await ingest_quarter_pdf(request, "AUTO", file)


@router.get("/reports")
@limiter.limit("20/minute")
def all_reports(request: Request):
    items = list_all_reports()
    return {
        "reports": attach_evolution_scores(items),
    }


@router.delete("/reports")
@limiter.limit("4/minute")
def clear_reports(request: Request):
    return delete_all_reports()


@router.get("/db-status")
@limiter.limit("20/minute")
def db_status(request: Request):
    return get_db_status()


@router.post("/reports/reprocess")
@limiter.limit("2/minute")
def reprocess_reports(request: Request, ticker: str | None = None):
    return reprocess_stored_reports(ticker)


@router.post("/sec/import")
@limiter.limit("4/minute")
def import_from_sec(request: Request, body: SecImportRequest):
    allowed_modes = {"last_quarter", "last_4_quarters", "this_year_quarters", "last_year_quarters", "last_4_quarters_plus_10k"}
    if body.mode not in allowed_modes:
        raise HTTPException(status_code=400, detail="Invalid SEC import mode.")
    try:
        result = import_sec_filings(body.ticker, body.mode)
        history = attach_evolution_scores(list_reports(result["ticker"]))
        latest = history[0] if history else None
        return {
            **result,
            "history": history,
            "latest": latest,
            "score": latest.get("score") if latest else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tickers")
@limiter.limit("20/minute")
def tickers(request: Request):
    return {"tickers": list_tickers()}


@router.get("/{ticker}/reports")
@limiter.limit("20/minute")
def reports(request: Request, ticker: str):
    items = list_reports(ticker)
    return {
        "ticker": ticker.upper(),
        "reports": attach_evolution_scores(items),
    }


@router.post("/{report_id}/analyze")
@limiter.limit("4/minute")
def analyze_report(request: Request, report_id: int, body: AnalyzeRequest):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Quarter report not found.")

    prior_reports = list_reports(report["ticker"])
    current_index = next((index for index, item in enumerate(prior_reports) if item["id"] == report["id"]), -1)
    previous = prior_reports[current_index + 1] if current_index >= 0 and current_index + 1 < len(prior_reports) else None
    score = score_report(report["metrics"], previous["metrics"] if previous else None)
    try:
        mistral_prompt = build_prompt(report, score, prior_reports)
        mistral_analysis, mistral_model = call_mistral(mistral_prompt, body.model)
        groq_prompt = build_unified_optimization_prompt(report, score, prior_reports, mistral_analysis)
        unified_analysis, groq_model = call_groq(groq_prompt, None)
        return {
            "report": report,
            "score": score,
            "analysis": unified_analysis,
            "provider": "mistral+groq",
            "model": {"mistral": mistral_model, "groq": groq_model},
            "prompt": {"mistral": mistral_prompt, "groq": groq_prompt},
            "mistral_draft": mistral_analysis,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
