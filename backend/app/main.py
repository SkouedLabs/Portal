import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import select, text

from .config import get_settings
from .db import Base, SessionLocal, engine
from .models import Dashboard, User
from .routers import account, admin, auth, dashboards, logs, public, status
from .security import hash_password, verify_password
from .services import audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("portal")

SAMPLE_CONFIG = {
    "columns": "3",
    "message": {
        "enabled": True,
        "style": "is-info",
        "title": "Welcome to Portal-NG",
        "icon": "fa-solid fa-circle-info",
        "content": "This sample dashboard can be edited with the \"Edit\" button or from the admin panel.",
    },
    "links": [
        {"name": "Intranet", "icon": "fa-solid fa-building", "url": "https://intranet.example.com", "target": "_blank"},
    ],
    "sections": [
        {
            "id": "s1", "name": "Applications", "icon": "fa-solid fa-cloud",
            "items": [
                {"id": "i1", "name": "Mail", "subtitle": "Company webmail", "icon": "fa-solid fa-envelope",
                 "url": "https://mail.example.com", "tag": "app", "tagstyle": "is-info"},
                {"id": "i2", "name": "Wiki", "subtitle": "Internal documentation", "icon": "fa-solid fa-book",
                 "url": "https://wiki.example.com", "tag": "doc", "tagstyle": "is-success"},
            ],
        },
        {
            "id": "s2", "name": "Tools", "icon": "fa-solid fa-screwdriver-wrench",
            "items": [
                {"id": "i3", "name": "Support", "subtitle": "Open a ticket", "icon": "fa-solid fa-life-ring",
                 "url": "https://support.example.com", "tag": "it", "tagstyle": "is-warning"},
            ],
        },
    ],
}


def bootstrap() -> None:
    settings = get_settings()
    with engine.connect() as conn:
        # Advisory lock: several workers start in parallel.
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_lock(7461001)"))
        try:
            Base.metadata.create_all(conn)
            conn.commit()
            with SessionLocal(bind=conn) as db:
                uname = settings.initial_admin_username
                admin_user = db.scalar(select(User).where(User.source == "local", User.external_id == uname.lower()))
                if admin_user is None and not db.scalar(select(User.id).where(User.is_superadmin.is_(True))):
                    password = settings.initial_admin_password
                    if not password:
                        password = secrets.token_urlsafe(18)
                        log.warning("=" * 70)
                        log.warning("Super-admin account created: %s / %s", uname, password)
                        log.warning("Change this password or set INITIAL_ADMIN_PASSWORD.")
                        log.warning("=" * 70)
                    db.add(User(source="local", external_id=uname.lower(), username=uname, display_name="Administrator",
                                password_hash=hash_password(password), is_superadmin=True))
                    log.info("Super-admin \"%s\" created", uname)
                    default_pw = password == "admin"
                else:
                    default_pw = admin_user is not None and verify_password(admin_user.password_hash, "admin")
                if default_pw:
                    log.warning("The super-admin \"%s\" uses the default password \"admin\": change it now "
                                "(Users page) or set INITIAL_ADMIN_PASSWORD before the first start.", uname)
                if not db.scalar(select(Dashboard.id)):
                    db.add(Dashboard(slug="home", title="Home", subtitle="Your applications", visibility="authenticated",
                                     config=SAMPLE_CONFIG, updated_by="system"))
                db.commit()
            conn.commit()
        finally:
            if engine.dialect.name == "postgresql":
                conn.execute(text("SELECT pg_advisory_unlock(7461001)"))
                conn.commit()


async def _housekeeping() -> None:
    while True:
        try:
            with SessionLocal() as db:
                await asyncio.to_thread(audit.purge, db)
        except Exception:
            log.exception("Periodic purge failed")
        await asyncio.sleep(6 * 3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(bootstrap)
    task = asyncio.create_task(_housekeeping())
    yield
    task.cancel()


app = FastAPI(title="Portal-NG", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/uploads/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


for r in (auth.router, account.router, public.router, dashboards.router, status.router, admin.router, logs.router):
    app.include_router(r)
