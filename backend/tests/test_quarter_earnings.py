import unittest

from core.quarter_earnings import _derive_gross_profit


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


if __name__ == "__main__":
    unittest.main()
