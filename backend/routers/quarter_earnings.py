import json
import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.quarter_earnings import build_pdf_payload, get_report, list_reports, save_report, score_report

load_dotenv()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class AnalyzeRequest(BaseModel):
    provider: str = "mistral"
    model: str | None = None


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
Interpret the uploaded 10-Q PDF using only supplied filing text and extracted filing metrics.

Required final structure:
1. Executive summary.
2. Filing identity: company, period, form type, extraction limits.
3. Financial statement interpretation: revenue, profit, operating income, net income, cash, assets, liabilities, operating cash flow.
4. Risk and disclosure interpretation: material weakness, liquidity, impairment, going concern, restructuring, default, legal exposure.
5. Score table in Markdown with Factor, Evidence from 10-Q, Score, Risk, Analyst view.
6. Quarter-to-quarter comparison using prior stored filings when available.
7. Management discussion and future guidance if present in the filing text.
8. Mistral/Groq analyst guidance: bullish case, bearish case, watchlist, conclusion.

Company: {report.get("company_name")} ({report.get("ticker")})
Quarter: {report.get("fiscal_quarter")}
Source: uploaded 10-Q PDF {report.get("source_url") or ""}

Deterministic score:
{json.dumps(score, indent=2)}

Extracted filing data:
{json.dumps(report.get("metrics"), indent=2)}

Prior stored 10-Q filings for comparison:
{json.dumps(prior_context, indent=2)}

10-Q filing text:
{(report.get("report_text") or "No full web report text supplied.")[:25000]}
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
        saved["score"] = score_report(saved["metrics"])
        saved["history"] = [{**item, "score": score_report(item["metrics"])} for item in list_reports(ticker)]
        return saved
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{ticker}/reports")
@limiter.limit("20/minute")
def reports(request: Request, ticker: str):
    items = list_reports(ticker)
    return {
        "ticker": ticker.upper(),
        "reports": [{**item, "score": score_report(item["metrics"])} for item in items],
    }


@router.post("/{report_id}/analyze")
@limiter.limit("4/minute")
def analyze_report(request: Request, report_id: int, body: AnalyzeRequest):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Quarter report not found.")

    score = score_report(report["metrics"])
    prior_reports = list_reports(report["ticker"])
    prompt = build_prompt(report, score, prior_reports)
    try:
        provider = body.provider.lower()
        if provider == "groq":
            analysis, model = call_groq(prompt, body.model)
        elif provider == "mistral":
            analysis, model = call_mistral(prompt, body.model)
        else:
            raise HTTPException(status_code=400, detail="Provider must be mistral or groq.")
        return {"report": report, "score": score, "analysis": analysis, "provider": provider, "model": model, "prompt": prompt}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
