from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, JSONType


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


user_groups = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_user_source_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(16))  # local | ldap | oidc
    # Stable provider-side key: username (local/ldap, lowercased) or "sub" (oidc)
    external_id: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    ldap_dn: Mapped[str | None] = mapped_column(String(1024))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    groups: Mapped[list["Group"]] = relationship(secondary=user_groups, back_populates="members")


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_group_source_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(16))  # local | ldap | oidc
    external_id: Mapped[str] = mapped_column(String(1024))  # LDAP DN (lowercased), OIDC claim value, local name
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    members: Mapped[list[User]] = relationship(secondary=user_groups, back_populates="groups")


class Dashboard(Base):
    __tablename__ = "dashboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    subtitle: Mapped[str | None] = mapped_column(String(255))
    logo: Mapped[str | None] = mapped_column(String(1024))
    # "authenticated": visible to every signed-in user; "restricted": according to access rules
    visibility: Mapped[str] = mapped_column(String(16), default="restricted")
    position: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(255))

    access: Mapped[list["DashboardAccess"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan", passive_deletes=True
    )


class DashboardAccess(Base):
    __tablename__ = "dashboard_access"
    __table_args__ = (
        CheckConstraint("(group_id IS NULL) <> (user_id IS NULL)", name="ck_access_one_principal"),
        UniqueConstraint("dashboard_id", "group_id", name="uq_access_group"),
        UniqueConstraint("dashboard_id", "user_id", name="uq_access_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(ForeignKey("dashboards.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)

    dashboard: Mapped[Dashboard] = relationship(back_populates="access")
    group: Mapped[Group | None] = relationship()
    user: Mapped[User | None] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"

    # SHA3-256 digest of the token: the plaintext token is never stored.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    auth_source: Mapped[str] = mapped_column(String(16))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship()


class OIDCState(Base):
    __tablename__ = "oidc_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA3-256 of the "state"
    code_verifier: Mapped[str] = mapped_column(String(128))
    nonce: Mapped[str] = mapped_column(String(128))
    next_url: Mapped[str] = mapped_column(String(1024), default="/")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    category: Mapped[str] = mapped_column(String(16), index=True)  # auth | navigation | admin
    event: Mapped[str] = mapped_column(String(48), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    dashboard_id: Mapped[int | None] = mapped_column(ForeignKey("dashboards.id", ondelete="SET NULL"))
    dashboard_title: Mapped[str | None] = mapped_column(String(255))
    target: Mapped[str | None] = mapped_column(String(2048))
    label: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    details: Mapped[dict | None] = mapped_column(JSONType)


class TrustedCA(Base):
    """Extra root/intermediate CA trusted for outgoing TLS (LDAPS, OIDC, status checks)."""
    __tablename__ = "trusted_cas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    pem: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(1024))
    issuer: Mapped[str] = mapped_column(String(1024))
    fingerprint_sha256: Mapped[str] = mapped_column(String(95), unique=True)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    not_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255))


class MfaFactor(Base):
    __tablename__ = "mfa_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # totp | webauthn
    name: Mapped[str] = mapped_column(String(128))
    # TOTP: secret encrypted with AES-256-GCM. WebAuthn: base64url credential id.
    secret: Mapped[str | None] = mapped_column(Text)
    credential_id: Mapped[str | None] = mapped_column(String(1024), unique=True)
    public_key: Mapped[str | None] = mapped_column(Text)  # base64url COSE key
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0)
    last_used_step: Mapped[int] = mapped_column(BigInteger, default=0)  # TOTP replay protection
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))  # SHA3-256
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthChallenge(Base):
    """Short-lived server-side state: pending MFA sign-in, forced enrolment, TOTP / WebAuthn setup."""
    __tablename__ = "auth_challenges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA3-256 of the token
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(24))  # mfa | enroll | totp_setup | webauthn_reg | webauthn_auth
    auth_source: Mapped[str | None] = mapped_column(String(16))
    data: Mapped[dict | None] = mapped_column(JSONType)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
