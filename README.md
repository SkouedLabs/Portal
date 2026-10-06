# Portal-NG

A company portal inspired by [Homer](https://github.com/bastienwirtz/homer). It keeps Homer's card-and-section look, and adds what Homer lacks for company use: several dashboards, administration from the UI, LDAP / OpenID Connect sign-in with two-step verification, status checks, and navigation logs.

```
.
├── docker-compose.yml        # db (PostgreSQL 17) + backend + frontend
├── .env.example              # optional overrides
├── backend/                  # Python API (FastAPI, SQLAlchemy)
│   └── app/
│       ├── routers/          # auth, account (MFA), dashboards, status, admin, logs, public
│       └── services/         # ldap, oidc, mfa, trust (CAs), provisioning, settings, audit
├── frontend/                 # Vue 3 + Vite, built and served by unprivileged nginx (plain HTTP)
└── example/
    ├── nginx/                # nginx on the host in front of Portal-NG (TLS, admin IP allow-list)
    ├── traefik/              # Traefik in front of Portal-NG (file provider or labels)
    ├── pki/                  # demo internal PKI (CA + server certificate) for the examples
    └── podman/               # rootless Podman quadlet units
```

## Quick start (Docker Compose)

No configuration is needed:

```bash
docker compose up -d 
```

Open http://localhost:8080 and sign in as `admin` / `admin`. **Change this password right away** (Admin › Users), or set `INITIAL_ADMIN_PASSWORD` in a `.env` file before the first start. The backend logs a warning as long as the default password is in use.

On first start, the backend:

- creates the database schema;
- generates the master key (`/data/secret_key` in the `app-data` volume) if `SECRET_KEY` is not set;
- creates the local super-admin;
- creates a sample "Home" dashboard visible to every signed-in user.

The frontend serves **plain HTTP on `127.0.0.1:8080`**, which is not reachable from the network. TLS is the job of your reverse proxy (next section). To override defaults, copy `.env.example` to `.env` and edit it.

### Production checklist

- Put a **reverse proxy** in front for TLS (nginx on the host or Traefik, see below) and set `PUBLIC_URL` to the `https://` address users type. It drives the OIDC redirect URI, WebAuthn security keys and `Secure` cookies.
- Set `POSTGRES_PASSWORD` and `INITIAL_ADMIN_PASSWORD` **before the first start**. PostgreSQL keeps the password it was initialised with.
- Restrict the administration by IP on the proxy (examples provided).
- Back up the `db-data` and `app-data` volumes. `app-data` contains the master key: without it, the stored LDAP/OIDC secrets and TOTP secrets cannot be decrypted.

## Reverse proxy (TLS)

```
browser ──HTTPS (TLS 1.3, X25519MLKEM768)──▶ reverse proxy ──HTTP, local──▶ frontend :8080 ──▶ backend ──▶ db
                                             nginx on the host  127.0.0.1    (non-root nginx)
                                             or Traefik         Docker net.
                                             • certificate, HSTS
                                             • /admin + /api/admin/ IP allow-list
```

Portal-NG holds no certificate. The proxy terminates TLS and forwards plain HTTP to the frontend, either over the host loopback (`127.0.0.1:8080`) or over a Docker network. The frontend:

- sends its own security headers (CSP, `X-Frame-Options`, `nosniff`…); the proxy adds HSTS;
- takes the **real client IP** from `X-Forwarded-For`, but only from `TRUSTED_PROXIES` (default: loopback and private ranges, consistent with a port published on `127.0.0.1`). That IP is the one in the logs and the sign-in throttling.

| Variable (compose / `.env`) | Default | Role |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | Address users type: `https://portal.example.com` behind the proxy |
| `HTTP_BIND` / `HTTP_PORT` | `127.0.0.1` / `8080` | Published HTTP port. Use `0.0.0.0` only if the proxy runs on another machine, and then restrict `TRUSTED_PROXIES` to it |
| `TRUSTED_PROXIES` | `127.0.0.1/32 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 ::1/128 fc00::/7` | Who may set `X-Forwarded-For` |
| `COOKIE_SECURE` | empty = automatic | `Secure` cookies when `PUBLIC_URL` is `https://` |

### nginx on the host

[`example/nginx/portal-ng.conf`](example/nginx/portal-ng.conf) proxies to `127.0.0.1:8080`. It provides TLS 1.3 with X25519MLKEM768 (OpenSSL ≥ 3.5 on the host), HTTP→HTTPS redirect, HSTS, and an IP allow-list on the administration ([`admin-allow.conf`](example/nginx/admin-allow.conf)).

```bash
sudo cp example/nginx/portal-ng.conf /etc/nginx/conf.d/
sudo cp example/nginx/admin-allow.conf /etc/nginx/snippets/portal-ng-admin-allow.conf
# certificate: /etc/nginx/ssl/portal.crt + portal.key (your PKI, or example/pki/gen-certs.sh for a demo)
sudo nginx -t && sudo systemctl reload nginx
```

### Traefik

- **Traefik in the same compose project** ([`example/traefik/compose.yml`](example/traefik/compose.yml)): file provider (no Docker socket mounted), non-root, read-only. It provides TLS 1.3, HTTP→HTTPS redirect, HSTS, and an IP allow-list on the administration. Traefik ≥ 3.x (Go ≥ 1.24) negotiates X25519MLKEM768 by default.

  ```bash
  sh example/pki/gen-certs.sh portal.example.internal     # or put your own portal.crt / portal.key in example/pki/certs
  PUBLIC_URL=https://portal.example.internal \
    docker compose -f docker-compose.yml -f example/traefik/compose.yml up -d --build
  ```

- **Existing Traefik with the Docker provider** ([`example/traefik/compose.labels.yml`](example/traefik/compose.labels.yml)): labels on the frontend, joined to your external `traefik` network.

Both are detailed in [`example/README.md`](example/README.md).

### Administration IP allow-list

Both examples filter **`/admin`** (the UI route) **and `/api/admin/`** (the API). The UI route alone would protect nothing, since the protection that matters is on the API. Tested with the allow-list in deny mode: 17 path-manipulation variants (`//api/admin`, `/api/./admin`, `/api/x/../admin`, `/api/%61dmin`, `/api%2Fadmin`, `;`, `%2e%2e`…) are all refused (403/400) by both nginx and Traefik. The Traefik example also rejects ambiguous encodings and header aliases.

### Built-in TLS (optional, without a reverse proxy)

For a test or a small deployment without a proxy, the frontend can terminate TLS itself: TLS 1.3, X25519MLKEM768, HSTS, HTTP→HTTPS redirect. Self-signed certificate generated if none is provided. Example `docker-compose.override.yml`:

```yaml
services:
  frontend:
    environment:
      FRONTEND_TLS: "true"
      HTTPS_PUBLIC_PORT: "8443"          # port in the HTTP->HTTPS redirect
      TLS_COMMON_NAME: portal.example.com
    ports: !override
      - "8080:8080"
      - "8443:8443"
    volumes:
      # your tls.crt / tls.key (readable by uid 101), or a volume to get a generated self-signed one
      - frontend-certs:/etc/nginx/certs
volumes:
  frontend-certs: {}
```

Then set `PUBLIC_URL=https://portal.example.com:8443`.

## Offline (air-gapped) installation

Portal-NG needs **no internet access at runtime**. Everything the browser loads comes from the portal itself: application code, Font Awesome icons and fonts, the icon search index, TOTP QR codes generated by the server. No CDN, no external fonts, no telemetry. The backend only connects to what you configure: LDAP directory, OIDC provider, status-checked applications. Only building the images needs internet (Python and npm packages, base images).

On a machine with internet access:

```bash
docker compose build
docker pull postgres:17-alpine
docker save -o portal-ng-images.tar \
  emeryn/portal-ng-backend:latest emeryn/portal-ng-frontend:latest postgres:17-alpine
# + traefik:v3 if you use example/traefik
```

Copy `portal-ng-images.tar` and this repository to the offline host, then:

```bash
docker load -i portal-ng-images.tar
docker compose up -d --no-build      # never tries to build or pull
```

Same with Podman: `podman load -i portal-ng-images.tar`, then tag the images as in the quadlet files (`podman tag emeryn/portal-ng-backend:latest localhost/portal-ng-backend:latest`, same for the frontend).

What to plan for offline:

- **Logos and icons of your links**: upload them (Admin, image fields) instead of pointing to internet URLs, or use the bundled Font Awesome icons.
- **Certificates**: internal PKI on the reverse proxy. Import its root CA in Admin › Certificates so the backend trusts your LDAPS directory, IdP and internal applications.
- **OIDC**: the identity provider must be reachable from the backend on your network.

Tested: the stack started on Docker networks with no route to the outside (`internal: true`, no DNS or IP egress). A headless browser then went through the sign-in page, dashboards, editor, icon picker, every admin page, the TOTP enrolment and a Homer import. Result: 0 requests outside the portal, 0 JavaScript errors, icons and fonts rendered.

## Non-root, hardened containers

| Container | User | Root filesystem | Capabilities |
|---|---|---|---|
| `db` (PostgreSQL) | `70:70` (postgres), from the start: no root entrypoint | read-only (+ tmpfs `/tmp`, `/var/run/postgresql`) | none |
| `backend` | `10001:10001` (portal) | read-only (+ tmpfs `/tmp`) | none |
| `frontend` | `101:101` (nginx-unprivileged: no root master process, port 8080) | read-only (+ tmpfs `/tmp`) | none |
| `traefik` (example) | `65532:65532`, ports 8080/8443 inside, published as 80/443 | read-only | none |

Every container also runs with `no-new-privileges`. The quadlet units in `example/podman/` apply the same settings (`User=`, `ReadOnly=`, `DropCapability=all`, `NoNewPrivileges=`).

Files you mount must be readable by these users. Example: certificates for the Traefik example (uid 65532), or for the built-in TLS mode (uid 101).

## Features

| Need | Where |
|---|---|
| Several Homer-style dashboards: sections, cards, icons or uploaded logos, tags, navigation links, message banner, search (`/` key), light/dark theme, column/list view | Admin › Dashboards, then the editor |
| **Icon picker** with search over the 2,000+ Font Awesome Free icons, bundled locally (works offline) | Any icon field, magnifier button |
| Per-dashboard background (colour, gradient, image with darkening and blur) and theme colours, with a live preview | Editor › Appearance |
| **Status checks** of web applications: green / orange / red dot with HTTP code and latency on each card | Editor › link › "Check status" ; settings in Admin › Branding |
| **Migration from Homer**: import an existing Homer instance (its `assets` folder: `config.yml`, additional pages, local logos) into new dashboards | Admin › Dashboards › Import from Homer |
| Import / export of Homer's `config.yml` into an existing dashboard (Homer `Ping` cards become status checks) | Editor › YAML |
| LDAP / Active Directory (OpenLDAP, AD and FreeIPA presets), connection test, group synchronisation | Admin › Authentication |
| OpenID Connect (authorization code + PKCE S256, configurable groups claim, nested claims supported) | Admin › Authentication |
| **Two-step verification** for local and LDAP accounts: authenticator apps (TOTP), security keys and passkeys (WebAuthn), recovery codes. Optional, required for admins, or required for everyone | Admin › Authentication › Two-step verification; users: menu › Security |
| **Trusted root / intermediate CAs** (internal PKI) for LDAPS, the OIDC provider and status checks, plus a TLS connection tester | Admin › Certificates |
| **Turn local sign-in off** once LDAP or SSO is enabled, with a break-glass switch in docker-compose (`FORCE_LOCAL_LOGIN`) | Admin › Authentication › Local sign-in & sessions |
| A group designated as Portal-NG administrators | Admin › Groups, "Administrator" toggle |
| Dashboard access per group (local, LDAP, OIDC) or per user, view or view + edit, managed from the dashboard, the group or the user | Admin › Dashboards › Access; Admin › Groups / Users › Dashboards |
| Portal name, logo, favicon, colour, **sign-in page background** (default, colour, gradient or image with darkening/blur), message, footer | Admin › Branding |
| Logs: dashboards viewed, links opened, sign-ins and failures, MFA events, admin actions; filters, auto-refresh, CSV export, statistics | Admin › Logs and Overview |

### Access rules

- **Administrators** (local super-admins and members of a group flagged "Administrator") have full access.
- A dashboard with **"All signed-in users"** visibility is visible to everyone. Its access rules then grant edit rights.
- A dashboard with **"Restricted"** visibility is only visible to the listed groups and users.
- A rule targets a group (local, LDAP or OIDC) or a single user, with **View** or **View + edit**. A user gets the highest right among their own rules and their groups' rules.
- Rights can be managed from three places:
  - **Admin › Dashboards**, the access column: visibility and rules of one dashboard;
  - **Admin › Groups › Dashboards**: every dashboard a group can view or edit;
  - **Admin › Users › Dashboards**: the user's own rules, and their **effective access** with the reason (administrator, everyone, group X, direct rule). Use it to see why someone sees a dashboard or not.
- **Declaring in advance**: LDAP / OIDC groups and accounts normally appear after a synchronisation or a first sign-in. To grant rights before that, declare them (Admin › Groups / Users › Declare…, or straight from the access window by typing the exact identifier):
  - LDAP group: its DN; OIDC group: the exact value of the groups claim (e.g. `/portal/staff` for a Keycloak group path, an object id for Entra ID);
  - LDAP account: the username attribute value; OIDC account: the username claim value. The OIDC account is linked at its first sign-in. Use a username claim that users cannot change themselves (not a self-editable `preferred_username`).
- LDAP groups are refreshed at each sign-in and by the manual synchronisation. OIDC groups are refreshed at each sign-in. Local groups assigned by hand are kept.
- An LDAP group that the synchronisation no longer finds is deleted, **except** when it carries dashboard rights or the Administrator flag: it is then kept (without members) and reported, so that a wrong filter does not wipe rights. Delete it by hand if it is gone for good.

### Local sign-in and break-glass access

Local accounts (including the super-admin) can be prevented from signing in, in Admin › Authentication › Local sign-in & sessions. This is only possible while LDAP or OpenID Connect is enabled. If both get disabled, local sign-in comes back automatically.

If the directory or the SSO is unavailable, re-enable local sign-in from the compose file:

```yaml
# docker-compose.yml, backend service
FORCE_LOCAL_LOGIN: "true"
```

```bash
docker compose up -d backend    # recreates the backend with the variable
```

Sign in with the local super-admin, fix the configuration, then set the variable back to `false`. While the variable is active, the admin panel shows a banner.

### Two-step verification

- Applies to local and LDAP accounts. OIDC accounts rely on the MFA of their identity provider.
- Users manage their methods from the user menu › **Security**. When MFA is required, users without a method set one up at their next sign-in, before getting access.
- Each account gets 10 single-use recovery codes. An admin can reset a user's methods (Admin › Users, shield button).
- TOTP QR codes are generated by the server (no external service). Codes are protected against replay and limited to 5 attempts per sign-in.
- WebAuthn is bound to the portal hostname: `PUBLIC_URL` must match the URL in the browser (the proxy's `https://` address).

### Migrating from Homer

In **Admin › Dashboards › Import from Homer**, select Homer's `assets` folder (the one containing `config.yml`), or pick files one by one, or paste a `config.yml`. Everything runs in your browser until you confirm, and nothing needs internet access.

- `config.yml` becomes a dashboard. Each additional Homer page (`page2.yml`…) becomes another dashboard, merged with `config.yml` the way Homer does it (colours, background and message are inherited). Homer page links such as `#page2` are rewritten to the new dashboards.
- Local images referenced by the configuration (item logos, header logo, `background-image`) are found in the selected files and uploaded to the portal. Only the images actually used are uploaded, once each. Remote image URLs are kept.
- A review screen shows, for each dashboard, the title, slug, visibility, images found or missing, and what could not be converted.
- Not converted (listed in the review): smart cards other than `Ping` (imported as simple links), `quick` links, custom stylesheets, remote messages (`message.url`), unsupported colours, and anything the portal refuses for security reasons (`javascript:` URLs, CSS injection). HTML in the title, message and footer is reduced to text.
- Homer's root `logo.png` sits next to `index.html`, outside `assets`. Add it to the selection with "Select files" if you want it imported.
- Imported dashboards are **restricted** by default: set their access rules afterwards.

### Status checks

The **backend** probes the URLs, not the browser. So it works for internal applications, honours the CAs from Admin › Certificates, and avoids CORS and mixed-content issues. Results: green for 2xx/3xx, orange for 4xx (reachable, for example asking for authentication), red for 5xx, timeouts and TLS errors. Results are cached (30 s by default) so many viewers don't multiply requests. Only `http(s)` URLs flagged by an editor are probed.

## Deployment with rootless Podman (quadlet)

[`example/podman/`](example/podman/) contains [quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) units: systemd manages the containers of an unprivileged user. The frontend publishes plain HTTP on `127.0.0.1:8080` for the reverse proxy of the host, typically nginx with [`example/nginx/portal-ng.conf`](example/nginx/portal-ng.conf). That also avoids the rootless limitation on ports below 1024. You need Podman ≥ 5.0 (for `Notify=healthy`) and an unprivileged user, here `portal`.

```bash
# As root: create the user and let its services run without an open session
sudo useradd -m portal
sudo loginctl enable-linger portal

# As the "portal" user (ssh portal@host or machinectl shell portal@)
git clone <this repository> ~/portal-ng && cd ~/portal-ng

# 1. Images
podman build -t localhost/portal-ng-backend:latest backend/
podman build -t localhost/portal-ng-frontend:latest frontend/

# 2. Secrets (never written in the unit files)
openssl rand -base64 32 | tr -d '\n' | podman secret create portal-ng-db-password -
# optional, otherwise generated in the data volume:
# openssl rand -base64 48 | tr -d '\n' | podman secret create portal-ng-secret-key -

# 3. Units: adapt PUBLIC_URL (the proxy's https:// address) / INITIAL_ADMIN_PASSWORD in portal-ng-backend.container
mkdir -p ~/.config/containers/systemd
cp example/podman/* ~/.config/containers/systemd/
systemctl --user daemon-reload

# 4. Start (the database, then the backend, then the frontend, each once healthy)
systemctl --user start portal-ng-frontend
systemctl --user status portal-ng-db portal-ng-backend portal-ng-frontend
journalctl --user -u portal-ng-backend    # admin password if INITIAL_ADMIN_PASSWORD is empty

# 5. Reverse proxy on the host (as root): see "nginx on the host" above
```

| Unit | Role |
|---|---|
| `portal-ng-internal.network` | Internal network (`Internal=true`, no outgoing access): database ↔ backend ↔ frontend |
| `portal-ng.network` | Network with outgoing access: backend (LDAP, OIDC, status checks) and frontend (published port) |
| `portal-ng-db.container` | PostgreSQL. Password from the `portal-ng-db-password` secret |
| `portal-ng-backend.container` | API. Builds its database URL from `POSTGRES_HOST` / `POSTGRES_USER` / `POSTGRES_DB` + the secret |
| `portal-ng-frontend.container` | nginx, plain HTTP published on `127.0.0.1:8080` |
| `*.volume` | `portal-ng-db`, `portal-ng-data` (master key, uploads) |

Notes:

- **Real client IP**: the image trusts `X-Forwarded-For` from loopback and private ranges. With rootless networking, check once that Admin › Logs shows your clients' addresses. If it shows the same address for everyone, that is the proxy as the container sees it: add it to `TRUSTED_PROXIES` in `portal-ng-frontend.container`.
- **Break-glass**: set `Environment=FORCE_LOCAL_LOGIN=true` in `portal-ng-backend.container`, then `systemctl --user daemon-reload && systemctl --user restart portal-ng-backend`.
- **Updates**: rebuild the images, then `systemctl --user restart portal-ng-backend portal-ng-frontend`.
- **Backups**: `podman volume export portal-ng-data > data.tar` and `podman exec portal-ng-db pg_dump -U portal portal > portal.sql`.

## Post-quantum cryptography

The application uses **no classical asymmetric cryptography** (RSA/ECC) for its own secrets. It relies on symmetric and hash-based primitives, against which a quantum computer only gains a quadratic speed-up (Grover), absorbed by 256-bit keys and digests.

| Use | Algorithm |
|---|---|
| Browser ↔ reverse proxy | TLS 1.3, hybrid key exchange **X25519MLKEM768** (ML-KEM-768, FIPS 203) with the provided examples: nginx with OpenSSL ≥ 3.5, Traefik ≥ 3 (Go ≥ 1.24). Same in the optional built-in TLS mode |
| Reverse proxy → frontend | Plain HTTP on the same host: loopback `127.0.0.1` or a Docker network, never the LAN |
| Backend → LDAPS / IdP / status checks | OpenSSL 3.5: X25519MLKEM768 offered by default, used when the remote server supports it |
| Local passwords | Argon2id (RFC 9106), 64 MiB, t=3, p=4, automatic rehash |
| Session, CSRF, MFA challenge tokens, recovery codes | 256-bit (80-bit for recovery codes) random values. Only SHA3-256 digests are stored |
| Secrets at rest (LDAP bind password, OIDC client secret, TOTP secrets) | AES-256-GCM, key derived from the master key with HKDF-SHA3-512 |
| TOTP | HMAC (RFC 6238), 160-bit secrets: symmetric, not affected by Shor's algorithm |

Limits outside the application's control:

- **The reverse proxy decides the TLS key exchange.** An nginx linked to OpenSSL < 3.5 or an old Traefik only offers X25519 (secure today, not post-quantum). Check below.
- **Certificate signatures** (TLS, internal PKI): browsers do not accept ML-DSA certificates yet, so certificates stay ECDSA/RSA. The ML-KEM key exchange already protects confidentiality against "harvest now, decrypt later"; server authentication remains classical.
- **WebAuthn**: security keys and passkeys sign with ES256 / EdDSA / RS256. No authenticator supports ML-DSA yet. WebAuthn is always a second factor on top of the password, and it remains resistant to phishing.
- **OIDC ID tokens** are signed by the IdP (RS256/ES256…). They are fetched directly from the IdP over TLS and their signature is verified. `none` and `HS*` are refused.

Check the key exchange negotiated by your proxy (OpenSSL ≥ 3.5 on the client side):

```bash
echo | openssl s_client -connect portal.example.com:443 2>/dev/null | grep Negotiated
# Negotiated TLS1.3 group: X25519MLKEM768
```

## Other security measures

- Session cookie `HttpOnly`, `SameSite=Lax`, and `Secure` behind HTTPS. A CSRF token is required on every state-changing request.
- Sign-in throttling: 10 failures per (IP, username) and 50 per IP over 15 minutes. Constant response time for unknown users.
- LDAP: filter escaping, empty passwords refused (no anonymous bind), warning for plaintext connections.
- OIDC: `state` bound to the browser with a cookie, `nonce`, PKCE S256, single-use `state` valid for 10 minutes.
- Dashboard content (editable by non-admins): `javascript:`, `data:`, `vbscript:` and `file:` URLs refused; colours, icon classes and image URLs validated against CSS/HTML injection; status URLs limited to `http(s)`.
- Trusted CAs: only CA certificates (basic constraints) that are not expired are accepted.
- Uploads: type detected from magic bytes, random names, served with `CSP: sandbox`.
- Headers sent by the frontend on every response: strict CSP (no external or inline scripts), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. HSTS is added by the proxy.
- Plain HTTP port published on `127.0.0.1` only; real client IP accepted only from `TRUSTED_PROXIES`.

## Local development

```bash
# Backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATA_DIR=./data DATABASE_URL=postgresql+psycopg://portal:portal@localhost:5432/portal
uvicorn app.main:app --reload

# Frontend (proxies /api to http://localhost:8000)
cd frontend && npm install && npm run dev
```

## Operations

- Data: `db-data` (PostgreSQL) and `app-data` (master key, logos and backgrounds). Certificates live on the reverse proxy.
- Log retention: configurable in Admin › Branding (90 days by default). The purge runs every 6 hours.
- The database schema is created at startup (`create_all`; new tables are added automatically). Add Alembic before changing existing columns in production.
- **Upgrading from a version where the frontend handled TLS**: the frontend now serves HTTP on `127.0.0.1:8080` and no longer uses the `certs` volume. Put a reverse proxy in front, or enable the built-in TLS mode. The old volume can be removed: `docker volume rm portal-ng_certs`.
