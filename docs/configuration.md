# Configuration

[Documentation](README.md) · [Portal-NG](../README.md)

Two places, and the split is deliberate:

- **The environment** holds what the application needs *before* it can read its own database: where the
  database is, the master key, the public address. These live in `docker-compose.yml`, overridable from a
  `.env` file (copy [`.env.example`](../.env.example)).
- **The database**, edited from the administration, holds everything else: branding, LDAP, OpenID Connect,
  two-step verification, status checks, log retention. Changing any of those takes effect immediately —
  there is nothing to redeploy.

Every environment variable has a default, so `docker compose up -d` works with no `.env` at all.

## Identity and secrets

| Variable | Default | What it does |
|---|---|---|
| `POSTGRES_PASSWORD` | `portal-ng-db-password` | The database password. **Set it before the first start**: PostgreSQL keeps the password it was initialised with. |
| `DATABASE_URL` | built from the parts below | The full SQLAlchemy URL. Set it to point at a database you manage yourself. |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_USER` / `POSTGRES_DB` | `db` / `5432` / `portal` / `portal` | Used to build `DATABASE_URL` when it is not set. |
| `POSTGRES_PASSWORD_FILE` | empty | Read the password from a file instead, so it can come from a Docker or Podman secret. |
| `SECRET_KEY` | empty = generated | The master key, ≥ 32 characters. HKDF-SHA3-512 derives the AES-256-GCM key that encrypts the LDAP and OIDC secrets and the TOTP secrets. Empty means one is generated into `/data/secret_key` in the `app-data` volume. **Changing it makes already stored secrets unreadable.** |
| `INITIAL_ADMIN_USERNAME` | `admin` | The local super-admin created on first start. |
| `INITIAL_ADMIN_PASSWORD` | `admin` | Its password. A warning is logged for as long as the default is in use. An **empty value** generates a random one, printed once in `docker compose logs backend`. |
| `FORCE_LOCAL_LOGIN` | `false` | Break-glass: `true` re-enables local sign-in if it was turned off in the administration. See [Users and rights](users-and-rights.md#local-sign-in-and-break-glass-access). |

## Addresses and the reverse proxy

| Variable | Default | What it does |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | The address users type in their browser. It drives the **OIDC redirect URI**, the **WebAuthn** relying-party identifier and the `Secure` cookies, so it must match the address in the browser exactly. |
| `HTTP_BIND` / `HTTP_PORT` | `127.0.0.1` / `8080` | Where the frontend publishes plain HTTP. `0.0.0.0` only if the reverse proxy runs on another machine. |
| `TRUSTED_PROXIES` | `127.0.0.1/32 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 ::1/128 fc00::/7` | Space-separated CIDRs allowed to set `X-Forwarded-For`. Anything else and the connecting address is used as the client IP. |
| `COOKIE_SECURE` | empty = automatic | `Secure` cookies when `PUBLIC_URL` starts with `https://`. Set it explicitly to override. |
| `FRONTEND_TLS` | `false` | `true` makes the frontend terminate TLS itself, instead of a reverse proxy. See [Deployment](deployment.md#built-in-tls-without-a-reverse-proxy). |

## Limits and storage

| Variable | Default | What it does |
|---|---|---|
| `MAX_UPLOAD_MB` | `10` | The largest image that may be **sent**. It is scaled down and re-encoded to WebP before it is stored, so what browsers download afterwards is a fraction of this — see [Branding](branding.md#images-and-how-they-are-stored). nginx allows 16 MB so the backend is what returns a readable `413`. |
| `DATA_DIR` | `/data` | Where the master key and the uploaded images live. Backed by the `app-data` volume. |

## Images

| Variable | Default | What it does |
|---|---|---|
| `PORTAL_NG_IMAGE_NAMESPACE` | `skouedlabs` | The Docker Hub namespace the compose file pulls from. Point it at your internal registry mirror. |
| `PORTAL_NG_VERSION` | `latest` | The tag to run. Pin it to a release (`1.2.0`) in production, so an upgrade is something you decide. |

## What is configured from the interface instead

| Setting | Where | Documented in |
|---|---|---|
| Portal name, subtitle, logo, favicon, colours, sign-in background, message, footer | Admin › Branding | [Branding](branding.md) |
| LDAP / Active Directory, OpenID Connect, group synchronisation | Admin › Authentication | [Users and rights](users-and-rights.md) |
| Two-step verification, and whether it is required | Admin › Authentication | [Users and rights](users-and-rights.md#two-step-verification) |
| Turning local sign-in off, session lifetime | Admin › Authentication | [Users and rights](users-and-rights.md#local-sign-in-and-break-glass-access) |
| Trusted root and intermediate CAs (internal PKI) | Admin › Certificates | [Security](security.md) |
| Status checks: on/off, timeout, cache | Admin › Branding | [Status checks](monitoring.md#status-checks) |
| Log retention, what is logged | Admin › Branding | [Logs](monitoring.md#logs) |
