from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import AuthContext, can_edit, can_view, dashboard_permissions, require_user
from ..models import Dashboard
from ..schemas import ClickEvent, DashboardConfig, DashboardContent
from ..services import audit
from ..services.settings import get_section

router = APIRouter(prefix="/api", tags=["dashboards"])


def dashboard_out(d: Dashboard, *, editable: bool | None = None, full: bool = True) -> dict:
    out = {
        "id": d.id,
        "slug": d.slug,
        "title": d.title,
        "subtitle": d.subtitle or "",
        "logo": d.logo or "",
        "visibility": d.visibility,
        "position": d.position,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        "updated_by": d.updated_by,
    }
    if editable is not None:
        out["can_edit"] = editable
    if full:
        out["config"] = DashboardConfig.model_validate(d.config or {}).model_dump()
    return out


@router.get("/dashboards")
def list_dashboards(auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    perms = dashboard_permissions(db, auth)
    if not perms:
        return []
    rows = db.scalars(select(Dashboard).where(Dashboard.id.in_(perms)).order_by(Dashboard.position, Dashboard.title)).all()
    return [dashboard_out(d, editable=perms[d.id], full=False) for d in rows]


def _get_by_slug(db: Session, slug: str) -> Dashboard:
    d = db.scalar(select(Dashboard).where(Dashboard.slug == slug))
    if d is None:
        raise HTTPException(404, "Dashboard not found")
    return d


@router.get("/dashboards/{slug}")
def get_dashboard(slug: str, request: Request, auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    d = _get_by_slug(db, slug)
    if not can_view(db, auth, d):
        raise HTTPException(404, "Dashboard not found")
    if get_section(db, "logs")["log_views"] and request.headers.get("x-portal-preview") != "1":
        audit.record(db, category="navigation", event="view_dashboard", request=request, user=auth.user, dashboard=d, target=f"/d/{d.slug}")
    return dashboard_out(d, editable=can_edit(db, auth, d))


@router.get("/dashboards/id/{dashboard_id}/edit")
def get_for_edit(dashboard_id: int, auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    d = db.get(Dashboard, dashboard_id)
    if d is None or not can_edit(db, auth, d):
        raise HTTPException(404, "Dashboard not found")
    return dashboard_out(d, editable=True)


@router.put("/dashboards/id/{dashboard_id}/content")
def update_content(
    dashboard_id: int, body: DashboardContent, request: Request,
    auth: AuthContext = Depends(require_user), db: Session = Depends(get_db),
):
    d = db.get(Dashboard, dashboard_id)
    if d is None or not can_edit(db, auth, d):
        raise HTTPException(404, "Dashboard not found")
    d.title, d.subtitle, d.logo = body.title, body.subtitle, body.logo
    d.config = body.config.model_dump()
    d.updated_by = auth.user.username
    audit.record(db, category="admin", event="dashboard_edit", request=request, user=auth.user, dashboard=d, commit=False)
    db.commit()
    return dashboard_out(d, editable=True)


@router.post("/logs/click", status_code=204)
def log_click(body: ClickEvent, request: Request, auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    if not get_section(db, "logs")["log_clicks"]:
        return
    dash = db.get(Dashboard, body.dashboard_id) if body.dashboard_id else None
    if dash is not None and not can_view(db, auth, dash):
        dash = None
    audit.record(
        db, category="navigation", event="click_link", request=request, user=auth.user, dashboard=dash,
        target=body.url, label=body.label, details={"section": body.section} if body.section else None,
    )
