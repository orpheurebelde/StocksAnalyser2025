import unittest
from unittest.mock import patch

from core import fmp_client, market_data_client


class MarketDataFacadeTests(unittest.TestCase):
    def test_fmp_maps_profile_estimates_and_targets(self):
        replies = {
            "profile": [{"companyName": "Apple", "description": "Maker", "fullTimeEmployees": 100, "price": 200}],
            "analyst-estimates": [{"estimatedEpsAvg": 10, "numberAnalystsEstimatedEps": 20}],
            "price-target-consensus": [{"targetConsensus": 220, "targetLow": 180, "targetHigh": 250}],
        }
        with patch.object(fmp_client, "_get", side_effect=lambda endpoint, *_args: replies[endpoint]):
            result = fmp_client.get_fmp_info_fields("AAPL")
        self.assertEqual(result["longBusinessSummary"], "Maker")
        self.assertEqual(result["forwardEps"], 10)
        self.assertEqual(result["forwardPE"], 20)
        self.assertEqual(result["targetMeanPrice"], 220)

    def test_facade_uses_sec_totals_and_fmp_forward_fields(self):
        with patch.object(market_data_client, "_finnhub_info", return_value={"currentPrice": 100, "totalRevenue": 1}), patch.object(market_data_client, "get_sec_info_fields", return_value={"totalRevenue": 2}), patch.object(market_data_client, "get_fmp_info_fields", return_value={"currentPrice": 99, "forwardEps": 5}):
            result = market_data_client.get_ticker_info("AAPL")
        self.assertEqual(result["currentPrice"], 100)
        self.assertEqual(result["totalRevenue"], 2)
        self.assertEqual(result["forwardEps"], 5)


if __name__ == "__main__":
    unittest.main()
