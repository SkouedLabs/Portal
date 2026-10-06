import logging
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import (
    AuthContext,
    clear_session_cookie,
    create_session,
    dashboard_permissions,
    get_optional_auth,
    require_user,
    user_is_admin,
)
from ..models import OIDCState, User, utcnow
from ..schemas import LoginRequest
from ..security import constant_time_equals, hash_password, password_needs_rehash, token_digest, verify_password
from ..services import audit, ldap, mfa, oidc
from ..services.identity import provision
from ..services.settings import get_section, local_login_state

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("portal.auth")

OIDC_COOKIE = "portal_oidc"

# Simple attempt throttling: 10 failures / 15 min per (IP, username) and 50 per IP.
_failures: dict[str, deque] = defaultdict(deque)
_WINDOW = 900


def _throttled(*keys: str, limit: tuple[int, ...]) -> bool:
    now = time.monotonic()
    for key, lim in zip(keys, limit):
        q = _failures[key]
        while q and now - q[0] > _WINDOW:
            q.popleft()
        if len(q) >= lim:
            return True
    return False


def _fail(*keys: str) -> None:
    now = time.monotonic()
    for key in keys:
        _failures[key].append(now)


def _safe_next(url: str | None) -> str:
    if not url or not url.startswith("/") or url.startswith("//") or "\\" in url:
        return "/"
    return url


def me_payload(db: Session, auth: AuthContext) -> dict:
    u = auth.user
    perms = dashboard_permissions(db, auth)
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name or u.username,
        "email": u.email,
        "source": u.source,
        "is_admin": auth.is_admin,
        "is_superadmin": u.is_superadmin,
        "can_edit_any": auth.is_admin or any(perms.values()),
        "mfa_available": u.source in mfa.MFA_SOURCES and bool(mfa.methods_enabled(db)),
        "groups": [{"id": g.id, "name": g.name, "source": g.source} for g in u.groups],
        "csrf_token": auth.session.csrf_token,
    }


@router.get("/me")
def me(auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    return me_payload(db, auth)


def finish_login(db: Session, request: Request, response: Response, user: User, source: str, method: str | None = None) -> dict:
    user.last_login_at = utcnow()
    db.commit()
    create_session(db, response, request, user, source)
    details = {"method": source} | ({"mfa": method} if method else {})
    audit.record(db, category="auth", event="login", request=request, user=user, details=details)
    return {"ok": True}


def _second_step(db: Session, request: Request, response: Response, user: User, source: str) -> dict:
    """After a valid password: ask for the second factor, force enrolment, or open the session."""
    if user.source in mfa.MFA_SOURCES:
        factors = mfa.user_factors(db, user, usable_only=True)
        if factors:
            methods = sorted({f.kind for f in factors})
            if mfa.recovery_remaining(db, user):
                methods.append("recovery")
            token = mfa.create_challenge(db, user, "mfa", source=source)
            return {"mfa": "verify", "token": token, "methods": methods}
        if mfa.enrolment_required(db, user, user_is_admin(user)):
            token = mfa.create_challenge(db, user, "enroll", source=source)
            return {"mfa": "enroll", "token": token, "methods": mfa.methods_enabled(db)}
    return finish_login(db, request, response, user, source)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = audit.client_ip(request) or "?"
    uname = body.username.strip()
    k_user, k_ip = f"{ip}|{uname.lower()}", f"{ip}"
    if _throttled(k_user, k_ip, limit=(10, 50)):
        audit.record(db, category="auth", event="login_throttled", request=request, username=uname)
        raise HTTPException(429, "Too many attempts, please try again later")

    user: User | None = None
    source = None

    local = db.scalar(select(User).where(User.source == "local", User.external_id == uname.lower()))
    if local and local_login_state(db)["effective"]:
        if verify_password(local.password_hash, body.password) and local.is_active:
            user, source = local, "local"
            if password_needs_rehash(local.password_hash):
                local.password_hash = hash_password(body.password)
    else:
        verify_password(None, body.password)  # constant time

    ldap_cfg = get_section(db, "ldap")
    if user is None and ldap_cfg["enabled"]:
        try:
            ident = ldap.authenticate(ldap.with_trust(db, ldap_cfg), uname, body.password)
        except ldap.LdapError as exc:
            log.error("LDAP unavailable: %s", exc)
            audit.record(db, category="auth", event="ldap_error", request=request, username=uname, details={"error": str(exc)[:300]})
            ident = None
        if ident:
            user = provision(db, ident)
            db.commit()
            if not user.is_active:
                user = None
            source = "ldap"

    if user is None:
        _fail(k_user, k_ip)
        audit.record(db, category="auth", event="login_failed", request=request, username=uname)
        raise HTTPException(401, "Invalid credentials")

    return _second_step(db, request, response, user, source)


@router.post("/logout")
def logout(request: Request, response: Response, auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    audit.record(db, category="auth", event="logout", request=request, user=auth.user, commit=False)
    db.delete(auth.session)
    db.commit()
    clear_session_cookie(response)
    return {"ok": True}


# --- Second factor at sign-in ------------------------------------------------------

def _mfa_challenge(db: Session, token: str):
    try:
        ch = mfa.get_challenge(db, token, ("mfa",))
    except mfa.MfaError as exc:
        raise HTTPException(401, str(exc))
    user = db.get(User, ch.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Account disabled")
    return ch, user


def _mfa_failed(db: Session, request: Request, ch, user: User, method: str):
    mfa.fail_attempt(db, ch)
    audit.record(db, category="auth", event="mfa_failed", request=request, user=user, details={"method": method})
    left = max(mfa.MAX_ATTEMPTS - ch.attempts, 0)
    raise HTTPException(401, f"Invalid code ({left} attempt(s) left)" if left else "Too many attempts, please sign in again")


@router.post("/mfa/verify")
def mfa_verify(
    request: Request, response: Response,
    token: str = Body(...), method: Literal["totp", "recovery"] = Body(...), code: str = Body(..., max_length=64),
    db: Session = Depends(get_db),
):
    ch, user = _mfa_challenge(db, token)
    ok = mfa.totp_verify(db, user, code) if method == "totp" else mfa.recovery_verify(db, user, code)
    if not ok:
        _mfa_failed(db, request, ch, user, method)
    source = ch.auth_source or user.source
    db.delete(ch)
    db.commit()
    if method == "recovery":
        audit.record(db, category="auth", event="mfa_recovery_used", request=request, user=user,
                     details={"remaining": mfa.recovery_remaining(db, user)})
    return finish_login(db, request, response, user, source, method)


@router.post("/mfa/webauthn/options")
def mfa_webauthn_options(token: str = Body(..., embed=True), db: Session = Depends(get_db)):
    ch, user = _mfa_challenge(db, token)
    try:
        return mfa.webauthn_auth_options(db, user, ch)
    except mfa.MfaError as exc:
        raise HTTPException(422, str(exc))


@router.post("/mfa/webauthn/verify")
def mfa_webauthn_verify(
    request: Request, response: Response,
    token: str = Body(...), credential: dict = Body(...),
    db: Session = Depends(get_db),
):
    ch, user = _mfa_challenge(db, token)
    if not mfa.webauthn_verify(db, user, ch, credential):
        _mfa_failed(db, request, ch, user, "webauthn")
    source = ch.auth_source or user.source
    db.delete(ch)
    db.commit()
    return finish_login(db, request, response, user, source, "webauthn")


# --- OpenID Connect ------------------------------------------------------------

def _login_error(msg: str) -> RedirectResponse:
    return RedirectResponse(f"/login?error={quote(msg)}", status_code=302)


@router.get("/oidc/login")
def oidc_login(next: str = "/", db: Session = Depends(get_db)):
    cfg = get_section(db, "oidc")
    if not cfg["enabled"]:
        raise HTTPException(404, "OIDC is disabled")
    try:
        url, state, verifier, nonce = oidc.build_authorization(oidc.with_trust(db, cfg))
    except Exception as exc:
        log.exception("OIDC discovery failed")
        return _login_error(f"SSO provider unreachable: {exc}")
    db.add(OIDCState(id=token_digest(state), code_verifier=verifier, nonce=nonce, next_url=_safe_next(next)))
    db.commit()
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(
        OIDC_COOKIE, state, max_age=600, httponly=True, secure=get_settings().cookie_secure,
        samesite="lax", path="/api/auth/oidc",
    )
    return resp


@router.get("/oidc/callback")
def oidc_callback(request: Request, db: Session = Depends(get_db), code: str = "", state: str = "", error: str = ""):
    if error:
        return _login_error(f"SSO: {error}")
    cookie_state = request.cookies.get(OIDC_COOKIE, "")
    if not state or not cookie_state or not constant_time_equals(state, cookie_state):
        return _login_error("Invalid SSO session, please try again")
    st = db.get(OIDCState, token_digest(state))
    if st is None or st.created_at < utcnow() - timedelta(minutes=10):
        return _login_error("SSO session expired, please try again")
    db.delete(st)
    db.commit()

    cfg = oidc.with_trust(db, get_section(db, "oidc"))
    try:
        ident = oidc.exchange_code(cfg, code, st.code_verifier, st.nonce)
    except Exception as exc:
        log.exception("OIDC sign-in failed")
        audit.record(db, category="auth", event="login_failed", request=request, details={"method": "oidc", "error": str(exc)[:300]})
        return _login_error("SSO authentication refused")

    user = provision(db, ident)
    db.commit()
    if not user.is_active:
        audit.record(db, category="auth", event="login_failed", request=request, user=user, details={"method": "oidc", "reason": "disabled"})
        return _login_error("Account disabled")

    resp = RedirectResponse(st.next_url, status_code=302)
    resp.delete_cookie(OIDC_COOKIE, path="/api/auth/oidc")
    create_session(db, resp, request, user, "oidc")
    audit.record(db, category="auth", event="login", request=request, user=user, details={"method": "oidc"})
    return resp


@router.get("/session")
def session_probe(auth: AuthContext | None = Depends(get_optional_auth)):
    return {"authenticated": auth is not None}
