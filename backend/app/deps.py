"""Session authentication, CSRF and access control."""
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Dashboard, DashboardAccess, User, UserSession, utcnow
from .security import constant_time_equals, new_token, token_digest
from .services.audit import client_ip
from .services.settings import get_section

SESSION_COOKIE = "portal_session"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class AuthContext:
    user: User
    session: UserSession
    is_admin: bool
    group_ids: set[int]


def user_is_admin(user: User) -> bool:
    return user.is_superadmin or any(g.is_admin for g in user.groups)


def create_session(db: Session, response: Response, request: Request, user: User, source: str) -> UserSession:
    ttl = int(get_section(db, "auth").get("session_ttl_hours") or 12)
    token = new_token()
    sess = UserSession(
        id=token_digest(token),
        user_id=user.id,
        csrf_token=new_token(),
        auth_source=source,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512],
        expires_at=utcnow() + timedelta(hours=ttl),
    )
    db.add(sess)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ttl * 3600,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    return sess


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=get_settings().cookie_secure, httponly=True, samesite="lax")


def get_optional_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sess = db.get(UserSession, token_digest(token))
    now = utcnow()
    if sess is None or sess.expires_at < now or not sess.user.is_active:
        return None
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not constant_time_equals(sent, sess.csrf_token):
            raise HTTPException(403, "Invalid CSRF token")
    if (now - sess.last_seen_at).total_seconds() > 300:
        sess.last_seen_at = now
        db.commit()
    user = sess.user
    return AuthContext(user=user, session=sess, is_admin=user_is_admin(user), group_ids={g.id for g in user.groups})


def require_user(auth: AuthContext | None = Depends(get_optional_auth)) -> AuthContext:
    if auth is None:
        raise HTTPException(401, "Authentication required")
    return auth


def require_admin(auth: AuthContext = Depends(require_user)) -> AuthContext:
    if not auth.is_admin:
        raise HTTPException(403, "Administrator rights required")
    return auth


# --- Dashboard permissions ----------------------------------------------------

def _access_rules(db: Session, auth: AuthContext, dashboard_id: int | None = None):
    q = select(DashboardAccess).where(
        or_(
            DashboardAccess.user_id == auth.user.id,
            DashboardAccess.group_id.in_(auth.group_ids or {-1}),
        )
    )
    if dashboard_id is not None:
        q = q.where(DashboardAccess.dashboard_id == dashboard_id)
    return db.scalars(q).all()


def dashboard_permissions(db: Session, auth: AuthContext) -> dict[int, bool]:
    """{dashboard_id: can_edit} for every dashboard visible to the user."""
    dashboards = db.scalars(select(Dashboard)).all()
    if auth.is_admin:
        return {d.id: True for d in dashboards}
    perms: dict[int, bool] = {d.id: False for d in dashboards if d.visibility == "authenticated"}
    for rule in _access_rules(db, auth):
        perms[rule.dashboard_id] = perms.get(rule.dashboard_id, False) or rule.can_edit
    return perms


def can_view(db: Session, auth: AuthContext, dash: Dashboard) -> bool:
    return auth.is_admin or dash.visibility == "authenticated" or bool(_access_rules(db, auth, dash.id))


def can_edit(db: Session, auth: AuthContext, dash: Dashboard) -> bool:
    return auth.is_admin or any(r.can_edit for r in _access_rules(db, auth, dash.id))


def is_any_editor(db: Session, auth: AuthContext) -> bool:
    return auth.is_admin or any(r.can_edit for r in _access_rules(db, auth))


def explain_access(db: Session, user: User) -> list[dict]:
    """Effective access of a user to every dashboard, with the reasons (administration view)."""
    admin = user_is_admin(user)
    group_ids = {g.id for g in user.groups}
    rules = db.scalars(
        select(DashboardAccess).where(
            or_(DashboardAccess.user_id == user.id, DashboardAccess.group_id.in_(group_ids or {-1}))
        )
    ).all()
    by_dash: dict[int, list[DashboardAccess]] = {}
    for r in rules:
        by_dash.setdefault(r.dashboard_id, []).append(r)

    out = []
    for d in db.scalars(select(Dashboard).order_by(Dashboard.position, Dashboard.title)).all():
        reasons = []
        if admin:
            reasons.append({"kind": "admin", "can_edit": True})
        if d.visibility == "authenticated":
            reasons.append({"kind": "everyone", "can_edit": False})
        for r in by_dash.get(d.id, []):
            if r.user_id:
                reasons.append({"kind": "user", "can_edit": r.can_edit})
            else:
                reasons.append({"kind": "group", "can_edit": r.can_edit, "group_id": r.group_id, "group": r.group.name})
        out.append({
            "dashboard_id": d.id, "slug": d.slug, "title": d.title, "visibility": d.visibility,
            "can_view": bool(reasons), "can_edit": any(x["can_edit"] for x in reasons), "reasons": reasons,
        })
    return out
