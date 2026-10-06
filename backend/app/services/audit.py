"""Event logging (navigation, authentication, administration)."""
import logging
from datetime import timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import AuditLog, OIDCState, User, UserSession, utcnow
from .settings import get_section

log = logging.getLogger("portal.audit")


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def record(
    db: Session,
    *,
    category: str,
    event: str,
    request: Request | None = None,
    user: User | None = None,
    username: str | None = None,
    dashboard=None,
    target: str | None = None,
    label: str | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    entry = AuditLog(
        category=category,
        event=event,
        user_id=user.id if user else None,
        username=(user.username if user else username),
        dashboard_id=dashboard.id if dashboard is not None else None,
        dashboard_title=dashboard.title if dashboard is not None else None,
        target=(target or None) and target[:2048],
        label=(label or None) and label[:255],
        ip=client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:512] if request else None),
        details=details,
    )
    db.add(entry)
    if commit:
        db.commit()
    log.info("%s/%s user=%s target=%s", category, event, entry.username, target)


def purge(db: Session) -> None:
    now = utcnow()
    retention = int(get_section(db, "logs").get("retention_days") or 90)
    db.execute(delete(AuditLog).where(AuditLog.ts < now - timedelta(days=max(retention, 1))))
    db.execute(delete(UserSession).where(UserSession.expires_at < now))
    db.execute(delete(OIDCState).where(OIDCState.created_at < now - timedelta(minutes=15)))
    from .mfa import purge_challenges

    purge_challenges(db)
    db.commit()
