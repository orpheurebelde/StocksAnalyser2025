import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.auth import (
    COOKIE_DOMAIN,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    GOOGLE_CLIENT_ID,
    SESSION_COOKIE_NAME,
    SESSION_DAYS,
    create_session,
    create_registration_access_request,
    check_login_risk,
    decide_quota_request,
    analysis_quota,
    list_audit_events,
    list_users,
    list_quota_requests,
    list_registration_access_requests,
    list_user_activity,
    log_login_event,
    public_user,
    record_login_device,
    registration_status,
    request_analysis_access,
    request_quota_access,
    revoke_session,
    set_analysis_access,
    upsert_google_user,
    verify_google_credential,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=100, max_length=10000)
    device_id: str = Field(min_length=16, max_length=200)


class RegistrationAccessRequest(GoogleLoginRequest):
    message: str = Field(default="", max_length=1000)


class AnalysisAccessRequest(BaseModel):
    authorized: bool


class QuotaDecisionRequest(BaseModel):
    approved: bool


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


@router.get("/config")
@limiter.limit("60/minute")
def auth_config(request: Request):
    return {"google_client_id": GOOGLE_CLIENT_ID}


@router.post("/google")
@limiter.limit("10/minute")
def google_login(request: Request, body: GoogleLoginRequest):
    ip_address, user_agent = _request_context(request)
    try:
        claims = verify_google_credential(body.credential)
        check_login_risk(str(claims["email"]), body.device_id, ip_address)
        user = upsert_google_user(claims)
        if user.get("is_admin"):
            from core.quarter_earnings import claim_unowned_reports
            claim_unowned_reports(user["id"])
        raw_token, session = create_session(user["id"], ip_address, user_agent)
        record_login_device(user["id"], body.device_id, ip_address, user_agent)
        log_login_event(
            "login_success",
            True,
            ip_address,
            user_agent,
            user_id=user["id"],
            email=user.get("email"),
        )
    except PermissionError as exc:
        logger.warning("Google login blocked by fraud control: %s", exc)
        try:
            log_login_event("login_blocked", False, ip_address, user_agent, failure_reason=str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Google login failed")
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


@router.post("/registration-access/request")
@limiter.limit("3/hour")
def request_registration_access(request: Request, body: RegistrationAccessRequest):
    ip_address, _user_agent = _request_context(request)
    try:
        claims = verify_google_credential(body.credential)
        check_login_risk(str(claims["email"]), body.device_id, ip_address)
        access_request = create_registration_access_request(claims, body.device_id, ip_address, body.message.strip() or None)
        return {"status": "requested", "message": "Access request sent to the administrator profile."}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Registration access request failed")
        raise HTTPException(status_code=500, detail="Could not submit registration access request.") from exc


@router.get("/me")
@limiter.limit("60/minute")
def current_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": public_user(user)}


@router.get("/activity")
@limiter.limit("30/minute")
def current_user_activity(request: Request, limit: int = 25):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"activity": list_user_activity(user["id"], limit)}


@router.post("/analysis-access/request")
@limiter.limit("5/hour")
def request_access(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": request_analysis_access(user["id"])}


@router.get("/analysis-quota")
@limiter.limit("60/minute")
def get_analysis_quota(request: Request):
    return analysis_quota(request.state.user["id"])


@router.post("/analysis-quota/request")
@limiter.limit("5/hour")
def request_daily_quota(request: Request):
    try:
        return request_quota_access(request.state.user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/users")
@limiter.limit("30/minute")
def admin_users(request: Request):
    user = getattr(request.state, "user", None)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return {
        "users": list_users(),
        "registration": registration_status(),
        "registration_requests": list_registration_access_requests(),
    }


@router.get("/admin/quota-requests")
@limiter.limit("30/minute")
def admin_quota_requests(request: Request):
    user = getattr(request.state, "user", None)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return {"requests": list_quota_requests()}


@router.patch("/admin/quota-requests/{request_id}")
@limiter.limit("30/minute")
def admin_decide_quota(request: Request, request_id: int, body: QuotaDecisionRequest):
    user = getattr(request.state, "user", None)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    item = decide_quota_request(request_id, user["id"], body.approved)
    if not item:
        raise HTTPException(status_code=404, detail="Authorization request not found.")
    return {"request": item}


@router.patch("/admin/users/{user_id}/analysis-access")
@limiter.limit("30/minute")
def admin_set_access(request: Request, user_id: int, body: AnalysisAccessRequest):
    user = getattr(request.state, "user", None)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    updated = set_analysis_access(user_id, body.authorized)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"user": updated}


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
