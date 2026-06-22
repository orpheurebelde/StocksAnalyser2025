import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

from core.auth import SESSION_COOKIE_NAME, authenticate_session, init_auth_db, log_user_activity
from routers import auth, comparison, dcf, market, monte_carlo, portfolio, quarter_earnings, stock

DEFAULT_FRONTEND_ORIGINS = [
    "https://stocks-valuation.vercel.app",
    "https://stocksanalyser.onrender.com",
    "http://localhost:5173",
    "http://localhost:3000",
]
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", ",".join(DEFAULT_FRONTEND_ORIGINS)).split(",")
    if origin.strip()
]
PUBLIC_AUTH_PATHS = {"/api/auth/config", "/api/auth/google", "/api/auth/me", "/api/auth/logout"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_auth_db()
    yield


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="StocksAnalyser API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def authenticate_and_audit(request: Request, call_next):
    started = time.perf_counter()
    request.state.user = None
    request.state.session_id = None

    origin = (request.headers.get("origin") or "").rstrip("/")
    if request.method in UNSAFE_METHODS and origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)

    if request.method != "OPTIONS" and request.url.path.startswith("/api/"):
        try:
            user, session_id = authenticate_session(request.cookies.get(SESSION_COOKIE_NAME))
        except Exception:
            return JSONResponse({"detail": "Authentication service unavailable."}, status_code=503)
        request.state.user = user
        request.state.session_id = session_id
        if request.url.path not in PUBLIC_AUTH_PATHS and not user:
            return JSONResponse({"detail": "Authentication required."}, status_code=401)

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        user = getattr(request.state, "user", None)
        if user:
            forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            ip_address = forwarded or (request.client.host if request.client else None)
            try:
                log_user_activity(
                    user["id"],
                    getattr(request.state, "session_id", None),
                    request.method,
                    request.url.path,
                    status_code,
                    ip_address,
                    request.headers.get("user-agent", "")[:1000] or None,
                    {"duration_ms": round((time.perf_counter() - started) * 1000, 2)},
                )
            except Exception:
                pass


# CORS stays outermost so authentication errors also include browser CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(stock.router, prefix="/api/stock", tags=["stock"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(dcf.router, prefix="/api/dcf", tags=["dcf"])
app.include_router(monte_carlo.router, prefix="/api/monte-carlo", tags=["monte-carlo"])
app.include_router(comparison.router, prefix="/api/comparison", tags=["comparison"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(quarter_earnings.router, prefix="/api/quarter-earnings", tags=["quarter-earnings"])


@app.get("/")
@limiter.limit("10/minute")
def read_root(request: Request):
    return {"status": "ok", "message": "API is running"}
