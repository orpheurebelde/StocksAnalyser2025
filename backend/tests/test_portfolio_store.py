import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import auth, portfolio_store


class PortfolioStoreTests(unittest.TestCase):
    def test_portfolio_limit_and_ticker_crud_are_user_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "portfolio.sqlite")
            with (
                patch.object(auth, "AUTH_DB_PATH", db_path),
                patch.object(auth, "POSTGRES_URL", None),
                patch.object(auth, "_initialized_db_key", None),
            ):
                user_one = auth.upsert_google_user({
                    "sub": "portfolio-user-1",
                    "email": "portfolio1@example.com",
                    "email_verified": True,
                    "name": "Portfolio One",
                })
                user_two = auth.upsert_google_user({
                    "sub": "portfolio-user-2",
                    "email": "portfolio2@example.com",
                    "email_verified": True,
                    "name": "Portfolio Two",
                })

                first = portfolio_store.create_portfolio(user_one["id"], "Core")
                updated = portfolio_store.add_ticker(user_one["id"], first["id"], "aapl", 12.5, "2024-06-10")
                portfolio_store.add_ticker(user_one["id"], first["id"], "AAPL")

                self.assertEqual(updated["tickers"], ["AAPL"])
                self.assertEqual(updated["holdings"][0]["quantity"], 12.5)
                self.assertEqual(updated["holdings"][0]["acquisition_date"], "2024-06-10")
                self.assertIsNone(portfolio_store.get_portfolio(user_two["id"], first["id"]))

                edited = portfolio_store.update_holding(user_one["id"], first["id"], "AAPL", 20, "2025-01-15")
                self.assertEqual(edited["holdings"][0]["quantity"], 20)
                self.assertEqual(edited["holdings"][0]["acquisition_date"], "2025-01-15")

                for index in range(2, 6):
                    portfolio_store.create_portfolio(user_one["id"], f"Portfolio {index}")
                with self.assertRaisesRegex(ValueError, "Maximum 5"):
                    portfolio_store.create_portfolio(user_one["id"], "Portfolio 6")

                renamed = portfolio_store.rename_portfolio(user_one["id"], first["id"], "Long Term")
                self.assertEqual(renamed["name"], "Long Term")
                without_ticker = portfolio_store.remove_ticker(user_one["id"], first["id"], "AAPL")
                self.assertEqual(without_ticker["tickers"], [])
                self.assertTrue(portfolio_store.delete_portfolio(user_one["id"], first["id"]))
                self.assertIsNone(portfolio_store.get_portfolio(user_one["id"], first["id"]))


if __name__ == "__main__":
    unittest.main()
