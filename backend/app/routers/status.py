"""Web application status checks.

The backend probes the URLs (not the browser): it works for internal applications,
honours the trusted CAs from the admin panel and avoids CORS / mixed-content issues.
Only http(s) URLs are probed, only for items an editor flagged, and results are
cached briefly so that many viewers do not multiply the requests.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import AuthContext, can_view, require_user
from ..models import Dashboard
from ..services.settings import get_section
from ..services.trust import ssl_context

router = APIRouter(prefix="/api", tags=["status"])

_cache: dict[tuple, tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="status")


def _probe(url: str, verify, timeout: float) -> dict:
    started = time.perf_counter()
    try:
        with httpx.Client(verify=verify, timeout=timeout, follow_redirects=True, max_redirects=5,
                          headers={"User-Agent": "Portal-NG status check"}) as c:
            r = c.head(url)
            if r.status_code in (405, 501):  # HEAD not supported: fall back to GET
                r = c.get(url)
        code = r.status_code
        state = "up" if code < 400 else "warn" if code < 500 else "down"
        return {"state": state, "code": code, "latency_ms": round((time.perf_counter() - started) * 1000)}
    except httpx.TimeoutException:
        return {"state": "down", "error": "timeout"}
    except httpx.ConnectError as exc:
        msg = str(exc)
        return {"state": "down", "error": "certificate error" if "CERTIFICATE" in msg.upper() else "connection refused or unreachable"}
    except Exception as exc:  # noqa: BLE001 — anything else is reported as down
        return {"state": "down", "error": type(exc).__name__}


@router.get("/dashboards/{slug}/status")
def dashboard_status(slug: str, auth: AuthContext = Depends(require_user), db: Session = Depends(get_db)):
    cfg = get_section(db, "status")
    if not cfg["enabled"]:
        return {"enabled": False, "items": {}}
    d = db.scalar(select(Dashboard).where(Dashboard.slug == slug))
    if d is None or not can_view(db, auth, d):
        raise HTTPException(404, "Dashboard not found")

    targets: dict[str, tuple] = {}
    for section in (d.config or {}).get("sections", []):
        for item in section.get("items", []):
            if not item.get("status_check"):
                continue
            url = (item.get("status_url") or item.get("url") or "").strip()
            if urlsplit(url).scheme.lower() not in ("http", "https"):
                continue
            targets[item.get("id") or item.get("name")] = (url, bool(item.get("status_ignore_tls")))

    timeout = float(cfg["timeout_seconds"])
    ttl = float(cfg["cache_seconds"])
    now = time.monotonic()
    results: dict[str, dict] = {}
    pending: dict[tuple, list[str]] = {}
    with _cache_lock:
        for item_id, key in targets.items():
            hit = _cache.get(key)
            if hit and now - hit[0] < ttl:
                results[item_id] = hit[1]
            else:
                pending.setdefault(key, []).append(item_id)

    if pending:
        secure, insecure = ssl_context(db, True), ssl_context(db, False)
        futures = {key: _pool.submit(_probe, key[0], insecure if key[1] else secure, timeout) for key in pending}
        for key, fut in futures.items():
            res = fut.result()
            with _cache_lock:
                _cache[key] = (time.monotonic(), res)
            for item_id in pending[key]:
                results[item_id] = res
    return {"enabled": True, "items": results, "checked_at": time.time()}
