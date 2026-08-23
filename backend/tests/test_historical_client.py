import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import historical_client


class HistoricalAdapterTests(unittest.TestCase):
    def test_twelve_keeps_ohlcv_contract(self):
        payload = {"values": [{"datetime": "2026-01-02", "open": "10", "high": "12", "low": "9", "close": "11", "volume": "100"}]}
        with patch.dict(os.environ, {"TWELVE_DATA_API_KEY": "key"}), patch.object(historical_client, "_request", return_value=payload):
            result = historical_client.download_data("AAPL", "5d", "1d")
        self.assertEqual(list(result.columns), ["Open", "High", "Low", "Close", "Volume"])
        self.assertEqual(float(result["Close"].iloc[0]), 11.0)

    def test_fred_maps_index_close_to_compatible_frame(self):
        payload = {"observations": [{"date": "2026-01-02", "value": "6000.5"}]}
        with patch.dict(os.environ, {"FRED_API_KEY": "key"}), patch.object(historical_client, "_request", return_value=payload):
            result = historical_client.download_data("^GSPC", "5d", "1d")
        self.assertEqual(float(result["Close"].iloc[0]), 6000.5)
        self.assertEqual(float(result["Open"].iloc[0]), 6000.5)


if __name__ == "__main__":
    unittest.main()
