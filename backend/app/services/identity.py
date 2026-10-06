"""Provisioning of users and groups coming from an external provider."""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Group, User, utcnow


@dataclass
class ExternalGroup:
    external_id: str
    name: str


@dataclass
class ExternalIdentity:
    source: str  # ldap | oidc
    external_id: str
    username: str
    email: str | None = None
    display_name: str | None = None
    ldap_dn: str | None = None
    groups: list[ExternalGroup] = field(default_factory=list)


def upsert_group(db: Session, source: str, external_id: str, name: str) -> Group:
    grp = db.scalar(select(Group).where(Group.source == source, Group.external_id == external_id))
    if grp is None:
        grp = Group(source=source, external_id=external_id, name=name)
        db.add(grp)
    else:
        grp.name = name
    grp.synced_at = utcnow()
    return grp


# OIDC accounts declared by an administrator before their first sign-in: the "sub"
# is not known yet, the account is keyed by username and bound at first sign-in.
PENDING_PREFIX = "pending:"


def pending_external_id(username: str) -> str:
    return PENDING_PREFIX + username.strip().lower()


def provision(db: Session, ident: ExternalIdentity) -> User:
    user = db.scalar(select(User).where(User.source == ident.source, User.external_id == ident.external_id))
    if user is None and ident.source == "oidc":
        user = db.scalar(select(User).where(
            User.source == "oidc", User.external_id == pending_external_id(ident.username), User.last_login_at.is_(None),
        ))
        if user is not None:
            user.external_id = ident.external_id
    if user is None:
        user = User(source=ident.source, external_id=ident.external_id, username=ident.username, is_active=True)
        db.add(user)
    user.username = ident.username
    user.email = ident.email
    user.display_name = ident.display_name or ident.username
    if ident.ldap_dn:
        user.ldap_dn = ident.ldap_dn

    synced = [upsert_group(db, ident.source, g.external_id, g.name) for g in ident.groups]
    # Provider groups are replaced; manually assigned local groups are kept.
    kept = [g for g in user.groups if g.source != ident.source]
    user.groups = kept + synced
    user.last_login_at = utcnow()
    db.flush()
    return user
