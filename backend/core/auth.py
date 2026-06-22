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
MAX_REGISTERED_USERS = max(1, int(os.getenv("MAX_REGISTERED_USERS", "90")))
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


def _first_value(row: Any) -> Any:
    return next(iter(row.values())) if isinstance(row, dict) else row[0]


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
                analysis_requested BOOLEAN NOT NULL DEFAULT FALSE,
                analysis_authorized BOOLEAN NOT NULL DEFAULT FALSE,
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
            """
            CREATE TABLE IF NOT EXISTS analysis_usage (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                feature TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_quota_requests (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                usage_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                decided_at TEXT,
                decided_by BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
                UNIQUE(user_id, usage_date)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS login_devices (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                device_hash TEXT NOT NULL,
                first_ip TEXT,
                last_ip TEXT,
                user_agent TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(user_id, device_hash)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS fraud_events (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
                attempted_email TEXT,
                event_type TEXT NOT NULL,
                ip_address TEXT,
                device_hash TEXT,
                details_json TEXT,
                blocked BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS registration_access_requests (
                id BIGSERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                name TEXT,
                google_sub TEXT NOT NULL,
                ip_address TEXT,
                device_hash TEXT,
                request_message TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
                analysis_requested INTEGER NOT NULL DEFAULT 0,
                analysis_authorized INTEGER NOT NULL DEFAULT 0,
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
            """
            CREATE TABLE IF NOT EXISTS analysis_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_quota_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                usage_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                decided_at TEXT,
                decided_by INTEGER,
                UNIQUE(user_id, usage_date),
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE,
                FOREIGN KEY(decided_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS login_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                device_hash TEXT NOT NULL,
                first_ip TEXT,
                last_ip TEXT,
                user_agent TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(user_id, device_hash),
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS fraud_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                attempted_email TEXT,
                event_type TEXT NOT NULL,
                ip_address TEXT,
                device_hash TEXT,
                details_json TEXT,
                blocked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS registration_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                name TEXT,
                google_sub TEXT NOT NULL,
                ip_address TEXT,
                device_hash TEXT,
                request_message TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
            conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS analysis_requested BOOLEAN NOT NULL DEFAULT FALSE")
            conn.execute("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS analysis_authorized BOOLEAN NOT NULL DEFAULT FALSE")
            conn.execute("ALTER TABLE registration_access_requests ADD COLUMN IF NOT EXISTS request_message TEXT")
        else:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(app_users)").fetchall()}
            if "is_admin" not in columns:
                conn.execute("ALTER TABLE app_users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
            if "analysis_requested" not in columns:
                conn.execute("ALTER TABLE app_users ADD COLUMN analysis_requested INTEGER NOT NULL DEFAULT 0")
            if "analysis_authorized" not in columns:
                conn.execute("ALTER TABLE app_users ADD COLUMN analysis_authorized INTEGER NOT NULL DEFAULT 0")
            request_columns = {row[1] for row in conn.execute("PRAGMA table_info(registration_access_requests)").fetchall()}
            if "request_message" not in request_columns:
                conn.execute("ALTER TABLE registration_access_requests ADD COLUMN request_message TEXT")
        ph = _placeholder()
        for admin_email in ADMIN_EMAILS:
            conn.execute(
                f"UPDATE app_users SET is_admin = {ph}, analysis_authorized = {ph} WHERE LOWER(email) = {ph}",
                (True, True, admin_email),
            )
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
            user_count = _first_value(conn.execute("SELECT COUNT(*) FROM app_users").fetchone())
            if int(user_count) >= MAX_REGISTERED_USERS:
                raise PermissionError(f"Registration limit reached ({MAX_REGISTERED_USERS} users). Contact administrator.")
            returning = " RETURNING id" if _using_postgres() else ""
            cursor = conn.execute(
                f"""
                INSERT INTO app_users
                (google_sub, email, email_verified, name, picture_url, locale, is_active, is_admin, analysis_authorized, created_at, updated_at, last_login_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}){returning}
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
                    is_admin,
                    now,
                    now,
                    now,
                ),
            )
            user_id = _first_value(cursor.fetchone()) if _using_postgres() else cursor.lastrowid
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
        "analysis_requested": bool(user.get("analysis_requested")),
        "analysis_authorized": bool(user.get("analysis_authorized") or user.get("is_admin")),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }


def _device_hash(device_id: str) -> str:
    return hashlib.sha256(f"device:{device_id}".encode("utf-8")).hexdigest()


def _log_fraud_event(
    event_type: str,
    attempted_email: str,
    ip_address: str | None,
    device_hash: str | None,
    blocked: bool,
    details: dict[str, Any],
    user_id: int | None = None,
) -> None:
    ph = _placeholder()
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO fraud_events
                (user_id, attempted_email, event_type, ip_address, device_hash, details_json, blocked, created_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
            (user_id, attempted_email, event_type, ip_address, device_hash, json.dumps(details), blocked, _iso()),
        )


def check_login_risk(email: str, device_id: str, ip_address: str | None) -> None:
    """Block account switching on one browser; treat shared IP as review signal only."""
    init_auth_db()
    ph = _placeholder()
    normalized_email = email.lower()
    hashed_device = _device_hash(device_id)
    cutoff = _iso(_now() - timedelta(days=30))
    with _connect(row_factory=True) as conn:
        device_conflict = conn.execute(
            f"""SELECT u.id, u.email FROM login_devices d JOIN app_users u ON u.id = d.user_id
                WHERE d.device_hash = {ph} AND LOWER(u.email) <> {ph} LIMIT 1""",
            (hashed_device, normalized_email),
        ).fetchone()
        ip_accounts = []
        if ip_address:
            ip_accounts = conn.execute(
                f"""SELECT DISTINCT user_id, email FROM login_events
                    WHERE success = {ph} AND ip_address = {ph} AND created_at >= {ph}
                      AND email IS NOT NULL AND LOWER(email) <> {ph}""",
                (True, ip_address, cutoff, normalized_email),
            ).fetchall()
    if device_conflict:
        conflict = _row_dict(device_conflict)
        _log_fraud_event(
            "device_multiple_accounts",
            normalized_email,
            ip_address,
            hashed_device,
            True,
            {"existing_user_id": conflict["id"], "existing_email": conflict["email"]},
        )
        raise PermissionError("This browser is already linked to another Google account. Contact administrator.")
    if ip_accounts:
        _log_fraud_event(
            "ip_multiple_accounts",
            normalized_email,
            ip_address,
            hashed_device,
            False,
            {"other_user_ids": [_row_dict(row)["user_id"] for row in ip_accounts]},
        )


def record_login_device(user_id: int, device_id: str, ip_address: str | None, user_agent: str | None) -> None:
    init_auth_db()
    ph = _placeholder()
    hashed_device = _device_hash(device_id)
    now = _iso()
    with _connect() as conn:
        row = conn.execute(
            f"SELECT id FROM login_devices WHERE user_id = {ph} AND device_hash = {ph}",
            (user_id, hashed_device),
        ).fetchone()
        if row:
            conn.execute(
                f"UPDATE login_devices SET last_ip = {ph}, user_agent = {ph}, last_seen_at = {ph} WHERE user_id = {ph} AND device_hash = {ph}",
                (ip_address, user_agent, now, user_id, hashed_device),
            )
        else:
            conn.execute(
                f"""INSERT INTO login_devices
                    (user_id, device_hash, first_ip, last_ip, user_agent, first_seen_at, last_seen_at)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                (user_id, hashed_device, ip_address, ip_address, user_agent, now, now),
            )


def request_analysis_access(user_id: int) -> dict[str, Any]:
    init_auth_db()
    ph = _placeholder()
    with _connect(row_factory=True) as conn:
        conn.execute(f"UPDATE app_users SET analysis_requested = {ph}, updated_at = {ph} WHERE id = {ph}", (True, _iso(), user_id))
        row = conn.execute(f"SELECT * FROM app_users WHERE id = {ph}", (user_id,)).fetchone()
    return public_user(_row_dict(row))


def list_users() -> list[dict[str, Any]]:
    init_auth_db()
    with _connect(row_factory=True) as conn:
        rows = conn.execute("SELECT * FROM app_users ORDER BY analysis_requested DESC, created_at DESC").fetchall()
    return [public_user(_row_dict(row)) for row in rows]


def registration_status() -> dict[str, int]:
    init_auth_db()
    with _connect() as conn:
        count = int(_first_value(conn.execute("SELECT COUNT(*) FROM app_users").fetchone()))
    return {"registered_users": count, "registration_limit": MAX_REGISTERED_USERS, "remaining": max(0, MAX_REGISTERED_USERS - count)}


def create_registration_access_request(
    claims: dict[str, Any],
    device_id: str,
    ip_address: str | None,
    request_message: str | None = None,
) -> dict[str, Any]:
    init_auth_db()
    ph = _placeholder()
    email = str(claims["email"]).lower()
    status = registration_status()
    if status["registered_users"] < status["registration_limit"]:
        raise ValueError("Registration is currently available. Try Google login again.")
    now = _iso()
    with _connect(row_factory=True) as conn:
        registered = conn.execute(f"SELECT id FROM app_users WHERE email = {ph}", (email,)).fetchone()
        if registered:
            raise ValueError("This Google account is already registered. Try Google login again.")
        existing = conn.execute(
            f"SELECT id FROM registration_access_requests WHERE email = {ph} AND status = {ph} ORDER BY id DESC LIMIT 1",
            (email, "pending"),
        ).fetchone()
        if existing:
            request_id = _first_value(existing)
            conn.execute(
                f"""UPDATE registration_access_requests
                    SET name = {ph}, google_sub = {ph}, ip_address = {ph}, device_hash = {ph},
                        request_message = {ph}, requested_at = {ph}, updated_at = {ph}
                    WHERE id = {ph}""",
                (claims.get("name"), str(claims["sub"]), ip_address, _device_hash(device_id), request_message, now, now, request_id),
            )
        else:
            returning = " RETURNING id" if _using_postgres() else ""
            cursor = conn.execute(
                f"""INSERT INTO registration_access_requests
                    (email, name, google_sub, ip_address, device_hash, request_message, status, requested_at, updated_at)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}){returning}""",
                (email, claims.get("name"), str(claims["sub"]), ip_address, _device_hash(device_id), request_message, "pending", now, now),
            )
            request_id = _first_value(cursor.fetchone()) if _using_postgres() else cursor.lastrowid
    return {"id": request_id, "email": email, "name": claims.get("name"), "ip_address": ip_address, "request_message": request_message, **status}


def list_registration_access_requests(limit: int = 100) -> list[dict[str, Any]]:
    init_auth_db()
    ph = _placeholder()
    bounded_limit = min(max(limit, 1), 500)
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            f"SELECT * FROM registration_access_requests ORDER BY id DESC LIMIT {ph}",
            (bounded_limit,),
        ).fetchall()
    return [_row_dict(row) for row in rows]


def set_analysis_access(user_id: int, authorized: bool) -> dict[str, Any] | None:
    init_auth_db()
    ph = _placeholder()
    with _connect(row_factory=True) as conn:
        conn.execute(
            f"UPDATE app_users SET analysis_authorized = {ph}, analysis_requested = {ph}, updated_at = {ph} WHERE id = {ph} AND is_admin = {ph}",
            (authorized, False, _iso(), user_id, False),
        )
        row = conn.execute(f"SELECT * FROM app_users WHERE id = {ph}", (user_id,)).fetchone()
    return public_user(_row_dict(row)) if row else None


def analysis_quota(user_id: int) -> dict[str, Any]:
    init_auth_db()
    ph = _placeholder()
    usage_date = _now().date().isoformat()
    with _connect(row_factory=True) as conn:
        used = conn.execute(
            f"SELECT COUNT(*) FROM analysis_usage WHERE user_id = {ph} AND created_at >= {ph}",
            (user_id, f"{usage_date}T00:00:00+00:00"),
        ).fetchone()
        request = conn.execute(
            f"SELECT * FROM analysis_quota_requests WHERE user_id = {ph} AND usage_date = {ph}",
            (user_id, usage_date),
        ).fetchone()
    request_data = _row_dict(request) if request else None
    return {"used": int(_first_value(used)), "limit": 5, "request": request_data, "usage_date": usage_date}


def ensure_analysis_quota(user: dict[str, Any]) -> None:
    if user.get("is_admin"):
        return
    quota = analysis_quota(user["id"])
    if quota["used"] >= quota["limit"] and (quota["request"] or {}).get("status") != "approved":
        raise PermissionError("Daily analysis limit reached. Request administrator authorization.")


def record_analysis_use(user_id: int, feature: str) -> None:
    init_auth_db()
    ph = _placeholder()
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO analysis_usage (user_id, feature, created_at) VALUES ({ph}, {ph}, {ph})",
            (user_id, feature, _iso()),
        )


def request_quota_access(user_id: int) -> dict[str, Any]:
    init_auth_db()
    current = analysis_quota(user_id)
    if current["used"] < current["limit"]:
        raise ValueError("Daily analysis limit has not been reached.")
    ph = _placeholder()
    usage_date = _now().date().isoformat()
    with _connect() as conn:
        existing = conn.execute(
            f"SELECT id FROM analysis_quota_requests WHERE user_id = {ph} AND usage_date = {ph}",
            (user_id, usage_date),
        ).fetchone()
        if existing:
            conn.execute(
                f"UPDATE analysis_quota_requests SET status = {ph}, requested_at = {ph}, decided_at = NULL, decided_by = NULL WHERE user_id = {ph} AND usage_date = {ph}",
                ("pending", _iso(), user_id, usage_date),
            )
        else:
            conn.execute(
                f"INSERT INTO analysis_quota_requests (user_id, usage_date, status, requested_at) VALUES ({ph}, {ph}, {ph}, {ph})",
                (user_id, usage_date, "pending", _iso()),
            )
    return analysis_quota(user_id)


def list_quota_requests() -> list[dict[str, Any]]:
    init_auth_db()
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            """SELECT r.*, u.email, u.name FROM analysis_quota_requests r
               JOIN app_users u ON u.id = r.user_id ORDER BY r.id DESC LIMIT 200"""
        ).fetchall()
    return [_row_dict(row) for row in rows]


def decide_quota_request(request_id: int, admin_id: int, approved: bool) -> dict[str, Any] | None:
    init_auth_db()
    ph = _placeholder()
    status = "approved" if approved else "rejected"
    with _connect(row_factory=True) as conn:
        conn.execute(
            f"UPDATE analysis_quota_requests SET status = {ph}, decided_at = {ph}, decided_by = {ph} WHERE id = {ph}",
            (status, _iso(), admin_id, request_id),
        )
        row = conn.execute(f"SELECT * FROM analysis_quota_requests WHERE id = {ph}", (request_id,)).fetchone()
    return _row_dict(row) if row else None


def list_user_activity(user_id: int, limit: int = 25) -> list[dict[str, Any]]:
    init_auth_db()
    ph = _placeholder()
    bounded_limit = min(max(limit, 1), 100)
    with _connect(row_factory=True) as conn:
        rows = conn.execute(
            f"""
            SELECT activity_type, method, path, status_code, ip_address, metadata_json, created_at
            FROM user_activity
            WHERE user_id = {ph}
            ORDER BY id DESC LIMIT {ph}
            """,
            (user_id, bounded_limit),
        ).fetchall()
    return [_row_dict(row) for row in rows]


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
        fraud_rows = conn.execute(
            f"SELECT * FROM fraud_events ORDER BY id DESC LIMIT {ph}",
            (bounded_limit,),
        ).fetchall()
    return {
        "login_events": [_row_dict(row) for row in login_rows],
        "activity": [_row_dict(row) for row in activity_rows],
        "fraud_events": [_row_dict(row) for row in fraud_rows],
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
