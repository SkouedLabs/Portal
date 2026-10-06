"""Application settings editable from the admin UI."""
import copy
from typing import Any

from sqlalchemy.orm import Session

from ..models import AppSetting
from ..security import decrypt_secret, encrypt_secret

DEFAULTS: dict[str, dict[str, Any]] = {
    "branding": {
        "portal_name": "Portal-NG",
        "subtitle": "Company portal",
        "logo": "",
        "favicon": "",
        "footer": "",
        "login_message": "",
        "primary_color": "#3367d6",
        # Sign-in page background: default (gradient of the primary colour) | color | gradient | image
        "login_bg_type": "default",
        "login_bg_color": "",
        "login_bg_gradient_from": "",
        "login_bg_gradient_to": "",
        "login_bg_gradient_angle": 135,
        "login_background": "",
        "login_bg_overlay": 0.0,
        "login_bg_blur": 0,
    },
    "auth": {
        "local_login_enabled": True,
        "session_ttl_hours": 12,
    },
    "ldap": {
        "enabled": False,
        "server_uri": "ldaps://ldap.example.com:636",
        "start_tls": False,
        "verify_tls": True,
        "ca_cert": "",
        "bind_dn": "",
        "bind_password": "",
        "user_base_dn": "",
        "user_filter": "(&(objectClass=person)(uid={username}))",
        "attr_username": "uid",
        "attr_email": "mail",
        "attr_display_name": "cn",
        "group_base_dn": "",
        "group_filter": "(|(objectClass=groupOfNames)(objectClass=groupOfUniqueNames)(objectClass=group))",
        "group_member_attr": "member",
        "group_member_uses_dn": True,
        "group_name_attr": "cn",
    },
    "oidc": {
        "enabled": False,
        "issuer": "",
        "client_id": "",
        "client_secret": "",
        "token_auth_method": "client_secret_basic",
        "scopes": "openid profile email groups",
        "groups_claim": "groups",
        "username_claim": "preferred_username",
        "button_label": "Sign in with SSO",
        "verify_tls": True,
        "auto_redirect": False,
    },
    "mfa": {
        "totp_enabled": True,
        "webauthn_enabled": True,
        "enforce": "off",  # off | admins | all  (local and LDAP accounts)
    },
    "status": {
        "enabled": True,
        "timeout_seconds": 5,
        "cache_seconds": 30,
    },
    "logs": {
        "retention_days": 90,
        "log_views": True,
        "log_clicks": True,
    },
}

SECRET_FIELDS: dict[str, tuple[str, ...]] = {"ldap": ("bind_password",), "oidc": ("client_secret",)}


def _merge(section: str, stored: dict | None) -> dict:
    data = copy.deepcopy(DEFAULTS[section])
    for k, v in (stored or {}).items():
        if k in data:
            data[k] = v
    return data


def get_section(db: Session, section: str, *, decrypt: bool = True) -> dict:
    row = db.get(AppSetting, section)
    data = _merge(section, row.value if row else None)
    if decrypt:
        for f in SECRET_FIELDS.get(section, ()):
            data[f] = decrypt_secret(data.get(f))
    return data


def get_section_public(db: Session, section: str) -> dict:
    """Version returned to admins: secrets never leave the server."""
    data = get_section(db, section, decrypt=False)
    for f in SECRET_FIELDS.get(section, ()):
        data[f"{f}_set"] = bool(data.get(f))
        data[f] = None
    return data


def update_section(db: Session, section: str, values: dict) -> dict:
    row = db.get(AppSetting, section)
    current = _merge(section, row.value if row else None)
    secrets = SECRET_FIELDS.get(section, ())
    for k, v in values.items():
        if k not in current:
            continue
        if k in secrets:
            if v is None:  # null = keep the existing value
                continue
            v = encrypt_secret(v)
        current[k] = v
    if row is None:
        row = AppSetting(key=section, value=current)
        db.add(row)
    else:
        row.value = current
    db.commit()
    return current


def local_login_state(db: Session) -> dict:
    """Local sign-in can only be turned off when LDAP or OIDC is enabled.
    FORCE_LOCAL_LOGIN=true (environment) always turns it back on (break-glass)."""
    from ..config import get_settings

    external = bool(get_section(db, "ldap")["enabled"] or get_section(db, "oidc")["enabled"])
    setting = bool(get_section(db, "auth")["local_login_enabled"])
    forced = get_settings().force_local_login
    return {
        "setting": setting,
        "forced_by_env": forced,
        "external_enabled": external,
        "effective": forced or setting or not external,
    }
