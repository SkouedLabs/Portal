import os
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import AuthContext, is_any_editor, require_user
from ..security import new_token
from ..services import audit, images
from ..services.settings import get_section, local_login_state

router = APIRouter(prefix="/api", tags=["public"])

_NAME = re.compile(r"^[A-Za-z0-9_-]{20,64}\.(png|jpg|gif|webp|ico|svg)$")
_MEDIA = {
    "png": "image/png", "jpg": "image/jpeg", "gif": "image/gif",
    "webp": "image/webp", "ico": "image/x-icon", "svg": "image/svg+xml",
}


def _sniff(head: bytes) -> str | None:
    """Detect the real type from magic bytes (never trust the file name or Content-Type)."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:4] == b"\x00\x00\x01\x00":
        return "ico"
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text.startswith(b"<svg") or (text.startswith(b"<?xml") and b"<svg" in text):
        return "svg"
    return None


@router.get("/public/config")
def public_config(db: Session = Depends(get_db)):
    branding = get_section(db, "branding")
    oidc_cfg = get_section(db, "oidc")
    return {
        "branding": branding,
        "login": {
            "local": local_login_state(db)["effective"],
            "ldap": get_section(db, "ldap")["enabled"],
            "oidc": oidc_cfg["enabled"],
            "oidc_label": oidc_cfg["button_label"],
            "oidc_auto_redirect": oidc_cfg["enabled"] and oidc_cfg["auto_redirect"],
        },
    }


@router.post("/uploads")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    # What the image is for, so it can be bounded to the size it will actually be drawn at:
    # "icon" (logo, favicon, card) or "background". Anything else gets the middle-ground bound.
    kind: str = Form(""),
    auth: AuthContext = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not is_any_editor(db, auth):
        raise HTTPException(403, "Edit rights required")
    settings = get_settings()
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    ext = _sniff(data[:512])
    if ext is None:
        raise HTTPException(415, "Unsupported format (PNG, JPEG, GIF, WebP, ICO, SVG)")
    # Scaled down and re-encoded before it is written: what lands in the volume is what the
    # browser will download, on every view, for as long as it is referenced.
    data, ext = images.optimize(data, ext, kind)
    os.makedirs(settings.upload_dir, exist_ok=True)
    name = f"{new_token(24)}.{ext}"
    with open(os.path.join(settings.upload_dir, name), "wb") as fh:
        fh.write(data)
    audit.record(db, category="admin", event="upload", request=request, user=auth.user, target=name, label=file.filename)
    # "bytes" and "format" are what was actually stored, so the interface can show what the
    # re-encoding saved rather than leaving the uploader guessing.
    return {"url": f"/api/uploads/{name}", "bytes": len(data), "format": ext}


@router.get("/uploads/{name}")
def get_upload(name: str):
    if not _NAME.match(name):
        raise HTTPException(404)
    path = os.path.join(get_settings().upload_dir, name)
    if not os.path.isfile(path):
        raise HTTPException(404)
    return FileResponse(
        path,
        media_type=_MEDIA[name.rsplit(".", 1)[1]],
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            # An SVG opened directly cannot run any script.
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        },
    )
