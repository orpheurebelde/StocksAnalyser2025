import unittest

from core.comparison_score import score_company


class ComparisonScoreTests(unittest.TestCase):
    def test_stronger_company_scores_higher(self):
        strong = {
            "trailingPE": 14, "forwardPE": 12, "priceToBook": 3, "priceToSalesTrailing12Months": 3,
            "returnOnEquity": 0.28, "returnOnAssets": 0.14, "grossMargins": 0.65,
            "operatingMargins": 0.30, "profitMargins": 0.25, "freeCashflowMargin": 0.25,
            "totalRevenue": 100, "currentRatio": 1.8, "totalCash": 15, "totalDebt": 10,
        }
        weak = {
            "trailingPE": 38, "forwardPE": 32, "priceToBook": 9, "priceToSalesTrailing12Months": 10,
            "returnOnEquity": 0.03, "returnOnAssets": 0.01, "grossMargins": 0.25,
            "operatingMargins": 0.02, "profitMargins": 0.01, "freeCashflowMargin": 0,
            "totalRevenue": 100, "currentRatio": 0.8, "totalCash": 2, "totalDebt": 10,
        }

        self.assertGreater(score_company(strong)[0], score_company(weak)[0])
        self.assertEqual(score_company(strong)[1], 100.0)

    def test_missing_fields_reduce_coverage_not_score_as_zero(self):
        score, coverage = score_company({"returnOnEquity": 0.30})

        self.assertEqual(score, 100.0)
        self.assertEqual(coverage, 10.0)


if __name__ == "__main__":
    unittest.main()
