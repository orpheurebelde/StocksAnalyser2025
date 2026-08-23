import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from core import finnhub_client


class FinnhubAdapterTests(unittest.TestCase):
    def test_info_maps_finnhub_values_to_existing_keys(self):
        replies = {
            "quote": {"c": 200, "pc": 198, "h": 202, "l": 197, "o": 199},
            "stock/profile2": {"name": "Apple", "currency": "USD", "marketCapitalization": 3000, "shareOutstanding": 15},
            "stock/metric": {"metric": {"peTTM": 25, "grossMarginTTM": 40, "roeTTM": 30}},
            "stock/recommendation": [{"strongBuy": 2, "buy": 2, "hold": 1, "sell": 0, "strongSell": 0}],
        }

        def fake_get(endpoint, *_args, **_kwargs):
            return replies[endpoint]

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(finnhub_client, "CACHE_DIR", Path(temp_dir)), patch.object(finnhub_client, "_get", side_effect=fake_get):
            result = finnhub_client.get_ticker_info("aapl")
        self.assertEqual(result["currentPrice"], 200)
        self.assertEqual(result["trailingPE"], 25)
        self.assertEqual(result["marketCap"], 3_000_000_000)
        self.assertEqual(result["sharesOutstanding"], 15_000_000)
        self.assertAlmostEqual(result["grossMargins"], 0.4)
        self.assertAlmostEqual(result["returnOnEquity"], 0.3)

    def test_deployed_environment_variable_spelling_is_supported(self):
        with patch.dict(os.environ, {"FINHUB_API_KEY": "deployed-key"}, clear=True):
            self.assertEqual(finnhub_client._api_key(), "deployed-key")



if __name__ == "__main__":
    unittest.main()
