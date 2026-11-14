# Architecture

[Documentation](README.md) · [Portal-NG](../README.md)

## Three containers

```
                    ┌──────────── egress network ────────────┐
                    │                                        │
browser ──▶ frontend (nginx, uid 101) ──▶ backend (uid 10001) ──▶ LDAP / OIDC / probed applications
            :8080, plain HTTP              :8000, FastAPI
                    │                              │
                    └──── internal network ────────┴──▶ db (PostgreSQL 17, uid 70)
                              (no outgoing access)
```

- **frontend** — nginx as an unprivileged account, serving the built Vue application and proxying
  `/api/` to the backend. It is the only container with a published port, and it publishes plain HTTP on
  `127.0.0.1` by default. It sends the security headers and resolves the real client IP from
  `X-Forwarded-For`.
- **backend** — FastAPI with SQLAlchemy, on Alpine. It holds every decision: who may see what, what the
  branding is, and it is what probes the applications whose status is checked. Alpine is not only for the
  size: its OpenSSL 3.5 is what gives the outgoing connections their post-quantum key exchange.
- **db** — PostgreSQL, on the internal network only. It has no published port and no route to the outside.

The `internal` network is `internal: true`: the database cannot reach, and cannot be reached from,
anything outside the project. Only the backend and the frontend also sit on the `egress` network, because
the backend has to reach your directory, your identity provider and the applications it probes.

Hardening is the same for all three: a non-root user, a read-only root filesystem, every Linux capability
dropped, and `no-new-privileges`. The details are in [Security](security.md#the-containers).

## Where each piece of data lives

| What | Where | Backed up by |
|---|---|---|
| Dashboards, users, groups, rights, settings, logs | PostgreSQL | `db-data` volume, or `pg_dump` |
| The master key (`secret_key`) | `/data/secret_key` in the backend | `app-data` volume |
| Uploaded images (logos, backgrounds) | `/data/uploads/` in the backend | `app-data` volume |
| LDAP and OIDC secrets, TOTP secrets | PostgreSQL, **encrypted** with a key derived from the master key | both — one is useless without the other |
| TLS certificates | On the reverse proxy, never in Portal-NG | your proxy's configuration |

Which is why both volumes have to be backed up together: `db-data` alone cannot be decrypted without the
master key in `app-data`. See [Operations](operations.md#backups).

## A request, end to end

1. The browser asks the frontend for `/`. nginx serves `index.html` and the hashed assets; nothing is
   fetched from the internet, including the icons and the fonts.
2. The application asks `/api/public/config` — the branding and which sign-in methods are enabled. That is
   the only endpoint that answers without a session.
3. The user signs in. Local accounts are checked with Argon2id; LDAP binds against the directory; OIDC
   goes through the authorization code flow with PKCE. If two-step verification applies, a second
   challenge follows.
4. The session cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` behind HTTPS. Every state-changing
   request also carries a CSRF token.
5. `/api/dashboards` returns only what this user may see, computed from their own rules and their groups'.
6. The cards render. If a card has a status check, the browser asks the backend, which probes the
   application itself and caches the result (30 s by default) so a hundred viewers do not make a hundred
   requests.

## The repository

```
.
├── docker-compose.yml        # db (PostgreSQL 17) + backend + frontend
├── .env.example              # optional overrides
├── Makefile                  # the usual tasks; every target is one command
├── backend/                  # Python API (FastAPI, SQLAlchemy)
│   └── app/
│       ├── routers/          # auth, account (MFA), dashboards, status, admin, logs, public
│       └── services/         # ldap, oidc, mfa, trust (CAs), identity, settings, audit, images
├── frontend/                 # Vue 3 + Vite, built and served by unprivileged nginx (plain HTTP)
│   ├── public/               # the bundled logo and favicon
│   ├── docker/               # the nginx configuration and its templates
│   └── src/
│       ├── views/            # the pages, including views/admin/
│       └── components/       # the editor's building blocks, the modals, the image and icon fields
├── docs/                     # this documentation
├── scripts/                  # dockerhub-description.sh
└── example/
    ├── nginx/                # nginx on the host in front of Portal-NG (TLS, admin IP allow-list)
    ├── traefik/              # Traefik in front of Portal-NG (file provider or labels)
    ├── pki/                  # a demo internal PKI (CA + server certificate) for the examples
    └── podman/               # rootless Podman Quadlet units
```

## Choices worth knowing about

- **The schema is created at startup** (`create_all`), and new tables are added automatically. There is no
  migration tool yet, so a change to an existing column needs one to be added first — see
  [Operations](operations.md#the-database-schema).
- **The backend probes, not the browser.** It costs a round trip, and it is what makes status checks work
  for internal applications without CORS or mixed-content problems, and with your own certificate
  authorities.
- **Uploaded images are re-encoded on the way in**, not resized on the way out. There is no thumbnailing
  service and no cache to invalidate: what is stored is what is served, with a one-year immutable
  `Cache-Control` because the names are random and never reused.
- **No asymmetric cryptography of its own.** Sessions, CSRF tokens and recovery codes are random values
  stored only as SHA3-256 digests; secrets at rest are AES-256-GCM. See
  [Security](security.md#post-quantum-cryptography).
