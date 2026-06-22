import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

AUTH_DB_PATH = os.getenv("AUTH_DB_PATH") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "auth.sqlite")
POSTGRES_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
SESSION_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "stocks_session")
SESSION_DAYS = max(1, int(os.getenv("AUTH_SESSION_DAYS", "7")))
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax").lower()
COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN") or None
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "almeida1976marco@gmail.com").split(",")
    if email.strip()
}
_initialized_db_key: str | None = None

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


class _ClosingSQLiteConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _using_postgres() -> bool:
    return bool(POSTGRES_URL)


def _placeholder() -> str:
    return "%s" if _using_postgres() else "?"


def _connect(row_factory: bool = False):
    if _using_postgres():
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set, but psycopg is not installed.")
        return psycopg.connect(POSTGRES_URL, row_factory=dict_row if row_factory else None)
    directory = os.path.dirname(AUTH_DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH, factory=_ClosingSQLiteConnection)
    conn.execute("PRAGMA foreign_keys = ON")
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _row_dict(row: Any) -> dict[str, Any]:
    return row if isinstance(row, dict) else dict(row)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def init_auth_db() -> None:
    global _initialized_db_key
    db_key = POSTGRES_URL or os.path.abspath(AUTH_DB_PATH)
    if _initialized_db_key == db_key:
        return
    if _using_postgres():
        statements = [
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id BIGSERIAL PRIMARY KEY,
                google_sub TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                email_verified BOOLEAN NOT NULL DEFAULT FALSE,
                name TEXT,
                picture_url TEXT,
                locale TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                revoked_at TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS login_events (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
                event_type TEXT NOT NULL,
                email TEXT,
                success BOOLEAN NOT NULL,
                failure_reason TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_activity (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                session_id BIGINT REFERENCES auth_sessions(id) ON DELETE SET NULL,
                activity_type TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_login_events_user_created ON login_events(user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_user_activity_user_created ON user_activity(user_id, created_at)",
        ]
    else:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                email_verified INTEGER NOT NULL DEFAULT 0,
                name TEXT,
                picture_url TEXT,
                locale TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                revoked_at TEXT,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS login_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                email TEXT,
                success INTEGER NOT NULL,
                failure_reason TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id INTEGER,
                activity_type TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE,
                FOREIGN KEY(session_id) REFERENCES auth_sessions(id) ON DELETE SET NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash)",
            "CREATE INDEX IF NOT EXISTS idx_login_events_user_created ON login_events(user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_user_activity_user_created ON user_activity(user_id, created_at)",
        ]
    with _connect() as conn:
        for statement in statements:
            conn.execute(statement)
        if _using_postgres():
            conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE")
        else:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(app_users)").fetchall()}
            if "is_admin" not in columns:
                conn.execute("ALTER TABLE app_users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        ph = _placeholder()
        for admin_email in ADMIN_EMAILS:
            conn.execute(f"UPDATE app_users SET is_admin = {ph} WHERE LOWER(email) = {ph}", (True, admin_email))
    _initialized_db_key = db_key


def verify_google_credential(credential: str) -> dict[str, Any]:
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured on backend.")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise RuntimeError("google-auth is not installed on backend.") from exc

    claims = id_token.verify_oauth2_token(credential, google_requests.Request(), GOOGLE_CLIENT_ID)
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise ValueError("Invalid Google token issuer.")
    if not claims.get("email_verified"):
        raise ValueError("Google account email is not verified.")
    if not claims.get("sub") or not claims.get("email"):
        raise ValueError("Google token is missing required identity claims.")
    return claims


def upsert_google_user(claims: dict[str, Any]) -> dict[str, Any]:
    init_auth_db()
    ph = _placeholder()
    now = _iso()
    google_sub = str(claims["sub"])
    email = str(claims["email"]).lower()
    is_admin = email in ADMIN_EMAILS
    with _connect(row_factory=True) as conn:
        row = conn.execute(f"SELECT * FROM app_users WHERE google_sub = {ph}", (google_sub,)).fetchone()
        if not row:
            email_row = conn.execute(f"SELECT * FROM app_users WHERE email = {ph}", (email,)).fetchone()
            if email_row:
                raise ValueError("Email is already linked to another Google identity.")
            returning = " RETURNING id" if _using_postgres() else ""
            cursor = conn.execute(
                f"""
                INSERT INTO app_users
                (google_sub, email, email_verified, name, picture_url, locale, is_active, is_admin, created_at, updated_at, last_login_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}){returning}
                """,
                (
                    google_sub,
                    email,
                    bool(claims.get("email_verified")),
                    claims.get("name"),
                    claims.get("picture"),
                    claims.get("locale"),
                    True,
                    is_admin,
                    now,
                    now,
                    now,
                ),
            )
            user_id = cursor.fetchone()[0] if _using_postgres() else cursor.lastrowid
        else:
            existing = _row_dict(row)
            if not existing.get("is_active"):
                raise ValueError("User account is disabled.")
            user_id = existing["id"]
            conn.execute(
                f"""
                UPDATE app_users
                SET email = {ph}, email_verified = {ph}, name = {ph}, picture_url = {ph}, locale = {ph},
                    is_admin = {ph}, updated_at = {ph}, last_login_at = {ph}
                WHERE id = {ph}
                """,
                (
                    email,
                    bool(claims.get("email_verified")),
                    claims.get("name"),
                    claims.get("picture"),
                    claims.get("locale"),
                    is_admin,
                    now,
                    now,
                    user_id,
                ),
            )
        user_row = conn.execute(f"SELECT * FROM app_users WHERE id = {ph}", (user_id,)).fetchone()
    return _row_dict(user_row)


def create_session(user_id: int, ip_address: str | None, user_agent: str | None) -> tuple[str, dict[str, Any]]:
    init_auth_db()
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    created_at = _now()
    expires_at = created_at + timedelta(days=SESSION_DAYS)
    ph = _placeholder()
    returning = " RETURNING id" if _using_postgres() else ""
    with _connect() as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO auth_sessions
            (user_id, token_hash, created_at, expires_at, last_seen_at, ip_address, user_agent)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}){returning}
            """,
            (user_id, token_hash, _iso(created_at), _iso(expires_at), _iso(created_at), ip_address, user_agent),
        )
        session_id = cursor.fetchone()[0] if _using_postgres() else cursor.lastrowid
    return raw_token, {"id": session_id, "expires_at": _iso(expires_at)}


def authenticate_session(raw_token: str | None) -> tuple[dict[str, Any] | None, int | None]:
    if not raw_token:
        return None, None
    init_auth_db()
    ph = _placeholder()
    with _connect(row_factory=True) as conn:
        row = conn.execute(
            f"""
            SELECT u.*, s.id AS session_id, s.expires_at
            FROM auth_sessions s
            JOIN app_users u ON u.id = s.user_id
            WHERE s.token_hash = {ph} AND s.revoked_at IS NULL AND s.expires_at > {ph} AND u.is_active = {ph}
            """,
            (_hash_token(raw_token), _iso(), True),
        ).fetchone()
        if not row:
            return None, None
        data = _row_dict(row)
        session_id = data.pop("session_id")
        data.pop("expires_at", None)
        conn.execute(f"UPDATE auth_sessions SET last_seen_at = {ph} WHERE id = {ph}", (_iso(), session_id))
    return data, session_id


def revoke_session(raw_token: str | None) -> int | None:
    if not raw_token:
        return None
    init_auth_db()
    ph = _placeholder()
    with _connect() as conn:
        row = conn.execute(f"SELECT id FROM auth_sessions WHERE token_hash = {ph}", (_hash_token(raw_token),)).fetchone()
        if not row:
            return None
        session_id = row[0]
        conn.execute(f"UPDATE auth_sessions SET revoked_at = {ph} WHERE id = {ph}", (_iso(), session_id))
    return session_id


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture_url": user.get("picture_url"),
        "locale": user.get("locale"),
        "is_admin": bool(user.get("is_admin")),
    }


def list_audit_events(limit: int = 100) -> dict[str, list[dict[str, Any]]]:
    init_auth_db()
    ph = _placeholder()
    bounded_limit = min(max(limit, 1), 500)
    with _connect(row_factory=True) as conn:
        login_rows = conn.execute(
            f"""
            SELECT le.*, u.name AS user_name
            FROM login_events le
            LEFT JOIN app_users u ON u.id = le.user_id
            ORDER BY le.id DESC LIMIT {ph}
            """,
            (bounded_limit,),
        ).fetchall()
        activity_rows = conn.execute(
            f"""
            SELECT ua.*, u.email, u.name AS user_name
            FROM user_activity ua
            JOIN app_users u ON u.id = ua.user_id
            ORDER BY ua.id DESC LIMIT {ph}
            """,
            (bounded_limit,),
        ).fetchall()
    return {
        "login_events": [_row_dict(row) for row in login_rows],
        "activity": [_row_dict(row) for row in activity_rows],
    }


def log_login_event(
    event_type: str,
    success: bool,
    ip_address: str | None,
    user_agent: str | None,
    user_id: int | None = None,
    email: str | None = None,
    failure_reason: str | None = None,
) -> None:
    init_auth_db()
    ph = _placeholder()
    with _connect() as conn:
        conn.execute(
            f"""
            INSERT INTO login_events
            (user_id, event_type, email, success, failure_reason, ip_address, user_agent, created_at)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (user_id, event_type, email, success, (failure_reason or "")[:500] or None, ip_address, user_agent, _iso()),
        )


def log_user_activity(
    user_id: int,
    session_id: int | None,
    method: str,
    path: str,
    status_code: int,
    ip_address: str | None,
    user_agent: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    init_auth_db()
    ph = _placeholder()
    with _connect() as conn:
        conn.execute(
            f"""
            INSERT INTO user_activity
            (user_id, session_id, activity_type, method, path, status_code, ip_address, user_agent, metadata_json, created_at)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (
                user_id,
                session_id,
                "api_request",
                method[:12],
                path[:500],
                status_code,
                ip_address,
                user_agent,
                json.dumps(metadata or {}),
                _iso(),
            ),
        )
