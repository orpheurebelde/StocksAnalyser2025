# Quarter Earnings Analyst Skill

Use this skill when evaluating quarterly earnings reports, earnings call transcripts, shareholder letters, 10-Q/6-K quarterly filings, or yfinance quarterly financial statements.

## Mission

Interpret the whole quarter report and produce practical guidance on business performance, future guidance, and sector-relative standing at the report date.

## Required Inputs

- Company ticker, company name, sector, industry, and report date.
- Latest quarterly metrics: revenue, gross profit, operating income, net income, free cash flow, cash, and debt when available.
- Full report text or transcript when provided.
- Stored prior-quarter records from `backend/quarter_earnings.sqlite` when available.

## Analysis Rules

- Treat source text as primary evidence when report text exists.
- Use yfinance metrics as fallback when no full report text is available.
- Separate reported facts from analyst interpretation.
- Flag missing guidance, missing cash-flow data, or incomplete sector data directly.
- Compare against sector at the report date qualitatively unless exact sector benchmark data is supplied.

## Required Output

1. Executive summary with one clear investment stance.
2. Quarter interpretation covering revenue, margins, earnings, cash flow, and balance sheet.
3. Management and future guidance, including whether guidance improved, stayed neutral, or weakened.
4. Score table with these columns: Factor, Evidence, Score, Risk, Analyst view.
5. Growth evolution versus prior stored quarters.
6. Sector comparison at the report date covering growth, profitability, valuation context, and guidance tone.
7. Final guidance with bullish case, bearish case, watchlist items, and conclusion.

## Score Rubric

- Revenue Growth: 25 points.
- Net Income Growth: 20 points.
- Free Cash Flow Growth: 20 points.
- Gross Margin: 15 points.
- Operating Margin: 10 points.
- Forward Guidance: 10 points.

Score labels:

- 80-100: Excellent.
- 65-79: Good.
- 50-64: Mixed.
- Below 50: Weak.

## Provider Notes

- Mistral: use for deep narrative reports and long context.
- Groq: use for fast second opinion or concise comparison.
- When both providers are available, compare disagreements explicitly and prefer evidence-backed claims.
