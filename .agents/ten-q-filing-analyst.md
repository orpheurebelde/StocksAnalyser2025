# 10-Q Filing Analyst Skill

Use this skill only for uploaded 10-Q PDF filings. Do not scrape websites, fetch report URLs, or rely on pasted manual text.

## Mission

Read a full 10-Q filing, extract the main financial and disclosure data into the database, and produce a useful investor-facing interpretation.

## Required Inputs

- Uploaded selectable-text 10-Q PDF.
- Ticker supplied by user.
- Extracted filing text from PDF.
- Extracted filing JSON stored in `quarter_reports.metrics_json`.

## Data To Extract

- Filing identity: form type, company name, ticker, fiscal quarter, report date, source filename.
- Income statement: revenue, gross profit, operating income, net income.
- Cash flow: operating cash flow.
- Balance sheet: cash, total assets, total liabilities.
- Risk language counts: going concern, material weakness, impairment, liquidity, substantial doubt, default, restructuring.
- Text stats: character and word counts.

## Interpretation Rules

- Filing text is primary source.
- Separate extracted facts from analyst interpretation.
- Flag missing or low-confidence extractions.
- Never invent unavailable statement numbers.
- Treat repeated risk language as a review signal, not automatic bearish proof.
- State when table-column ambiguity may affect current/prior-period comparison.

## Required Output

1. Executive summary.
2. Filing identity and extraction limits.
3. Statement interpretation: revenue, profit, operating income, net income, cash, assets, liabilities, operating cash flow.
4. Risk and disclosure analysis.
5. Markdown score table with Factor, Evidence from 10-Q, Score, Risk, Analyst view.
6. Management discussion and future guidance if present.
7. Bullish case, bearish case, watchlist, conclusion.

## Score Rubric

- Revenue Trend: 25 points.
- Gross Profit Trend: 15 points.
- Operating Income Trend: 20 points.
- Net Income Trend: 20 points.
- Operating Cash Flow Trend: 10 points.
- Risk Language: 10 points.

Score labels:

- 80-100: Excellent.
- 65-79: Good.
- 50-64: Mixed.
- Below 50: Weak.

## Provider Notes

- Mistral: preferred for full filing narrative and nuanced risk sections.
- Groq: preferred for fast second opinion and concise comparison.
- When both are used, compare disagreement and prefer direct 10-Q evidence.
