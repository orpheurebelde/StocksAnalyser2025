import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import quarter_earnings
from core.quarter_earnings import (
    _business_quality_score,
    _derive_balance_sheet_totals,
    _derive_gross_profit,
    _score_v2,
    calculate_filing_fair_value,
    enrich_derived_metrics,
    find_yoy_previous_report,
)


def statement(current, prior, start="2025-01-01", end="2025-03-31"):
    return {
        "current": current,
        "prior": prior,
        "xbrl_start": start,
        "xbrl_end": end,
        "accession": "test-accession",
        "taxonomy": "us-gaap",
    }


class DeriveGrossProfitTests(unittest.TestCase):
    def test_derives_gross_profit_from_matching_revenue_and_cost(self):
        statements = {
            "revenue": statement(100.0, 90.0),
            "cost_of_revenue": statement(60.0, 55.0),
        }

        result = _derive_gross_profit(statements)

        self.assertEqual(result["gross_profit"]["current"], 40.0)
        self.assertEqual(result["gross_profit"]["prior"], 35.0)
        self.assertAlmostEqual(result["gross_profit"]["growth"], 5.0 / 35.0)
        self.assertEqual(result["gross_profit"]["confidence"], "xbrl_sec_companyfacts_derived")

    def test_keeps_reported_gross_profit(self):
        reported = statement(42.0, 39.0)
        statements = {
            "revenue": statement(100.0, 90.0),
            "cost_of_revenue": statement(60.0, 55.0),
            "gross_profit": reported,
        }

        result = _derive_gross_profit(statements)

        self.assertIs(result, statements)
        self.assertIs(result["gross_profit"], reported)

    def test_rejects_mismatched_periods(self):
        statements = {
            "revenue": statement(100.0, 90.0),
            "cost_of_revenue": statement(60.0, 55.0, start="2025-01-01", end="2025-06-30"),
        }

        result = _derive_gross_profit(statements)

        self.assertNotIn("gross_profit", result)


class DeriveBalanceSheetTests(unittest.TestCase):
    def test_derives_acn_shaped_liabilities_and_total_debt(self):
        statements = {
            "current_liabilities": statement(21_609_107_000, 20_352_097_000, start=None, end="2026-05-31"),
            "noncurrent_liabilities": statement(13_689_741_000, 12_801_833_000, start=None, end="2026-05-31"),
            "current_debt": statement(112_816_000, 114_484_000, start=None, end="2026-05-31"),
            "total_debt": statement(5_029_449_000, 5_034_169_000, start=None, end="2026-05-31"),
        }

        result = _derive_balance_sheet_totals(statements)

        self.assertEqual(result["total_liabilities"]["current"], 35_298_848_000)
        self.assertEqual(result["total_debt"]["current"], 5_142_265_000)
        self.assertEqual(result["total_debt"]["confidence"], "xbrl_sec_companyfacts_derived")

    def test_labels_undisclosed_research_spend_without_inventing_value(self):
        score = _business_quality_score({
            "statements": {
                "revenue": {"current": 100, "growth": 0.05},
                "cash": {"current": 20},
                "total_assets": {"current": 100},
                "total_liabilities": {"current": 50},
                "total_debt": {"current": 10},
                "operating_cash_flow": {"current": 15},
            }
        })

        research_rows = [row for row in score["rows"] if row["factor"].startswith("R&D")]
        self.assertTrue(all(row["value"] == "Not separately disclosed" for row in research_rows))
        self.assertTrue(all(row["verdict"] == "Not disclosed" for row in research_rows))

    def test_missing_debt_is_not_treated_as_zero_debt(self):
        score = _business_quality_score({
            "statements": {
                "revenue": {"current": 100},
                "cash": {"current": 20},
                "total_assets": {"current": 100},
                "total_liabilities": {"current": 50},
                "operating_cash_flow": {"current": 15},
            }
        })

        debt_rows = [row for row in score["rows"] if row["factor"] in {"Debt to assets", "Cash to debt", "Operating cash flow to debt"}]
        self.assertTrue(all(row["value"] is None for row in debt_rows))
        self.assertTrue(all(row["verdict"] == "Needs review" for row in debt_rows))

    def test_requires_both_source_values(self):
        statements = {"revenue": statement(100.0, 90.0)}

        result = _derive_gross_profit(statements)

        self.assertNotIn("gross_profit", result)


class FilingFairValueTests(unittest.TestCase):
    def test_blends_annualized_filing_earnings_and_cash_flow(self):
        report = {"metrics": {"statements": {
            "net_income": statement(100.0, 80.0),
            "operating_cash_flow": statement(200.0, 150.0),
            "cash": {"current": 50.0},
            "total_debt": {"current": 10.0},
        }}}
        result = calculate_filing_fair_value(
            report,
            {"sharesOutstanding": 100.0, "currentPrice": 70.0},
            {"total": 50.0},
        )

        self.assertTrue(result["available"])
        self.assertEqual(len(result["methods"]), 2)
        self.assertEqual(result["methods"][0]["multiple"], 16.0)
        self.assertGreater(result["fair_value_per_share"], 70.0)
        self.assertEqual(result["confidence"], "medium")

    def test_requires_positive_valuation_base(self):
        report = {"metrics": {"statements": {"net_income": {"current": -1.0}}}}
        result = calculate_filing_fair_value(report, {"sharesOutstanding": 100.0}, {"total": 50.0})
        self.assertFalse(result["available"])

    def test_estimates_shares_from_market_cap_when_yahoo_shares_missing(self):
        report = {"metrics": {"statements": {
            "net_income": statement(100.0, 80.0),
            "operating_cash_flow": statement(200.0, 150.0),
        }}}
        result = calculate_filing_fair_value(
            report,
            {"marketCap": 1000.0, "currentPrice": 10.0},
            {"total": 50.0},
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["shares_outstanding"], 100.0)
        self.assertEqual(result["shares_source"], "yahoo_market_cap_price_estimate")
        self.assertEqual(result["confidence"], "low")

    def test_estimates_shares_from_filing_text_when_yahoo_market_data_is_thin(self):
        report = {
            "report_text": "Weighted average common shares outstanding - diluted 100,000,000",
            "metrics": {"statements": {
                "net_income": statement(100.0, 80.0),
            }},
        }
        result = calculate_filing_fair_value(report, {"currentPrice": 10.0}, {"total": 50.0})

        self.assertTrue(result["available"])
        self.assertEqual(result["shares_outstanding"], 100_000_000.0)
        self.assertEqual(result["shares_source"], "filing_text_weighted_average_shares")

class DeleteTickerReportsTests(unittest.TestCase):
    def test_deletes_only_selected_ticker_and_its_analyses(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "quarter-earnings.sqlite")
            with patch.object(quarter_earnings, "DB_PATH", db_path), patch.object(quarter_earnings, "POSTGRES_URL", None):
                quarter_earnings.init_db()
                with quarter_earnings._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO quarter_reports
                        (user_id, ticker, fiscal_quarter, source_type, metrics_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?)
                        """,
                        (1, "AAA", "2025-Q1", "test", "{}", "now", 1, "BBB", "2025-Q1", "test", "{}", "now", 2, "AAA", "2025-Q1", "test", "{}", "now"),
                    )
                    aaa_id = conn.execute("SELECT id FROM quarter_reports WHERE ticker = ?", ("AAA",)).fetchone()[0]
                    conn.execute(
                        """
                        INSERT INTO quarter_analyses
                        (report_id, provider, model, score_json, analysis_markdown, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (aaa_id, "test", "test", "{}", "test", "now"),
                    )

                result = quarter_earnings.delete_ticker_reports(1, "aaa")

                self.assertEqual(result["deleted_reports"], 1)
                self.assertEqual(result["deleted_analyses"], 1)
                with quarter_earnings._connect() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM quarter_reports WHERE user_id = 1 AND ticker = 'AAA'").fetchone()[0], 0)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM quarter_reports WHERE ticker = 'BBB'").fetchone()[0], 1)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM quarter_reports WHERE user_id = 2 AND ticker = 'AAA'").fetchone()[0], 1)

                self.assertEqual(len(quarter_earnings.list_reports(1, "AAA")), 0)
                self.assertEqual(len(quarter_earnings.list_reports(2, "AAA")), 1)


class DerivedAnalyticsV2Tests(unittest.TestCase):
    def test_derives_period_matched_margins_and_fcf(self):
        def item(current, prior, start="2025-01-01", end="2025-03-31"):
            return {"current": current, "prior": prior, "xbrl_start": start, "xbrl_end": end}

        metrics = {
            "statements": {
                "revenue": item(100, 90), "gross_profit": item(60, 50),
                "operating_income": item(25, 20), "net_income": item(20, 15),
                "operating_cash_flow": item(30, 24), "capital_expenditures": item(5, 4),
            },
            "risk_terms": [], "text_stats": {"words": 10000},
        }

        result = enrich_derived_metrics(metrics)["derived_metrics"]

        self.assertEqual(result["version"], "2.1")
        self.assertAlmostEqual(result["metrics"]["net_margin"]["current"], 0.20)
        self.assertEqual(result["metrics"]["free_cash_flow"]["current"], 25)
        self.assertAlmostEqual(result["metrics"]["fcf_margin"]["current"], 0.25)

    def test_does_not_mix_periods_for_fcf_margin(self):
        metrics = {"statements": {
            "revenue": {"current": 100, "xbrl_start": "2025-04-01", "xbrl_end": "2025-06-30"},
            "operating_cash_flow": {"current": 60, "xbrl_start": "2025-01-01", "xbrl_end": "2025-06-30"},
            "capital_expenditures": {"current": 10, "xbrl_start": "2025-01-01", "xbrl_end": "2025-06-30"},
        }}

        result = enrich_derived_metrics(metrics)["derived_metrics"]["metrics"]

        self.assertEqual(result["free_cash_flow"]["current"], 50)
        self.assertIsNone(result["fcf_margin"]["current"])

    def test_uses_matching_ytd_facts_for_cash_conversion_and_sbc(self):
        metrics = {"statements": {
            "revenue_ytd": statement(300, 260, start="2025-01-01", end="2025-09-30"),
            "net_income_ytd": statement(60, 50, start="2025-01-01", end="2025-09-30"),
            "operating_cash_flow": statement(75, 65, start="2025-01-01", end="2025-09-30"),
            "share_based_compensation_ytd": statement(12, 10, start="2025-01-01", end="2025-09-30"),
        }}

        result = enrich_derived_metrics(metrics)["derived_metrics"]["metrics"]

        self.assertAlmostEqual(result["cash_conversion"]["current"], 1.25)
        self.assertAlmostEqual(result["sbc_to_revenue"]["current"], 0.04)

    def test_score_v2_excludes_missing_facts(self):
        score = _score_v2({"statements": {"revenue": {"current": 100}}})

        self.assertLess(score["coverage"], 40)
        self.assertEqual(score["label"], "Insufficient evidence")
        self.assertTrue(any(not row["available"] for row in score["rows"]))

    def test_yoy_selector_uses_prior_year_not_previous_quarter(self):
        current = {"ticker": "AMD", "report_date": "2025-06-30", "metrics": {"form_type": "10-Q"}}
        previous_quarter = {"ticker": "AMD", "report_date": "2025-03-31", "metrics": {"form_type": "10-Q"}}
        prior_year = {"ticker": "AMD", "report_date": "2024-06-29", "metrics": {"form_type": "10-Q"}}

        result = find_yoy_previous_report(current, [previous_quarter, prior_year])

        self.assertIs(result, prior_year)


class SecAnalyticsBackfillTests(unittest.TestCase):
    def test_merges_missing_sec_facts_and_preserves_existing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "quarter-earnings.sqlite")
            stored = {
                "accession": "0000000001-25-000001",
                "form_type": "10-Q",
                "sec_enrichment_version": "2.0",
                "xbrl": {"cik": "1"},
                "statements": {"revenue": statement(100, 90)},
            }
            with (
                patch.object(quarter_earnings, "DB_PATH", db_path),
                patch.object(quarter_earnings, "POSTGRES_URL", None),
                patch.object(quarter_earnings, "_load_sec_companyfacts", return_value={"facts": {}}),
                patch.object(
                    quarter_earnings,
                    "_xbrl_item",
                    side_effect=lambda _facts, _accession, key, _date: statement(300, 260, "2025-01-01", "2025-09-30")
                    if key in {"revenue_ytd", "net_income_ytd", "operating_cash_flow", "share_based_compensation_ytd"}
                    else None,
                ),
            ):
                quarter_earnings.init_db()
                with quarter_earnings._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO quarter_reports
                        (user_id, ticker, report_date, source_type, metrics_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (1, "AAA", "2025-09-30", "sec_xbrl_import", json.dumps(stored), "now"),
                    )

                changed = quarter_earnings.backfill_sec_analytics(1, "aaa")

                self.assertEqual(changed, 1)
                with quarter_earnings._connect() as conn:
                    updated = json.loads(conn.execute("SELECT metrics_json FROM quarter_reports").fetchone()[0])
                self.assertEqual(updated["statements"]["revenue"]["current"], 100)
                self.assertEqual(updated["statements"]["revenue_ytd"]["current"], 300)
                self.assertEqual(updated["sec_enrichment_version"], "2.1")
                self.assertEqual(quarter_earnings.backfill_sec_analytics(1, "AAA"), 0)


if __name__ == "__main__":
    unittest.main()
