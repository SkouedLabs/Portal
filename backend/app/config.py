"""Bootstrap configuration read from the environment.

Everything editable from the UI (branding, LDAP, OIDC...) lives in the
database; only infrastructure settings are defined here.
"""
import logging
import os
import secrets
from functools import lru_cache
from urllib.parse import quote, urlsplit

from pydantic import BaseModel

log = logging.getLogger("portal.config")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_or_create_secret(data_dir: str) -> str:
    """Use SECRET_KEY if provided, otherwise generate one and persist it in the data volume.

    Several workers start concurrently: the key is written to a temp file and then
    hard-linked into place, which fails atomically if another worker won the race.
    """
    env = os.getenv("SECRET_KEY", "").strip()
    if env:
        if len(env) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters long (256 bits of entropy recommended).")
        return env

    path = os.path.join(data_dir, "secret_key")
    if not os.path.exists(path):
        os.makedirs(data_dir, exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_urlsafe(48))
        try:
            os.link(tmp, path)
            log.warning("No SECRET_KEY provided: generated one in %s (back it up with the volume).", path)
        except FileExistsError:
            pass
        finally:
            os.unlink(tmp)
    with open(path, encoding="utf-8") as fh:
        key = fh.read().strip()
    if len(key) < 32:
        raise RuntimeError(f"Invalid secret key in {path}")
    return key


def _database_url() -> str:
    """DATABASE_URL, or built from parts (lets the password come from a Podman/Docker secret)."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    password = os.getenv("POSTGRES_PASSWORD", "portal")
    pw_file = os.getenv("POSTGRES_PASSWORD_FILE")
    if pw_file and os.path.isfile(pw_file):
        with open(pw_file, encoding="utf-8") as fh:
            password = fh.read().strip()
    return "postgresql+psycopg://{}:{}@{}:{}/{}".format(
        quote(os.getenv("POSTGRES_USER", "portal"), safe=""),
        quote(password, safe=""),
        os.getenv("POSTGRES_HOST", "db"),
        os.getenv("POSTGRES_PORT", "5432"),
        os.getenv("POSTGRES_DB", "portal"),
    )


class Settings(BaseModel):
    database_url: str
    secret_key: str
    public_url: str
    initial_admin_username: str
    initial_admin_password: str | None
    cookie_secure: bool
    data_dir: str
    max_upload_mb: int
    # Break-glass: re-enables local sign-in even if it was disabled from the admin panel.
    force_local_login: bool

    @property
    def webauthn_rp_id(self) -> str:
        return urlsplit(self.public_url).hostname or "localhost"

    @property
    def upload_dir(self) -> str:
        return os.path.join(self.data_dir, "uploads")


@lru_cache
def get_settings() -> Settings:
    data_dir = os.getenv("DATA_DIR", "/data")
    public_url = (os.getenv("PUBLIC_URL") or "http://localhost:8080").rstrip("/")
    return Settings(
        database_url=_database_url(),
        secret_key=_load_or_create_secret(data_dir),
        public_url=public_url,
        initial_admin_username=os.getenv("INITIAL_ADMIN_USERNAME") or "admin",
        initial_admin_password=os.getenv("INITIAL_ADMIN_PASSWORD") or None,
        # Default: Secure cookies when the portal is served over HTTPS (by the reverse proxy)
        cookie_secure=_bool("COOKIE_SECURE", public_url.lower().startswith("https://")),
        data_dir=data_dir,
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB") or "5"),
        force_local_login=_bool("FORCE_LOCAL_LOGIN", False),
    )
