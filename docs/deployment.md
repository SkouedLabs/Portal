# Deployment

[Documentation](README.md) · [Portal-NG](../README.md)

```
browser ──HTTPS (TLS 1.3, X25519MLKEM768)──▶ reverse proxy ──HTTP, local──▶ frontend :8080 ──▶ backend ──▶ db
                                             nginx on the host  127.0.0.1    (non-root nginx)
                                             or Traefik         Docker net.
                                             • certificate, HSTS
                                             • /admin + /api/admin/ IP allow-list
```

Portal-NG holds no certificate. The proxy terminates TLS and forwards plain HTTP to the frontend, either
over the host loopback (`127.0.0.1:8080`) or over a Docker network. The frontend:

- sends its own security headers (CSP, `X-Frame-Options`, `nosniff`…); the proxy adds HSTS;
- takes the **real client IP** from `X-Forwarded-For`, but only from `TRUSTED_PROXIES` (default: loopback
  and private ranges, consistent with a port published on `127.0.0.1`). That IP is the one in the logs and
  in the sign-in throttling.

| Variable | Default | Role |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | The address users type: `https://portal.example.com` behind the proxy |
| `HTTP_BIND` / `HTTP_PORT` | `127.0.0.1` / `8080` | The published HTTP port. Use `0.0.0.0` only if the proxy runs on another machine, and then restrict `TRUSTED_PROXIES` to it |
| `TRUSTED_PROXIES` | loopback and private ranges | Who may set `X-Forwarded-For` |
| `COOKIE_SECURE` | empty = automatic | `Secure` cookies when `PUBLIC_URL` is `https://` |

Every variable is in [Configuration](configuration.md).

## nginx on the host

[`example/nginx/portal-ng.conf`](../example/nginx/portal-ng.conf) proxies to `127.0.0.1:8080`. It provides
TLS 1.3 with X25519MLKEM768 (OpenSSL ≥ 3.5 on the host), an HTTP→HTTPS redirect, HSTS, and an IP
allow-list on the administration ([`admin-allow.conf`](../example/nginx/admin-allow.conf)).

```bash
sudo cp example/nginx/portal-ng.conf /etc/nginx/conf.d/
sudo cp example/nginx/admin-allow.conf /etc/nginx/snippets/portal-ng-admin-allow.conf
# certificate: /etc/nginx/ssl/portal.crt + portal.key (your PKI, or example/pki/gen-certs.sh for a demo)
sudo nginx -t && sudo systemctl reload nginx
```

## Traefik

- **Traefik in the same compose project** ([`example/traefik/compose.yml`](../example/traefik/compose.yml)):
  the file provider (no Docker socket mounted), non-root, read-only. TLS 1.3, an HTTP→HTTPS redirect, HSTS
  and an IP allow-list on the administration. Traefik ≥ 3.x (Go ≥ 1.24) negotiates X25519MLKEM768 by
  default.

  ```bash
  sh example/pki/gen-certs.sh portal.example.internal   # or your own portal.crt / portal.key in example/pki/certs
  PUBLIC_URL=https://portal.example.internal \
    docker compose -f docker-compose.yml -f example/traefik/compose.yml up -d
  ```

- **An existing Traefik with the Docker provider**
  ([`example/traefik/compose.labels.yml`](../example/traefik/compose.labels.yml)): labels on the frontend,
  joined to your external `traefik` network.

Both are detailed in [`example/README.md`](../example/README.md).

## The IP allow-list on the administration

Both examples filter **`/admin`** (the interface route) **and `/api/admin/`** (the API). The interface
route alone would protect nothing, since the protection that matters is on the API.

Tested with the allow-list in deny mode: 17 path-manipulation variants (`//api/admin`, `/api/./admin`,
`/api/x/../admin`, `/api/%61dmin`, `/api%2Fadmin`, `;`, `%2e%2e`…) are all refused (403/400) by both nginx
and Traefik. The Traefik example also rejects ambiguous encodings and header aliases.

## Built-in TLS, without a reverse proxy

For a test or a small deployment, the frontend can terminate TLS itself: TLS 1.3, X25519MLKEM768, HSTS,
an HTTP→HTTPS redirect, and a self-signed certificate generated if none is provided. A
`docker-compose.override.yml`:

```yaml
services:
  frontend:
    environment:
      FRONTEND_TLS: "true"
      HTTPS_PUBLIC_PORT: "8443"          # the port used in the HTTP->HTTPS redirect
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

## Rootless Podman (Quadlet)

[`example/podman/`](../example/podman/) contains
[Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) units: systemd manages the
containers of an unprivileged user. The frontend publishes plain HTTP on `127.0.0.1:8080` for the reverse
proxy of the host, which also avoids the rootless limitation on ports below 1024. You need Podman ≥ 5.0
(for `Notify=healthy`) and an unprivileged user, here `portal`.

```bash
# As root: create the user and let its services run without an open session
sudo useradd -m portal
sudo loginctl enable-linger portal

# As the "portal" user (ssh portal@host, or machinectl shell portal@)
git clone https://github.com/SkouedLabs/Portal.git ~/portal-ng && cd ~/portal-ng

# 1. Images - the units name the published ones, so this is a pull
podman pull docker.io/skouedlabs/portal-ng-backend:latest
podman pull docker.io/skouedlabs/portal-ng-frontend:latest
#    ...or build them from the checkout under the same names:
#    podman build -t docker.io/skouedlabs/portal-ng-backend:latest backend/

# 2. Secrets (never written in the unit files)
openssl rand -base64 32 | tr -d "\n" | podman secret create portal-ng-db-password -
# optional, otherwise generated in the data volume:
# openssl rand -base64 48 | tr -d "\n" | podman secret create portal-ng-secret-key -

# 3. Units: set PUBLIC_URL (the proxy's https:// address) and INITIAL_ADMIN_PASSWORD
#    in portal-ng-backend.container
mkdir -p ~/.config/containers/systemd
cp example/podman/* ~/.config/containers/systemd/
systemctl --user daemon-reload

# 4. Start (the database, then the backend, then the frontend, each once healthy)
systemctl --user start portal-ng-frontend
systemctl --user status portal-ng-db portal-ng-backend portal-ng-frontend
journalctl --user -u portal-ng-backend    # the admin password, if INITIAL_ADMIN_PASSWORD is empty

# 5. The reverse proxy on the host (as root): see "nginx on the host" above
```

| Unit | Role |
|---|---|
| `portal-ng-internal.network` | Internal network (`Internal=true`, no outgoing access): database ↔ backend ↔ frontend |
| `portal-ng.network` | Network with outgoing access: the backend (LDAP, OIDC, status checks) and the frontend (published port) |
| `portal-ng-db.container` | PostgreSQL. The password comes from the `portal-ng-db-password` secret |
| `portal-ng-backend.container` | The API. Builds its database URL from `POSTGRES_HOST` / `POSTGRES_USER` / `POSTGRES_DB` plus the secret |
| `portal-ng-frontend.container` | nginx, plain HTTP published on `127.0.0.1:8080` |
| `*.volume` | `portal-ng-db`, `portal-ng-data` (the master key and the uploads) |

Notes:

- **The real client IP**: the image trusts `X-Forwarded-For` from loopback and private ranges. With
  rootless networking, check once that Admin › Logs shows your clients' addresses. If it shows the same
  address for everyone, that is the proxy as the container sees it: add it to `TRUSTED_PROXIES` in
  `portal-ng-frontend.container`.
- **Break-glass**: set `Environment=FORCE_LOCAL_LOGIN=true` in `portal-ng-backend.container`, then
  `systemctl --user daemon-reload && systemctl --user restart portal-ng-backend`. See
  [Users and rights](users-and-rights.md#local-sign-in-and-break-glass-access).
- **Updates**: `podman pull` the two images, then
  `systemctl --user restart portal-ng-backend portal-ng-frontend`.
- **Backups**: `podman volume export portal-ng-data > data.tar` and
  `podman exec portal-ng-db pg_dump -U portal portal > portal.sql`.
