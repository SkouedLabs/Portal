"""Self-service security page: MFA enrolment and management.

Two ways to call these endpoints:
* with a session (normal case, CSRF protected);
* with the `X-MFA-Token` header returned by /api/auth/login when enrolment is
  enforced: the first enrolled factor then opens the session.
"""
from dataclasses import dataclass

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import AuthContext, get_optional_auth, user_is_admin
from ..models import AuthChallenge, MfaFactor, User
from ..services import audit, mfa
from .auth import finish_login

router = APIRouter(prefix="/api/account", tags=["account"])


@dataclass
class Actor:
    user: User
    auth: AuthContext | None = None
    enrol: AuthChallenge | None = None


def get_actor(request: Request, db: Session = Depends(get_db), auth: AuthContext | None = Depends(get_optional_auth)) -> Actor:
    token = request.headers.get("x-mfa-token")
    if token:
        try:
            ch = mfa.get_challenge(db, token, ("enroll",))
        except mfa.MfaError as exc:
            raise HTTPException(401, str(exc))
        actor = Actor(user=db.get(User, ch.user_id), enrol=ch)
    elif auth is not None:
        actor = Actor(user=auth.user, auth=auth)
    else:
        raise HTTPException(401, "Authentication required")
    if actor.user is None or not actor.user.is_active:
        raise HTTPException(401, "Account disabled")
    if actor.user.source not in mfa.MFA_SOURCES:
        raise HTTPException(422, "Multi-factor authentication is managed by your identity provider")
    return actor


def require_session(actor: Actor = Depends(get_actor)) -> Actor:
    if actor.auth is None:
        raise HTTPException(401, "Authentication required")
    return actor


def _require_method(db: Session, method: str) -> None:
    if method not in mfa.methods_enabled(db):
        raise HTTPException(422, "This method is disabled by the administrator")


def _after_enrolment(db: Session, request: Request, response: Response, actor: Actor, factor: MfaFactor) -> dict:
    audit.record(db, category="auth", event="mfa_enrolled", request=request, user=actor.user, details={"kind": factor.kind})
    codes = None
    if not mfa.recovery_remaining(db, actor.user):
        codes = mfa.regenerate_recovery_codes(db, actor.user)
    signed_in = False
    if actor.enrol is not None:
        source = actor.enrol.auth_source or actor.user.source
        db.delete(actor.enrol)
        db.commit()
        finish_login(db, request, response, actor.user, source, factor.kind)
        signed_in = True
    return {"factor": mfa.factor_out(factor), "recovery_codes": codes, "signed_in": signed_in}


@router.get("/mfa")
def mfa_status(actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    return {
        "methods": mfa.methods_enabled(db),
        "enforced": mfa.enrolment_required(db, actor.user, user_is_admin(actor.user)),
        "factors": [mfa.factor_out(f) for f in mfa.user_factors(db, actor.user)],
        "recovery_remaining": mfa.recovery_remaining(db, actor.user),
    }


@router.post("/mfa/totp/begin")
def totp_begin(actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    _require_method(db, "totp")
    return mfa.totp_begin(db, actor.user)


@router.post("/mfa/totp/finish")
def totp_finish(
    request: Request, response: Response,
    setup_token: str = Body(...), code: str = Body(..., max_length=16), name: str = Body("", max_length=128),
    actor: Actor = Depends(get_actor), db: Session = Depends(get_db),
):
    _require_method(db, "totp")
    try:
        factor = mfa.totp_finish(db, actor.user, setup_token, code, name.strip())
    except mfa.MfaError as exc:
        raise HTTPException(422, str(exc))
    return _after_enrolment(db, request, response, actor, factor)


@router.post("/mfa/webauthn/begin")
def webauthn_begin(actor: Actor = Depends(get_actor), db: Session = Depends(get_db)):
    _require_method(db, "webauthn")
    return mfa.webauthn_register_begin(db, actor.user)


@router.post("/mfa/webauthn/finish")
def webauthn_finish(
    request: Request, response: Response,
    registration_token: str = Body(...), credential: dict = Body(...), name: str = Body("", max_length=128),
    actor: Actor = Depends(get_actor), db: Session = Depends(get_db),
):
    _require_method(db, "webauthn")
    try:
        factor = mfa.webauthn_register_finish(db, actor.user, registration_token, credential, name.strip())
    except mfa.MfaError as exc:
        raise HTTPException(422, str(exc))
    return _after_enrolment(db, request, response, actor, factor)


@router.delete("/mfa/factors/{factor_id}", status_code=204)
def delete_factor(factor_id: int, request: Request, actor: Actor = Depends(require_session), db: Session = Depends(get_db)):
    factor = db.get(MfaFactor, factor_id)
    if factor is None or factor.user_id != actor.user.id:
        raise HTTPException(404)
    others = [f for f in mfa.user_factors(db, actor.user, usable_only=True) if f.id != factor.id]
    if not others and mfa.enrolment_required(db, actor.user, user_is_admin(actor.user)):
        raise HTTPException(422, "Multi-factor authentication is mandatory: add another method before removing this one")
    db.delete(factor)
    db.commit()
    if not mfa.user_factors(db, actor.user):
        mfa.clear(db, actor.user)  # no factor left: recovery codes are meaningless
    audit.record(db, category="auth", event="mfa_removed", request=request, user=actor.user, details={"kind": factor.kind})


@router.post("/mfa/recovery-codes")
def new_recovery_codes(request: Request, actor: Actor = Depends(require_session), db: Session = Depends(get_db)):
    if not mfa.user_factors(db, actor.user):
        raise HTTPException(422, "Add an authentication method first")
    codes = mfa.regenerate_recovery_codes(db, actor.user)
    audit.record(db, category="auth", event="mfa_recovery_regenerated", request=request, user=actor.user)
    return {"recovery_codes": codes}
