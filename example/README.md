# Portal-NG examples

Portal-NG's frontend serves plain HTTP (`127.0.0.1:8080` by default) and leaves TLS to a reverse proxy.

| Folder | Content |
|---|---|
| [`nginx/`](nginx/) | nginx installed **on the host** in front of Portal-NG: TLS 1.3 + ML-KEM, HSTS, admin IP allow-list |
| [`traefik/`](traefik/) | Traefik in front of Portal-NG: in the same compose project (file provider), or an existing Traefik (labels) |
| [`pki/`](pki/) | Demo internal PKI: root CA + server certificate for the proxy |
| [`podman/`](podman/) | Quadlet units for rootless Podman under systemd (see the main README) |

All the configurations below have been tested, including with the allow-list in deny mode and path-manipulation attempts against the administration (`//api/admin`, `/api/%61dmin`, `/api%2Fadmin`, `..`, `;`…): all refused.

## Certificates (demo PKI)

```bash
sh example/pki/gen-certs.sh portal.example.internal
# without openssl locally:
docker run --rm -v "$PWD/example/pki:/w" -w /w alpine sh -c "apk add -q openssl && sh gen-certs.sh portal.example.internal"
```

| File | Use |
|---|---|
| `pki/certs/ca.crt` | Import it in your browsers / OS. Also in Portal-NG › Admin › Certificates if the backend must trust servers of this PKI |
| `pki/certs/portal.crt`, `portal.key` | Certificate of the reverse proxy |

With a real PKI (or ACME), use your own files. The CA key is only used by the script and never needs to be on the server. Add `portal.example.internal` to your DNS (or `/etc/hosts`).

On Windows, `curl` (Schannel) refuses the demo certificates with "revocation status is unknown" because they have no CRL endpoint: add `--ssl-no-revoke` for tests, or publish a CRL / OCSP in your real PKI.

## nginx on the host

```
browser ──HTTPS──▶ nginx (host) :443 ──HTTP──▶ 127.0.0.1:8080 (Portal-NG frontend container)
```

1. Portal-NG: keep the default compose (port on `127.0.0.1:8080`) and set `PUBLIC_URL=https://portal.example.internal`.
2. nginx:

   ```bash
   sudo cp example/nginx/portal-ng.conf /etc/nginx/conf.d/
   sudo mkdir -p /etc/nginx/snippets /etc/nginx/ssl
   sudo cp example/nginx/admin-allow.conf /etc/nginx/snippets/portal-ng-admin-allow.conf
   sudo cp example/pki/certs/portal.crt example/pki/certs/portal.key /etc/nginx/ssl/
   sudo chmod 600 /etc/nginx/ssl/portal.key
   sudo nginx -t && sudo systemctl reload nginx
   ```

3. Adapt `server_name` and the allow-list to your networks.

- **Post-quantum key exchange**: `ssl_ecdh_curve X25519MLKEM768:…` needs nginx linked to **OpenSSL ≥ 3.5** (Debian 13, Ubuntu 25.04+, RHEL 10, Alpine 3.22… check with `openssl version`). With an older OpenSSL, nginx refuses the line: use `X25519:secp384r1` (TLS 1.3 stays secure today, but without post-quantum key exchange).
- The allow-list file goes in `snippets/`, **not** `conf.d/`: nginx loads `conf.d/*.conf` at the `http` level, where a `deny all` would close the whole site.
- SELinux (RHEL family): allow nginx to connect to the local port with `sudo setsebool -P httpd_can_network_connect 1`.

## Traefik

### Traefik in the same compose project

```
browser ──HTTPS──▶ traefik :443 ──HTTP (Docker network)──▶ frontend:8080
```

```bash
PUBLIC_URL=https://portal.example.internal \
  docker compose -f docker-compose.yml -f example/traefik/compose.yml up -d --build
```

- [`traefik.yml`](traefik/traefik.yml) is the static configuration: entry points (Traefik listens on 8080/8443 as a non-root user, published as 80/443), HTTP→HTTPS redirect, file provider. It also rejects ambiguous path encodings and header aliases, so the admin allow-list can't be bypassed.
- [`dynamic/portal-ng.yml`](traefik/dynamic/portal-ng.yml) holds the routes, the admin allow-list (`ipAllowList`), HSTS, and the TLS 1.3 certificate. Edit `Host(...)` and `sourceRange` there.
- No Docker socket is mounted (it is equivalent to root on the host). Traefik runs as uid 65532, read-only, with no capabilities. The certificate key must be readable by that user (the demo script makes it so).
- Traefik ≥ 3 (Go ≥ 1.24) offers X25519MLKEM768 by default: no `curvePreferences` needed. Tested with Traefik 3.7.
- Traefik reloads `dynamic/` automatically on Linux. With Docker Desktop on Windows/macOS, file changes in bind mounts are not always detected: `docker compose restart traefik`.
- For ACME / Let's Encrypt, add a `certificatesResolvers` section to `traefik.yml` and reference it in the routers instead of the static certificate.

### Existing Traefik (Docker provider, labels)

If you already run Traefik with the Docker provider and an external network named `traefik`:

```bash
PUBLIC_URL=https://portal.example.internal \
  docker compose -f docker-compose.yml -f example/traefik/compose.labels.yml up -d --build
```

[`compose.labels.yml`](traefik/compose.labels.yml) attaches the frontend to that network with the router, HSTS and admin allow-list labels. Adapt the hostname, the entry point (`websecure`) and the certificate resolver to your Traefik.

## Trusting the internal CA inside Portal-NG

For the backend to reach internal servers signed by the same PKI (LDAPS directory, OIDC provider, status checks of internal applications), import `pki/certs/ca.crt` in **Admin › Certificates**. That page also has a "Test a TLS connection" tool.
