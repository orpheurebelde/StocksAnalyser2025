import json
import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.quarter_earnings import fetch_quarter_payload, get_report, list_reports, save_report, score_report

load_dotenv()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class IngestRequest(BaseModel):
    source_url: str | None = None
    manual_text: str | None = None


class AnalyzeRequest(BaseModel):
    provider: str = "mistral"
    model: str | None = None


def build_prompt(report: dict, score: dict) -> str:
    return f"""
You are the Quarter Earnings Analyst agent for StocksAnalyser2025.
Evaluate the complete quarterly report and financial evolution using only supplied data.

Required final structure:
1. Executive summary.
2. Quarter report interpretation: revenue, margins, earnings, cash flow, balance sheet.
3. Management/future guidance: quote or paraphrase report text when available, otherwise state data limitation.
4. Score table in Markdown with Factor, Evidence, Score, Risk, Analyst view.
5. Sector comparison at report date: compare company performance to sector norms qualitatively using sector and industry context.
6. Investment guidance: bullish case, bearish case, watchlist, conclusion.

Company: {report.get("company_name")} ({report.get("ticker")})
Quarter: {report.get("fiscal_quarter")}
Sector: {report.get("sector")}
Industry: {report.get("industry")}
Source: {report.get("source_type")} {report.get("source_url") or ""}

Deterministic score:
{json.dumps(score, indent=2)}

Quarter metrics:
{json.dumps(report.get("metrics"), indent=2)}

Report text:
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


@router.post("/{ticker}/ingest")
@limiter.limit("6/minute")
def ingest_quarter_report(request: Request, ticker: str, body: IngestRequest):
    try:
        payload = fetch_quarter_payload(ticker, body.source_url, body.manual_text)
        saved = save_report(payload)
        saved["score"] = score_report(saved["metrics"])
        saved["history"] = list_reports(ticker)
        return saved
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{ticker}/reports")
@limiter.limit("20/minute")
def reports(request: Request, ticker: str):
    return {"ticker": ticker.upper(), "reports": list_reports(ticker)}


@router.post("/{report_id}/analyze")
@limiter.limit("4/minute")
def analyze_report(request: Request, report_id: int, body: AnalyzeRequest):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Quarter report not found.")

    score = score_report(report["metrics"])
    prompt = build_prompt(report, score)
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
