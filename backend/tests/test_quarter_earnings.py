import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import quarter_earnings
from core.quarter_earnings import _derive_gross_profit, calculate_filing_fair_value


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


if __name__ == "__main__":
    unittest.main()
