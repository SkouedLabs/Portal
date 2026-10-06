"""LDAP / Active Directory connector."""
import logging
import ssl
from typing import Any

from ldap3 import NONE, SUBTREE, Connection, Server, Tls
from ldap3.utils.conv import escape_filter_chars
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DashboardAccess, Group, User, utcnow
from .identity import ExternalGroup, ExternalIdentity, upsert_group
from .trust import ldap_ca_kwargs

log = logging.getLogger("portal.ldap")


class LdapError(Exception):
    pass


def _server(cfg: dict) -> Server:
    uri = cfg["server_uri"].strip()
    tls = None
    if uri.lower().startswith("ldaps://") or cfg.get("start_tls"):
        ctx_kwargs: dict[str, Any] = {
            "validate": ssl.CERT_REQUIRED if cfg.get("verify_tls", True) else ssl.CERT_NONE,
            **cfg.get("_trust", {}),
        }
        tls = Tls(**ctx_kwargs)
    return Server(uri, use_ssl=uri.lower().startswith("ldaps://"), tls=tls, get_info=NONE, connect_timeout=5)


def _connect(cfg: dict, user: str | None, password: str | None) -> Connection:
    conn = Connection(
        _server(cfg),
        user=user or None,
        password=password or None,
        receive_timeout=10,
        read_only=True,
        raise_exceptions=False,
    )
    try:
        conn.open()
        if cfg.get("start_tls") and not cfg["server_uri"].lower().startswith("ldaps://"):
            if not conn.start_tls():
                raise LdapError("StartTLS failed")
        if not conn.bind():
            raise LdapError(f"Bind failed: {conn.result.get('description')}")
    except LdapError:
        conn.unbind()
        raise
    except Exception as exc:  # network / TLS errors
        raise LdapError(str(exc)) from exc
    return conn


def _first(attrs: dict, name: str) -> str | None:
    if not name:
        return None
    val = attrs.get(name)
    if isinstance(val, list):
        val = val[0] if val else None
    return str(val) if val is not None else None


def _entries(conn: Connection) -> list[dict]:
    return [e for e in (conn.response or []) if e.get("type") == "searchResEntry"]


def _search_groups(conn: Connection, cfg: dict, member_filter: str | None = None) -> list[dict]:
    if not cfg.get("group_base_dn"):
        return []
    flt = cfg["group_filter"] or "(objectClass=*)"
    if member_filter:
        flt = f"(&{flt}{member_filter})"
    attrs = [cfg["group_name_attr"]]
    if not member_filter:
        attrs.append(cfg["group_member_attr"])
    conn.search(cfg["group_base_dn"], flt, SUBTREE, attributes=attrs, paged_size=500)
    return _entries(conn)


def with_trust(db: Session, cfg: dict) -> dict:
    """Attach the trusted CAs (admin panel + LDAP-specific CA) to the connector config."""
    return {**cfg, "_trust": ldap_ca_kwargs(db, cfg.get("ca_cert", ""))}


def authenticate(cfg: dict, username: str, password: str) -> ExternalIdentity | None:
    # An empty password would trigger an "unauthenticated bind" that many directories accept.
    if not username or not password:
        return None
    svc = _connect(cfg, cfg.get("bind_dn"), cfg.get("bind_password"))
    try:
        flt = cfg["user_filter"].replace("{username}", escape_filter_chars(username))
        attrs = [a for a in (cfg["attr_username"], cfg["attr_email"], cfg["attr_display_name"]) if a]
        svc.search(cfg["user_base_dn"], flt, SUBTREE, attributes=attrs, size_limit=2)
        found = _entries(svc)
        if len(found) != 1:
            return None
        entry = found[0]
        dn = entry["dn"]
        try:
            _connect(cfg, dn, password).unbind()
        except LdapError:
            return None

        a = entry.get("attributes", {})
        uid = (_first(a, cfg["attr_username"]) or username).strip()
        member_value = dn if cfg.get("group_member_uses_dn", True) else uid
        member_filter = f"({cfg['group_member_attr']}={escape_filter_chars(member_value)})"
        groups = [
            ExternalGroup(external_id=g["dn"].lower(), name=_first(g.get("attributes", {}), cfg["group_name_attr"]) or g["dn"])
            for g in _search_groups(svc, cfg, member_filter)
        ]
        return ExternalIdentity(
            source="ldap",
            external_id=uid.lower(),
            username=uid,
            email=_first(a, cfg["attr_email"]),
            display_name=_first(a, cfg["attr_display_name"]),
            ldap_dn=dn,
            groups=groups,
        )
    finally:
        svc.unbind()


def test_connection(cfg: dict) -> dict:
    conn = _connect(cfg, cfg.get("bind_dn"), cfg.get("bind_password"))
    try:
        users = 0
        if cfg.get("user_base_dn"):
            flt = cfg["user_filter"].replace("{username}", "*")
            conn.search(cfg["user_base_dn"], flt, SUBTREE, attributes=[], size_limit=1000)
            users = len(_entries(conn))
        groups = len(_search_groups(conn, cfg))
        return {"ok": True, "users_found": users, "groups_found": groups}
    finally:
        conn.unbind()


def sync_groups(db: Session, cfg: dict) -> dict:
    """Synchronise the group list and the memberships of already known LDAP users."""
    conn = _connect(cfg, cfg.get("bind_dn"), cfg.get("bind_password"))
    try:
        entries = _search_groups(conn, cfg)
    finally:
        conn.unbind()

    users = db.scalars(select(User).where(User.source == "ldap")).all()
    by_dn = {u.ldap_dn.lower(): u for u in users if u.ldap_dn}
    by_uid = {u.external_id: u for u in users}
    uses_dn = cfg.get("group_member_uses_dn", True)

    seen: set[str] = set()
    memberships: dict[int, list[Group]] = {u.id: [] for u in users}
    for e in entries:
        attrs = e.get("attributes", {})
        grp = upsert_group(db, "ldap", e["dn"].lower(), _first(attrs, cfg["group_name_attr"]) or e["dn"])
        seen.add(e["dn"].lower())
        members = attrs.get(cfg["group_member_attr"]) or []
        if isinstance(members, str):
            members = [members]
        for m in members:
            u = by_dn.get(str(m).lower()) if uses_dn else by_uid.get(str(m).lower())
            if u:
                memberships[u.id].append(grp)
    db.flush()

    for u in users:
        u.groups = [g for g in u.groups if g.source != "ldap"] + memberships[u.id]

    removed, kept = 0, []
    with_rules = set(db.scalars(select(DashboardAccess.group_id).where(DashboardAccess.group_id.is_not(None))).all())
    # Safeguard: an empty search result (wrong base DN...) must not wipe every group.
    for grp in db.scalars(select(Group).where(Group.source == "ldap")).all() if seen else []:
        if grp.external_id not in seen:
            if grp.id in with_rules or grp.is_admin:
                # Kept (without members, see above) so that its dashboard rights and admin flag are not
                # lost on a filter mistake or a group declared before it exists; delete it by hand.
                kept.append(grp.name)
            else:
                db.delete(grp)
                removed += 1
    db.commit()
    return {"groups": len(seen), "removed": removed, "kept": kept, "users_updated": len(users), "synced_at": utcnow().isoformat()}
