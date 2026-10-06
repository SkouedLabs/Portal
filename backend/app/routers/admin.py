import socket
import ssl
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..deps import AuthContext, explain_access, require_admin, user_is_admin
from ..models import Dashboard, DashboardAccess, Group, MfaFactor, TrustedCA, User, UserSession, user_groups, utcnow
from ..schemas import (
    AccessRule,
    DashboardAdmin,
    ExternalGroupCreate,
    ExternalUserCreate,
    GroupCreate,
    GroupUpdate,
    LocalUserCreate,
    PrincipalRule,
    UserUpdate,
)
from ..security import hash_password
from ..services import audit, ldap, mfa, oidc, trust
from ..services.identity import pending_external_id
from ..services.settings import DEFAULTS, SECRET_FIELDS, get_section, get_section_public, local_login_state, update_section
from .dashboards import dashboard_out

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _act(db: Session, request: Request, auth: AuthContext, event: str, **kw) -> None:
    audit.record(db, category="admin", event=event, request=request, user=auth.user, commit=False, **kw)


# --- Settings -------------------------------------------------------------------

def _type_ok(value, default) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def _range(clean: dict, key: str, lo: float, hi: float) -> None:
    if key in clean and not lo <= clean[key] <= hi:
        raise HTTPException(422, f"{key} must be between {lo} and {hi}")


def _choice(clean: dict, key: str, allowed: set) -> None:
    if key in clean and clean[key] not in allowed:
        raise HTTPException(422, f"{key} must be one of {sorted(allowed)}")


def _settings_out(db: Session, section: str) -> dict:
    data = get_section_public(db, section)
    if section == "auth":
        data["local_login_state"] = local_login_state(db)
    return data


@router.get("/settings/{section}")
def read_settings(section: str, _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    if section not in DEFAULTS:
        raise HTTPException(404)
    return _settings_out(db, section)


@router.put("/settings/{section}")
def write_settings(
    section: str, request: Request, values: dict = Body(...),
    auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db),
):
    if section not in DEFAULTS:
        raise HTTPException(404)
    defaults = DEFAULTS[section]
    clean = {}
    for k, v in values.items():
        if k not in defaults or v is None and k not in SECRET_FIELDS.get(section, ()):
            continue
        if v is not None and not _type_ok(v, defaults[k]):
            raise HTTPException(422, f"Invalid type for {k}")
        clean[k] = v
    if section == "branding":
        from ..schemas import _color, _image  # validate values injected into the DOM
        try:
            for f in ("logo", "favicon", "login_background"):
                if f in clean:
                    clean[f] = _image(clean[f])
            for f in ("primary_color", "login_bg_color", "login_bg_gradient_from", "login_bg_gradient_to"):
                if f in clean:
                    clean[f] = _color(clean[f])
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        _choice(clean, "login_bg_type", {"default", "color", "gradient", "image"})
        _range(clean, "login_bg_gradient_angle", 0, 360)
        _range(clean, "login_bg_overlay", 0, 0.95)
        _range(clean, "login_bg_blur", 0, 30)
    elif section == "auth":
        _range(clean, "session_ttl_hours", 1, 720)
        if clean.get("local_login_enabled") is False and not local_login_state(db)["external_enabled"]:
            raise HTTPException(422, "Enable LDAP or OpenID Connect before disabling local sign-in")
    elif section == "mfa":
        _choice(clean, "enforce", {"off", "admins", "all"})
    elif section == "status":
        _range(clean, "timeout_seconds", 1, 30)
        _range(clean, "cache_seconds", 0, 3600)
    elif section == "logs":
        _range(clean, "retention_days", 1, 3650)
    update_section(db, section, clean)
    _act(db, request, auth, "settings_update", target=section, details={"fields": sorted(clean)})
    db.commit()
    return _settings_out(db, section)


# --- Trusted certificate authorities ----------------------------------------------

def _ca_out(c: TrustedCA) -> dict:
    return {
        "id": c.id, "name": c.name, "subject": c.subject, "issuer": c.issuer,
        "fingerprint_sha256": c.fingerprint_sha256,
        "not_before": c.not_before.isoformat(), "not_after": c.not_after.isoformat(),
        "expired": c.not_after < utcnow(), "self_signed": c.subject == c.issuer,
        "created_at": c.created_at.isoformat() if c.created_at else None, "created_by": c.created_by,
    }


@router.get("/cas")
def list_cas(_: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    return [_ca_out(c) for c in db.scalars(select(TrustedCA).order_by(TrustedCA.name)).all()]


@router.post("/cas", status_code=201)
async def add_ca(
    request: Request,
    name: str = Form(""),
    pem: str = Form(""),
    file: UploadFile | None = File(None),
    auth: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = (await file.read(1024 * 1024)) if file is not None else pem.encode()
    if not data.strip():
        raise HTTPException(422, "Paste a PEM certificate or choose a file")
    try:
        certs = trust.parse_bundle(data)
    except trust.CertificateError as exc:
        raise HTTPException(422, str(exc))
    added, skipped = [], []
    for c in certs:
        if not c.is_ca:
            skipped.append(f"{c.common_name}: not a CA certificate")
            continue
        if c.not_after < utcnow():
            skipped.append(f"{c.common_name}: expired")
            continue
        if db.scalar(select(TrustedCA.id).where(TrustedCA.fingerprint_sha256 == c.fingerprint_sha256)):
            skipped.append(f"{c.common_name}: already trusted")
            continue
        row = TrustedCA(
            name=(name.strip() if len(certs) == 1 and name.strip() else c.common_name)[:255],
            pem=c.pem, subject=c.subject[:1024], issuer=c.issuer[:1024], fingerprint_sha256=c.fingerprint_sha256,
            not_before=c.not_before, not_after=c.not_after, created_by=auth.user.username,
        )
        db.add(row)
        db.flush()
        added.append(row)
    if not added:
        db.rollback()
        raise HTTPException(422, "No certificate added: " + "; ".join(skipped))
    _act(db, request, auth, "ca_add", label=", ".join(a.name for a in added)[:255], details={"skipped": skipped})
    db.commit()
    return {"added": [_ca_out(a) for a in added], "skipped": skipped}


@router.delete("/cas/{ca_id}", status_code=204)
def delete_ca(ca_id: int, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(TrustedCA, ca_id)
    if c is None:
        raise HTTPException(404)
    _act(db, request, auth, "ca_delete", label=c.name, details={"fingerprint": c.fingerprint_sha256})
    db.delete(c)
    db.commit()


@router.post("/cas/test")
def test_tls(url: str = Body(..., embed=True), _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    """Opens a TLS connection with the current trust store and reports the outcome."""
    parts = urlsplit(url if "://" in url else f"https://{url}")
    host = parts.hostname
    if not host:
        raise HTTPException(422, "Invalid URL")
    port = parts.port or (636 if parts.scheme == "ldaps" else 443)
    ctx = trust.ssl_context(db, True)
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
                return {
                    "ok": True, "host": host, "port": port, "protocol": tls.version(), "cipher": tls.cipher()[0],
                    "subject": dict(x[0] for x in cert.get("subject", ())),
                    "issuer": dict(x[0] for x in cert.get("issuer", ())),
                    "not_after": cert.get("notAfter"),
                }
    except ssl.SSLCertVerificationError as exc:
        return {"ok": False, "host": host, "port": port, "error": f"Certificate not trusted: {exc.verify_message}"}
    except (OSError, ssl.SSLError) as exc:
        return {"ok": False, "host": host, "port": port, "error": str(exc)}


@router.post("/ldap/test")
def ldap_test(auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return ldap.test_connection(ldap.with_trust(db, get_section(db, "ldap")))
    except ldap.LdapError as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/ldap/sync")
def ldap_sync(request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        result = ldap.sync_groups(db, ldap.with_trust(db, get_section(db, "ldap")))
    except ldap.LdapError as exc:
        raise HTTPException(502, f"LDAP : {exc}")
    audit.record(db, category="admin", event="ldap_sync", request=request, user=auth.user, details=result)
    return result


@router.post("/oidc/test")
def oidc_test(_: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        meta = oidc.discover(oidc.with_trust(db, get_section(db, "oidc")), force=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "issuer": meta.get("issuer"),
        "redirect_uri": oidc.redirect_uri(),
        "algs": meta.get("id_token_signing_alg_values_supported"),
        "scopes": meta.get("scopes_supported"),
    }


@router.get("/oidc/redirect-uri")
def oidc_redirect(_: AuthContext = Depends(require_admin)):
    return {"redirect_uri": oidc.redirect_uri()}


# --- Users ----------------------------------------------------------------------

def _user_out(u: User, mfa_count: int | None = None) -> dict:
    return {
        "mfa_factors": mfa_count,
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "email": u.email,
        "source": u.source,
        "is_active": u.is_active,
        "is_superadmin": u.is_superadmin,
        "is_admin": user_is_admin(u),
        # External account declared by an administrator, never signed in yet
        "pending": u.source != "local" and u.last_login_at is None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "groups": [{"id": g.id, "name": g.name, "source": g.source, "is_admin": g.is_admin} for g in u.groups],
    }


@router.get("/users")
def list_users(q: str = "", _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(User).options(selectinload(User.groups)).order_by(User.username)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(User.username).like(like) | func.lower(func.coalesce(User.display_name, "")).like(like)
            | func.lower(func.coalesce(User.email, "")).like(like)
        )
    counts = dict(db.execute(select(MfaFactor.user_id, func.count()).group_by(MfaFactor.user_id)).all())
    return [_user_out(u, counts.get(u.id, 0)) for u in db.scalars(stmt.limit(500)).all()]


def _local_groups(db: Session, ids: list[int]) -> list[Group]:
    groups = db.scalars(select(Group).where(Group.id.in_(ids or [-1]))).all()
    if any(g.source != "local" for g in groups):
        raise HTTPException(422, "Only local groups can be assigned manually")
    return list(groups)


@router.post("/users", status_code=201)
def create_user(body: LocalUserCreate, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.source == "local", User.external_id == body.username.lower())):
        raise HTTPException(409, "This username already exists")
    if body.is_superadmin and not auth.user.is_superadmin:
        raise HTTPException(403, "Only a super-admin can create a super-admin")
    u = User(
        source="local", external_id=body.username.lower(), username=body.username,
        display_name=body.display_name or body.username, email=body.email or None,
        password_hash=hash_password(body.password), is_superadmin=body.is_superadmin,
    )
    u.groups = _local_groups(db, body.group_ids)
    db.add(u)
    db.flush()
    _act(db, request, auth, "user_create", target=u.username)
    db.commit()
    return _user_out(u)


@router.post("/users/external", status_code=201)
def declare_external_user(
    body: ExternalUserCreate, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db),
):
    """Declare an LDAP / OIDC account so that rights can be granted before its first sign-in."""
    username = body.username.strip()
    # LDAP accounts are keyed by username, like at sign-in. The OIDC "sub" is unknown until the first
    # sign-in: the account is bound then, by username claim (see services.identity.provision).
    ext = username.lower() if body.source == "ldap" else pending_external_id(username)
    taken = db.scalar(select(User.id).where(User.source == body.source, User.external_id == ext))
    if body.source == "oidc" and taken is None:
        taken = db.scalar(select(User.id).where(User.source == "oidc", func.lower(User.username) == username.lower()))
    if taken is not None:
        raise HTTPException(409, "This account already exists")
    u = User(
        source=body.source, external_id=ext, username=username,
        display_name=body.display_name or username, email=body.email or None, is_active=True,
    )
    db.add(u)
    db.flush()
    _act(db, request, auth, "user_declare", target=username, details={"source": body.source})
    db.commit()
    return _user_out(u, 0)


@router.get("/users/{user_id}/effective-access")
def user_effective_access(user_id: int, _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    return explain_access(db, u)


@router.put("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    changes = body.model_dump(exclude_none=True)
    if body.is_superadmin is not None and not auth.user.is_superadmin:
        raise HTTPException(403, "Only a super-admin can change this status")
    if u.id == auth.user.id and (body.is_active is False or body.is_superadmin is False):
        raise HTTPException(422, "You cannot disable yourself or remove your own rights")
    if body.password is not None:
        if u.source != "local":
            raise HTTPException(422, "Passwords of external accounts are managed in the directory")
        u.password_hash = hash_password(body.password)
        changes["password"] = "***"
    for f in ("display_name", "email", "is_active", "is_superadmin"):
        if getattr(body, f) is not None:
            setattr(u, f, getattr(body, f))
    if body.local_group_ids is not None:
        u.groups = [g for g in u.groups if g.source != "local"] + _local_groups(db, body.local_group_ids)
    if body.is_active is False:
        db.query(UserSession).filter(UserSession.user_id == u.id).delete()
    _act(db, request, auth, "user_update", target=u.username, details={"fields": sorted(changes)})
    db.commit()
    return _user_out(u)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    if u.id == auth.user.id:
        raise HTTPException(422, "You cannot delete your own account")
    if u.is_superadmin and not auth.user.is_superadmin:
        raise HTTPException(403)
    _act(db, request, auth, "user_delete", target=u.username)
    db.delete(u)
    db.commit()


@router.post("/users/{user_id}/mfa/reset", status_code=204)
def reset_mfa(user_id: int, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    if u.is_superadmin and not auth.user.is_superadmin:
        raise HTTPException(403, "Only a super-admin can reset a super-admin's MFA")
    mfa.clear(db, u)
    _act(db, request, auth, "mfa_reset", target=u.username)
    db.commit()


@router.post("/users/{user_id}/logout", status_code=204)
def revoke_sessions(user_id: int, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404)
    db.query(UserSession).filter(UserSession.user_id == u.id).delete()
    _act(db, request, auth, "user_sessions_revoked", target=u.username)
    db.commit()


# --- Groups ---------------------------------------------------------------------

def _group_out(g: Group, count: int, rules: int = 0) -> dict:
    return {
        "id": g.id, "name": g.name, "source": g.source, "external_id": g.external_id,
        "description": g.description, "is_admin": g.is_admin, "members": count, "rules": rules,
        "synced_at": g.synced_at.isoformat() if g.synced_at else None,
    }


def _group_rule_counts(db: Session) -> dict[int, int]:
    q = select(DashboardAccess.group_id, func.count()).where(DashboardAccess.group_id.is_not(None))
    return dict(db.execute(q.group_by(DashboardAccess.group_id)).all())


@router.get("/groups")
def list_groups(_: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(user_groups.c.group_id, func.count()).group_by(user_groups.c.group_id)).all())
    rules = _group_rule_counts(db)
    groups = db.scalars(select(Group).order_by(Group.source, Group.name)).all()
    return [_group_out(g, counts.get(g.id, 0), rules.get(g.id, 0)) for g in groups]


@router.post("/groups", status_code=201)
def create_group(body: GroupCreate, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    g = Group(source="local", external_id=body.name.lower(), name=body.name, description=body.description, is_admin=body.is_admin)
    db.add(g)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This group already exists")
    _act(db, request, auth, "group_create", target=g.name)
    db.commit()
    return _group_out(g, 0)


@router.post("/groups/external", status_code=201)
def declare_external_group(
    body: ExternalGroupCreate, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db),
):
    """Declare an LDAP / OIDC group so that rights can be granted before a member signs in."""
    ext = body.external_id.strip()
    if body.source == "ldap":
        ext = ext.lower()  # same normalisation as the synchronisation
        if "=" not in ext:
            raise HTTPException(422, "Enter the distinguished name of the LDAP group, e.g. cn=staff,ou=groups,dc=example,dc=com")
        default_name = ext.split(",", 1)[0].split("=", 1)[-1]
    else:
        default_name = ext.rsplit("/", 1)[-1] or ext  # same as services.oidc
    if db.scalar(select(Group.id).where(Group.source == body.source, Group.external_id == ext)):
        raise HTTPException(409, "This group already exists")
    g = Group(source=body.source, external_id=ext, name=body.name.strip() or default_name, description=body.description or None)
    db.add(g)
    db.flush()
    _act(db, request, auth, "group_declare", target=g.name, details={"source": body.source, "external_id": ext})
    db.commit()
    return _group_out(g, 0)


@router.put("/groups/{group_id}")
def update_group(group_id: int, body: GroupUpdate, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    g = db.get(Group, group_id)
    if g is None:
        raise HTTPException(404)
    if body.name is not None:
        if g.source != "local":
            raise HTTPException(422, "The name of a synchronised group comes from the directory")
        g.name, g.external_id = body.name, body.name.lower()
    if body.description is not None:
        g.description = body.description
    if body.is_admin is not None:
        if g.is_admin and not body.is_admin and g.id in auth.group_ids and not auth.user.is_superadmin:
            others = [x for x in auth.user.groups if x.is_admin and x.id != g.id]
            if not others:
                raise HTTPException(422, "You would lose your own administrator rights")
        g.is_admin = body.is_admin
    _act(db, request, auth, "group_update", target=g.name, details=body.model_dump(exclude_none=True))
    db.commit()
    count = db.scalar(select(func.count()).select_from(user_groups).where(user_groups.c.group_id == g.id)) or 0
    return _group_out(g, count, _group_rule_counts(db).get(g.id, 0))


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    g = db.get(Group, group_id)
    if g is None:
        raise HTTPException(404)
    _act(db, request, auth, "group_delete", target=g.name)
    db.delete(g)
    db.commit()


# --- Dashboards (administration) --------------------------------------------------

@router.get("/dashboards")
def admin_dashboards(_: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Dashboard)
        .options(
            selectinload(Dashboard.access).selectinload(DashboardAccess.group),
            selectinload(Dashboard.access).selectinload(DashboardAccess.user),
        )
        .order_by(Dashboard.position, Dashboard.title)
    ).all()
    out = []
    for d in rows:
        item = dashboard_out(d, editable=True, full=False)
        item["access_count"] = len(d.access)
        item["access"] = sorted((_access_out(a) for a in d.access), key=lambda a: (a["kind"], a["label"].lower()))
        item["sections"] = len((d.config or {}).get("sections", []))
        out.append(item)
    return out


def _apply_admin(d: Dashboard, body: DashboardAdmin, auth: AuthContext) -> None:
    d.slug, d.title, d.subtitle, d.logo = body.slug, body.title, body.subtitle, body.logo
    d.visibility, d.position = body.visibility, body.position
    d.config = body.config.model_dump()
    d.updated_by = auth.user.username


@router.post("/dashboards", status_code=201)
def create_dashboard(body: DashboardAdmin, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    d = Dashboard()
    _apply_admin(d, body, auth)
    db.add(d)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This slug is already in use")
    _act(db, request, auth, "dashboard_create", dashboard=d)
    db.commit()
    return dashboard_out(d, editable=True)


@router.put("/dashboards/{dashboard_id}")
def update_dashboard(dashboard_id: int, body: DashboardAdmin, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(Dashboard, dashboard_id)
    if d is None:
        raise HTTPException(404)
    _apply_admin(d, body, auth)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This slug is already in use")
    _act(db, request, auth, "dashboard_update", dashboard=d)
    db.commit()
    return dashboard_out(d, editable=True)


@router.patch("/dashboards/{dashboard_id}")
def patch_dashboard(dashboard_id: int, request: Request, values: dict = Body(...), auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    """Quick metadata update (slug, visibility, order)."""
    d = db.get(Dashboard, dashboard_id)
    if d is None:
        raise HTTPException(404)
    merged = dashboard_out(d) | {k: v for k, v in values.items() if k in {"slug", "visibility", "position", "title"}}
    body = DashboardAdmin.model_validate(merged)
    _apply_admin(d, body, auth)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This slug is already in use")
    _act(db, request, auth, "dashboard_update", dashboard=d, details={"fields": sorted(values)})
    db.commit()
    return dashboard_out(d, editable=True, full=False)


@router.post("/dashboards/{dashboard_id}/duplicate", status_code=201)
def duplicate_dashboard(dashboard_id: int, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    src = db.get(Dashboard, dashboard_id)
    if src is None:
        raise HTTPException(404)
    base = f"{src.slug[:50]}-copy"
    slug, n = base, 2
    while db.scalar(select(Dashboard.id).where(Dashboard.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    d = Dashboard(
        slug=slug, title=f"{src.title} (copy)", subtitle=src.subtitle, logo=src.logo,
        visibility="restricted", position=src.position + 1, config=src.config, updated_by=auth.user.username,
    )
    db.add(d)
    db.flush()
    _act(db, request, auth, "dashboard_create", dashboard=d, details={"duplicated_from": src.id})
    db.commit()
    return dashboard_out(d, editable=True, full=False)


@router.delete("/dashboards/{dashboard_id}", status_code=204)
def delete_dashboard(dashboard_id: int, request: Request, auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(Dashboard, dashboard_id)
    if d is None:
        raise HTTPException(404)
    _act(db, request, auth, "dashboard_delete", target=d.slug, label=d.title)
    db.delete(d)
    db.commit()


def _access_out(a: DashboardAccess) -> dict:
    return {
        "id": a.id,
        "group_id": a.group_id,
        "user_id": a.user_id,
        "can_edit": a.can_edit,
        "label": a.group.name if a.group else (a.user.display_name or a.user.username if a.user else "?"),
        "source": a.group.source if a.group else (a.user.source if a.user else None),
        "kind": "group" if a.group_id else "user",
    }


@router.get("/dashboards/{dashboard_id}/access")
def get_access(dashboard_id: int, _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(Dashboard, dashboard_id)
    if d is None:
        raise HTTPException(404)
    return [_access_out(a) for a in d.access]


@router.put("/dashboards/{dashboard_id}/access")
def set_access(
    dashboard_id: int, rules: list[AccessRule], request: Request,
    auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db),
):
    d = db.get(Dashboard, dashboard_id)
    if d is None:
        raise HTTPException(404)
    seen: set[tuple] = set()
    new: list[DashboardAccess] = []
    for r in rules:
        if (r.group_id is None) == (r.user_id is None):
            raise HTTPException(422, "Each rule must target a group OR a user")
        key = ("g", r.group_id) if r.group_id else ("u", r.user_id)
        if key in seen:
            continue
        seen.add(key)
        if r.group_id and db.get(Group, r.group_id) is None or r.user_id and db.get(User, r.user_id) is None:
            raise HTTPException(422, "Unknown group or user")
        new.append(DashboardAccess(group_id=r.group_id, user_id=r.user_id, can_edit=r.can_edit))
    d.access.clear()
    db.flush()
    d.access.extend(new)
    _act(db, request, auth, "dashboard_access", dashboard=d, details={"rules": len(new)})
    db.commit()
    return [_access_out(a) for a in d.access]


# --- Rights seen from a group or a user -------------------------------------------

PrincipalKind = Literal["groups", "users"]


def _principal(db: Session, kind: str, principal_id: int) -> Group | User:
    model = {"groups": Group, "users": User}.get(kind)
    obj = db.get(model, principal_id) if model else None
    if obj is None:
        raise HTTPException(404)
    return obj


def _principal_filter(kind: str, principal_id: int):
    return DashboardAccess.group_id == principal_id if kind == "groups" else DashboardAccess.user_id == principal_id


@router.get("/{kind}/{principal_id}/access")
def get_principal_access(kind: PrincipalKind, principal_id: int, _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    """Rules granted directly to this group / user, one per dashboard."""
    _principal(db, kind, principal_id)
    rules = db.scalars(select(DashboardAccess).where(_principal_filter(kind, principal_id))).all()
    return [{"dashboard_id": r.dashboard_id, "can_edit": r.can_edit} for r in rules]


@router.put("/{kind}/{principal_id}/access")
def set_principal_access(
    kind: PrincipalKind, principal_id: int, rules: list[PrincipalRule], request: Request,
    auth: AuthContext = Depends(require_admin), db: Session = Depends(get_db),
):
    """Replace every rule of this group / user (rules of other groups and users are untouched)."""
    p = _principal(db, kind, principal_id)
    wanted = {r.dashboard_id: r.can_edit for r in rules}
    known = set(db.scalars(select(Dashboard.id).where(Dashboard.id.in_(wanted or [-1]))).all())
    if known != set(wanted):
        raise HTTPException(422, "Unknown dashboard")
    current = {r.dashboard_id: r for r in db.scalars(select(DashboardAccess).where(_principal_filter(kind, principal_id))).all()}
    for dash_id, rule in current.items():
        if dash_id not in wanted:
            db.delete(rule)
        else:
            rule.can_edit = wanted[dash_id]
    for dash_id, editable in wanted.items():
        if dash_id not in current:
            db.add(DashboardAccess(
                dashboard_id=dash_id, can_edit=editable,
                group_id=principal_id if kind == "groups" else None,
                user_id=principal_id if kind == "users" else None,
            ))
    label = p.name if kind == "groups" else p.username
    _act(db, request, auth, "principal_access", target=f"{kind[:-1]}:{label}", details={"rules": len(wanted)})
    db.commit()
    return [{"dashboard_id": k, "can_edit": v} for k, v in wanted.items()]
