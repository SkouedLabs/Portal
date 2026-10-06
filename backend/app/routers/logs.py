import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, cast, Date, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import AuthContext, require_admin
from ..models import AuditLog, Dashboard, Group, User, UserSession, utcnow

router = APIRouter(prefix="/api/admin", tags=["logs"])


def _filtered(
    category: str = "", event: str = "", user: str = "", q: str = "",
    since: datetime | None = None, until: datetime | None = None, dashboard_id: int | None = None,
) -> Select:
    stmt = select(AuditLog)
    if category:
        stmt = stmt.where(AuditLog.category == category)
    if event:
        stmt = stmt.where(AuditLog.event == event)
    if user:
        stmt = stmt.where(func.lower(AuditLog.username).like(f"%{user.lower()}%"))
    if dashboard_id:
        stmt = stmt.where(AuditLog.dashboard_id == dashboard_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(func.coalesce(AuditLog.target, "")).like(like)
            | func.lower(func.coalesce(AuditLog.label, "")).like(like)
            | func.lower(func.coalesce(AuditLog.dashboard_title, "")).like(like)
            | func.coalesce(AuditLog.ip, "").like(like)
        )
    if since:
        stmt = stmt.where(AuditLog.ts >= since)
    if until:
        stmt = stmt.where(AuditLog.ts <= until)
    return stmt


def _row(e: AuditLog) -> dict:
    return {
        "id": e.id, "ts": e.ts.isoformat(), "category": e.category, "event": e.event,
        "username": e.username, "user_id": e.user_id, "dashboard_id": e.dashboard_id,
        "dashboard_title": e.dashboard_title, "target": e.target, "label": e.label,
        "ip": e.ip, "user_agent": e.user_agent, "details": e.details,
    }


@router.get("/logs")
def list_logs(
    category: str = "", event: str = "", user: str = "", q: str = "",
    since: datetime | None = None, until: datetime | None = None, dashboard_id: int | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    _: AuthContext = Depends(require_admin), db: Session = Depends(get_db),
):
    stmt = _filtered(category, event, user, q, since, until, dashboard_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.ts.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_row(e) for e in rows]}


@router.get("/logs/export.csv")
def export_logs(
    category: str = "", event: str = "", user: str = "", q: str = "",
    since: datetime | None = None, until: datetime | None = None, dashboard_id: int | None = None,
    _: AuthContext = Depends(require_admin), db: Session = Depends(get_db),
):
    stmt = _filtered(category, event, user, q, since, until, dashboard_id).order_by(AuditLog.ts.desc()).limit(100_000)
    # Materialised here: the DB session is closed before streaming ends.
    rows = db.scalars(stmt).all()

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["date", "category", "event", "user", "dashboard", "label", "target", "ip", "user_agent"])
        yield "﻿" + buf.getvalue()
        for e in rows:
            buf.seek(0)
            buf.truncate()
            # Neutralise spreadsheet formula injection
            cells = [e.ts.isoformat(), e.category, e.event, e.username, e.dashboard_title, e.label, e.target, e.ip, e.user_agent]
            w.writerow(["'" + c if isinstance(c, str) and c[:1] in "=+-@\t\r" else c for c in cells])
            yield buf.getvalue()

    return StreamingResponse(
        gen(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="portal-ng-logs.csv"'},
    )


@router.get("/stats")
def stats(days: int = Query(14, ge=1, le=365), _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)):
    now = utcnow()
    since = now - timedelta(days=days)
    day = cast(AuditLog.ts, Date)
    per_day = db.execute(
        select(day, AuditLog.category, func.count())
        .where(AuditLog.ts >= since)
        .group_by(day, AuditLog.category)
        .order_by(day)
    ).all()

    def top(col, event: str, limit: int = 10):
        return [
            {"label": label, "count": n}
            for label, n in db.execute(
                select(col, func.count().label("n"))
                .where(AuditLog.ts >= since, AuditLog.event == event, col.is_not(None))
                .group_by(col).order_by(func.count().desc()).limit(limit)
            ).all()
        ]

    return {
        "days": days,
        "per_day": [{"day": d.isoformat(), "category": c, "count": n} for d, c, n in per_day],
        "top_links": top(AuditLog.label, "click_link"),
        "top_dashboards": top(AuditLog.dashboard_title, "view_dashboard"),
        "top_users": top(AuditLog.username, "view_dashboard"),
        "totals": {
            "users": db.scalar(select(func.count()).select_from(User)),
            "groups": db.scalar(select(func.count()).select_from(Group)),
            "dashboards": db.scalar(select(func.count()).select_from(Dashboard)),
            "active_sessions": db.scalar(select(func.count()).select_from(UserSession).where(UserSession.expires_at > now)),
            "logins": db.scalar(select(func.count()).where(AuditLog.ts >= since, AuditLog.event == "login")),
            "failed_logins": db.scalar(select(func.count()).where(AuditLog.ts >= since, AuditLog.event == "login_failed")),
            "clicks": db.scalar(select(func.count()).where(AuditLog.ts >= since, AuditLog.event == "click_link")),
            "views": db.scalar(select(func.count()).where(AuditLog.ts >= since, AuditLog.event == "view_dashboard")),
        },
    }
