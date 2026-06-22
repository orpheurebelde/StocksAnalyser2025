from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.auth import (
    COOKIE_DOMAIN,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    SESSION_COOKIE_NAME,
    SESSION_DAYS,
    create_session,
    list_audit_events,
    log_login_event,
    public_user,
    revoke_session,
    upsert_google_user,
    verify_google_credential,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=100, max_length=10000)


def _request_context(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip_address = forwarded or (request.client.host if request.client else None)
    return ip_address, request.headers.get("user-agent", "")[:1000] or None


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        domain=COOKIE_DOMAIN,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )


@router.post("/google")
@limiter.limit("10/minute")
def google_login(request: Request, body: GoogleLoginRequest):
    ip_address, user_agent = _request_context(request)
    try:
        claims = verify_google_credential(body.credential)
        user = upsert_google_user(claims)
        raw_token, session = create_session(user["id"], ip_address, user_agent)
        log_login_event(
            "login_success",
            True,
            ip_address,
            user_agent,
            user_id=user["id"],
            email=user.get("email"),
        )
    except Exception as exc:
        try:
            log_login_event("login_failure", False, ip_address, user_agent, failure_reason=str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Google login failed.") from exc

    response = JSONResponse({"user": public_user(user), "session_expires_at": session["expires_at"]})
    response.set_cookie(
        SESSION_COOKIE_NAME,
        raw_token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        path="/",
        domain=COOKIE_DOMAIN,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )
    return response


@router.get("/me")
@limiter.limit("60/minute")
def current_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": public_user(user)}


@router.get("/admin/audit")
@limiter.limit("20/minute")
def admin_audit(request: Request, limit: int = 100):
    user = getattr(request.state, "user", None)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return list_audit_events(limit)


@router.post("/logout")
@limiter.limit("20/minute")
def logout(request: Request):
    user = getattr(request.state, "user", None)
    ip_address, user_agent = _request_context(request)
    revoke_session(request.cookies.get(SESSION_COOKIE_NAME))
    if user:
        log_login_event(
            "logout",
            True,
            ip_address,
            user_agent,
            user_id=user["id"],
            email=user.get("email"),
        )
    response = JSONResponse({"status": "logged_out"})
    _delete_session_cookie(response)
    return response
