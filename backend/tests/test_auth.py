import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import auth


class AuthPersistenceTests(unittest.TestCase):
    def test_reads_postgres_returning_id_from_dict_row(self):
        self.assertEqual(auth._first_value({"id": 42}), 42)

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
                auth.record_login_device(user["id"], "device-identifier-12345", "127.0.0.1", "test-agent")
                auth.check_login_risk(user["email"], "device-identifier-12345", "127.0.0.1")
                with self.assertRaises(PermissionError):
                    auth.check_login_risk("other@example.com", "device-identifier-12345", "127.0.0.1")

                authenticated, session_id = auth.authenticate_session(token)

                self.assertEqual(authenticated["email"], "person@example.com")
                self.assertEqual(session_id, session["id"])
                self.assertNotIn("google_sub", auth.public_user(authenticated))
                self.assertFalse(auth.public_user(authenticated)["is_admin"])
                self.assertFalse(auth.public_user(authenticated)["analysis_authorized"])

                for _ in range(5):
                    auth.ensure_analysis_quota(authenticated)
                    auth.record_analysis_use(user["id"], "stock")
                with self.assertRaises(PermissionError):
                    auth.ensure_analysis_quota(authenticated)
                quota_request = auth.request_quota_access(user["id"])
                self.assertEqual(quota_request["request"]["status"], "pending")
                request_id = quota_request["request"]["id"]
                auth.decide_quota_request(request_id, user["id"], True)
                auth.ensure_analysis_quota(authenticated)

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

    def test_registration_limit_blocks_new_google_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "auth.sqlite")
            with (
                patch.object(auth, "AUTH_DB_PATH", db_path),
                patch.object(auth, "POSTGRES_URL", None),
                patch.object(auth, "MAX_REGISTERED_USERS", 1),
                patch.object(auth, "_initialized_db_key", None),
            ):
                auth.upsert_google_user({"sub": "first", "email": "first@example.com", "email_verified": True})
                with self.assertRaises(PermissionError):
                    auth.upsert_google_user({"sub": "second", "email": "second@example.com", "email_verified": True})
                self.assertEqual(auth.registration_status()["remaining"], 0)
                access_request = auth.create_registration_access_request(
                    {"sub": "second", "email": "second@example.com", "email_verified": True, "name": "Second User"},
                    "second-device-identifier",
                    "127.0.0.2",
                    "Please grant access.",
                )
                self.assertEqual(access_request["email"], "second@example.com")
                stored = auth.list_registration_access_requests()
                self.assertEqual(stored[0]["request_message"], "Please grant access.")


if __name__ == "__main__":
    unittest.main()
