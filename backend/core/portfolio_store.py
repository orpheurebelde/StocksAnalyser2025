from datetime import datetime, timezone
from typing import Any

from core import auth

MAX_PORTFOLIOS_PER_USER = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_portfolio_db() -> None:
    auth.init_auth_db()
    if auth._using_postgres():
        statements = [
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS portfolio_tickers (
                id BIGSERIAL PRIMARY KEY,
                portfolio_id BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                quantity DOUBLE PRECISION NOT NULL DEFAULT 1,
                acquisition_date TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(portfolio_id, ticker)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_portfolio_tickers_portfolio ON portfolio_tickers(portfolio_id)",
        ]
    else:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, name),
                FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS portfolio_tickers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1,
                acquisition_date TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(portfolio_id, ticker),
                FOREIGN KEY(portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_portfolio_tickers_portfolio ON portfolio_tickers(portfolio_id)",
        ]
    with auth._connect() as conn:
        for statement in statements:
            conn.execute(statement)
        if auth._using_postgres():
            conn.execute("ALTER TABLE portfolio_tickers ADD COLUMN IF NOT EXISTS quantity DOUBLE PRECISION NOT NULL DEFAULT 1")
            conn.execute("ALTER TABLE portfolio_tickers ADD COLUMN IF NOT EXISTS acquisition_date TEXT")
        else:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(portfolio_tickers)").fetchall()}
            if "quantity" not in columns:
                conn.execute("ALTER TABLE portfolio_tickers ADD COLUMN quantity REAL NOT NULL DEFAULT 1")
            if "acquisition_date" not in columns:
                conn.execute("ALTER TABLE portfolio_tickers ADD COLUMN acquisition_date TEXT")


def _row_dict(row: Any) -> dict[str, Any]:
    return row if isinstance(row, dict) else dict(row)


def _get_owned_portfolio(conn, user_id: int, portfolio_id: int):
    ph = auth._placeholder()
    return conn.execute(
        f"SELECT * FROM portfolios WHERE id = {ph} AND user_id = {ph}",
        (portfolio_id, user_id),
    ).fetchone()


def _portfolio_payload(conn, row: Any) -> dict[str, Any]:
    data = _row_dict(row)
    ph = auth._placeholder()
    holding_rows = conn.execute(
        f"SELECT ticker, quantity, acquisition_date FROM portfolio_tickers WHERE portfolio_id = {ph} ORDER BY ticker",
        (data["id"],),
    ).fetchall()
    data["holdings"] = [_row_dict(item) for item in holding_rows]
    data["tickers"] = [item["ticker"] for item in data["holdings"]]
    return data


def list_portfolios(user_id: int) -> list[dict[str, Any]]:
    init_portfolio_db()
    ph = auth._placeholder()
    with auth._connect(row_factory=True) as conn:
        rows = conn.execute(
            f"SELECT * FROM portfolios WHERE user_id = {ph} ORDER BY updated_at DESC, id DESC",
            (user_id,),
        ).fetchall()
        return [_portfolio_payload(conn, row) for row in rows]


def get_portfolio(user_id: int, portfolio_id: int) -> dict[str, Any] | None:
    init_portfolio_db()
    with auth._connect(row_factory=True) as conn:
        row = _get_owned_portfolio(conn, user_id, portfolio_id)
        return _portfolio_payload(conn, row) if row else None


def create_portfolio(user_id: int, name: str) -> dict[str, Any]:
    init_portfolio_db()
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Portfolio name is required.")
    if len(clean_name) > 80:
        raise ValueError("Portfolio name must be 80 characters or fewer.")
    ph = auth._placeholder()
    now = _now()
    with auth._connect(row_factory=True) as conn:
        count = conn.execute(
            f"SELECT COUNT(*) AS total FROM portfolios WHERE user_id = {ph}",
            (user_id,),
        ).fetchone()
        total = _row_dict(count)["total"]
        if total >= MAX_PORTFOLIOS_PER_USER:
            raise ValueError(f"Maximum {MAX_PORTFOLIOS_PER_USER} portfolios allowed.")
        try:
            sql = f"INSERT INTO portfolios (user_id, name, created_at, updated_at) VALUES ({ph}, {ph}, {ph}, {ph})"
            cursor = conn.execute(f"{sql} RETURNING id" if auth._using_postgres() else sql, (user_id, clean_name, now, now))
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise ValueError("Portfolio name already exists.") from exc
            raise
        portfolio_id = auth._first_value(cursor.fetchone()) if auth._using_postgres() else cursor.lastrowid
        row = _get_owned_portfolio(conn, user_id, portfolio_id)
        return _portfolio_payload(conn, row)


def rename_portfolio(user_id: int, portfolio_id: int, name: str) -> dict[str, Any] | None:
    init_portfolio_db()
    clean_name = name.strip()
    if not clean_name or len(clean_name) > 80:
        raise ValueError("Portfolio name must contain 1 to 80 characters.")
    ph = auth._placeholder()
    with auth._connect(row_factory=True) as conn:
        if not _get_owned_portfolio(conn, user_id, portfolio_id):
            return None
        try:
            conn.execute(
                f"UPDATE portfolios SET name = {ph}, updated_at = {ph} WHERE id = {ph} AND user_id = {ph}",
                (clean_name, _now(), portfolio_id, user_id),
            )
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise ValueError("Portfolio name already exists.") from exc
            raise
        return _portfolio_payload(conn, _get_owned_portfolio(conn, user_id, portfolio_id))


def delete_portfolio(user_id: int, portfolio_id: int) -> bool:
    init_portfolio_db()
    ph = auth._placeholder()
    with auth._connect() as conn:
        if not _get_owned_portfolio(conn, user_id, portfolio_id):
            return False
        conn.execute(f"DELETE FROM portfolio_tickers WHERE portfolio_id = {ph}", (portfolio_id,))
        conn.execute(f"DELETE FROM portfolios WHERE id = {ph} AND user_id = {ph}", (portfolio_id, user_id))
        return True


def add_ticker(
    user_id: int,
    portfolio_id: int,
    ticker: str,
    quantity: float = 1,
    acquisition_date: str | None = None,
) -> dict[str, Any] | None:
    init_portfolio_db()
    normalized = ticker.strip().upper()
    if not normalized or len(normalized) > 15:
        raise ValueError("Valid ticker is required.")
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    ph = auth._placeholder()
    with auth._connect(row_factory=True) as conn:
        if not _get_owned_portfolio(conn, user_id, portfolio_id):
            return None
        try:
            conn.execute(
                f"INSERT INTO portfolio_tickers (portfolio_id, ticker, quantity, acquisition_date, created_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
                (portfolio_id, normalized, quantity, acquisition_date, _now()),
            )
        except Exception as exc:
            if "unique" in str(exc).lower():
                conn.execute(
                    f"UPDATE portfolio_tickers SET quantity = {ph}, acquisition_date = {ph} WHERE portfolio_id = {ph} AND ticker = {ph}",
                    (quantity, acquisition_date, portfolio_id, normalized),
                )
            else:
                raise
        conn.execute(
            f"UPDATE portfolios SET updated_at = {ph} WHERE id = {ph}",
            (_now(), portfolio_id),
        )
        return _portfolio_payload(conn, _get_owned_portfolio(conn, user_id, portfolio_id))


def update_holding(
    user_id: int,
    portfolio_id: int,
    ticker: str,
    quantity: float,
    acquisition_date: str | None,
) -> dict[str, Any] | None:
    init_portfolio_db()
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    ph = auth._placeholder()
    with auth._connect(row_factory=True) as conn:
        if not _get_owned_portfolio(conn, user_id, portfolio_id):
            return None
        cursor = conn.execute(
            f"UPDATE portfolio_tickers SET quantity = {ph}, acquisition_date = {ph} WHERE portfolio_id = {ph} AND ticker = {ph}",
            (quantity, acquisition_date, portfolio_id, ticker.strip().upper()),
        )
        if cursor.rowcount == 0:
            raise ValueError("Ticker is not part of this portfolio.")
        conn.execute(f"UPDATE portfolios SET updated_at = {ph} WHERE id = {ph}", (_now(), portfolio_id))
        return _portfolio_payload(conn, _get_owned_portfolio(conn, user_id, portfolio_id))


def remove_ticker(user_id: int, portfolio_id: int, ticker: str) -> dict[str, Any] | None:
    init_portfolio_db()
    ph = auth._placeholder()
    with auth._connect(row_factory=True) as conn:
        if not _get_owned_portfolio(conn, user_id, portfolio_id):
            return None
        conn.execute(
            f"DELETE FROM portfolio_tickers WHERE portfolio_id = {ph} AND ticker = {ph}",
            (portfolio_id, ticker.strip().upper()),
        )
        conn.execute(
            f"UPDATE portfolios SET updated_at = {ph} WHERE id = {ph}",
            (_now(), portfolio_id),
        )
        return _portfolio_payload(conn, _get_owned_portfolio(conn, user_id, portfolio_id))
