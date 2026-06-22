import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import auth


class AuthPersistenceTests(unittest.TestCase):
    def test_user_session_login_and_activity_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "auth.sqlite")
            with (
                patch.object(auth, "AUTH_DB_PATH", db_path),
                patch.object(auth, "POSTGRES_URL", None),
                patch.object(auth, "_initialized_db_key", None),
            ):
                auth.init_auth_db()
                user = auth.upsert_google_user(
                    {
                        "sub": "google-user-1",
                        "email": "person@example.com",
                        "email_verified": True,
                        "name": "Test Person",
                        "picture": "https://example.com/avatar.png",
                        "locale": "en",
                    }
                )
                token, session = auth.create_session(user["id"], "127.0.0.1", "test-agent")

                authenticated, session_id = auth.authenticate_session(token)

                self.assertEqual(authenticated["email"], "person@example.com")
                self.assertEqual(session_id, session["id"])
                self.assertNotIn("google_sub", auth.public_user(authenticated))
                self.assertFalse(auth.public_user(authenticated)["is_admin"])

                auth.log_login_event(
                    "login_success",
                    True,
                    "127.0.0.1",
                    "test-agent",
                    user_id=user["id"],
                    email=user["email"],
                )
                auth.log_user_activity(
                    user["id"],
                    session_id,
                    "GET",
                    "/api/test",
                    200,
                    "127.0.0.1",
                    "test-agent",
                    {"duration_ms": 12.5},
                )
                with auth._connect() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM app_users").fetchone()[0], 1)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM login_events").fetchone()[0], 1)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM user_activity").fetchone()[0], 1)

                auth.revoke_session(token)
                self.assertEqual(auth.authenticate_session(token), (None, None))

    def test_configured_email_becomes_admin(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "auth.sqlite")
            with (
                patch.object(auth, "AUTH_DB_PATH", db_path),
                patch.object(auth, "POSTGRES_URL", None),
                patch.object(auth, "ADMIN_EMAILS", {"almeida1976marco@gmail.com"}),
                patch.object(auth, "_initialized_db_key", None),
            ):
                user = auth.upsert_google_user(
                    {
                        "sub": "admin-google-user",
                        "email": "almeida1976marco@gmail.com",
                        "email_verified": True,
                    }
                )

                self.assertTrue(user["is_admin"])
                self.assertTrue(auth.public_user(user)["is_admin"])


if __name__ == "__main__":
    unittest.main()
