# Security

[Documentation](README.md) · [Portal-NG](../README.md)

What the application does on its own, and what is left to you. To **report a vulnerability**, see
[SECURITY.md](../SECURITY.md) — please do not open a public issue.

## The containers

| Container | User | Root filesystem | Capabilities |
|---|---|---|---|
| `db` (PostgreSQL) | `70:70` (postgres), from the start — no root entrypoint | read-only (+ tmpfs `/tmp`, `/var/run/postgresql`) | none |
| `backend` | `10001:10001` (portal) | read-only (+ tmpfs `/tmp`) | none |
| `frontend` | `101:101` (nginx-unprivileged: no root master process, port 8080) | read-only (+ tmpfs `/tmp`) | none |
| `traefik` (example) | `65532:65532`, ports 8080/8443 inside, published as 80/443 | read-only | none |

All of them also run with `no-new-privileges`. The Quadlet units in `example/podman/` apply the same
settings (`User=`, `ReadOnly=`, `DropCapability=all`, `NoNewPrivileges=`).

Files you mount have to be readable by these users — certificates for the Traefik example (uid 65532), or
for the built-in TLS mode (uid 101).

The database sits on a network declared `internal: true`: no published port, and no route to or from
anything outside the project. See [Architecture](architecture.md#three-containers).

## Sessions and the sign-in

- Session cookie `HttpOnly`, `SameSite=Lax`, and `Secure` behind HTTPS. A **CSRF token** is required on
  every state-changing request.
- Sign-in throttling: 10 failures per (IP, username) and 50 per IP over 15 minutes. Constant response time
  for unknown users.
- Passwords: **Argon2id** (RFC 9106, 64 MiB, t=3, p=4), rehashed automatically.
- Session, CSRF, MFA challenge tokens and recovery codes are random values; only their **SHA3-256
  digests** are stored.

More, including two-step verification and the break-glass switch, in
[Users and rights](users-and-rights.md).

## Content written by your users

Dashboards are editable by people who are not administrators, so their content is validated as untrusted
input:

- `javascript:`, `data:`, `vbscript:` and `file:` URLs are refused;
- colours, icon classes and image URLs are validated against CSS and HTML injection;
- status check URLs are limited to `http(s)`.

## Uploads

- The format is detected from the **magic bytes**, never from the file name or the `Content-Type` the
  browser claims.
- Files are stored under **random names**, so one upload cannot overwrite or guess another.
- Raster images are **decoded and re-encoded** before being stored. Beyond making pages lighter, this
  drops the metadata — including the **GPS coordinates** in the EXIF of a photograph — and caps the
  dimensions, so a decompression bomb is refused rather than expanded. See
  [Branding](branding.md#images-and-how-they-are-stored).
- They are served with `X-Content-Type-Options: nosniff` and
  `Content-Security-Policy: default-src 'none'; sandbox`, so an SVG opened directly cannot run a script.
- The size of what may be sent is `MAX_UPLOAD_MB` (10 MB by default).

## Headers

The frontend sends, on every response: a strict **CSP** (no external and no inline script),
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy` and
`Cross-Origin-Opener-Policy`. **HSTS is added by your reverse proxy**, which is the only component that
knows it is serving HTTPS.

The plain HTTP port is published on `127.0.0.1` only, and the real client IP is accepted only from
`TRUSTED_PROXIES`.

## Trusted certificate authorities

**Admin › Certificates** imports your internal root and intermediate CAs, used by the backend for LDAPS,
the OIDC provider and the status checks. A **TLS connection tester** says what a host presents before you
rely on it.

Only CA certificates (with the right basic constraints) that have not expired are accepted.

## Post-quantum cryptography

The application uses **no classical asymmetric cryptography** (RSA/ECC) for its own secrets. It relies on
symmetric and hash-based primitives, against which a quantum computer only gains a quadratic speed-up
(Grover), absorbed by 256-bit keys and digests.

| Use | Algorithm |
|---|---|
| Browser ↔ reverse proxy | TLS 1.3, hybrid key exchange **X25519MLKEM768** (ML-KEM-768, FIPS 203) with the provided examples: nginx with OpenSSL ≥ 3.5, Traefik ≥ 3 (Go ≥ 1.24). Same in the optional built-in TLS mode |
| Reverse proxy → frontend | Plain HTTP on the same host: loopback `127.0.0.1` or a Docker network, never the LAN |
| Backend → LDAPS / IdP / status checks | OpenSSL 3.5: X25519MLKEM768 offered by default, used when the remote server supports it |
| Local passwords | Argon2id (RFC 9106), 64 MiB, t=3, p=4, automatic rehash |
| Session, CSRF, MFA challenge tokens, recovery codes | 256-bit random values (80-bit for recovery codes). Only SHA3-256 digests are stored |
| Secrets at rest (LDAP bind password, OIDC client secret, TOTP secrets) | AES-256-GCM, key derived from the master key with HKDF-SHA3-512 |
| TOTP | HMAC (RFC 6238), 160-bit secrets: symmetric, unaffected by Shor's algorithm |

Limits outside the application's control:

- **The reverse proxy decides the TLS key exchange.** An nginx linked against OpenSSL < 3.5, or an old
  Traefik, only offers X25519 — secure today, not post-quantum.
- **Certificate signatures** (TLS, internal PKI): browsers do not accept ML-DSA certificates yet, so
  certificates stay ECDSA/RSA. The ML-KEM key exchange already protects confidentiality against "harvest
  now, decrypt later"; server authentication remains classical.
- **WebAuthn**: security keys and passkeys sign with ES256 / EdDSA / RS256. No authenticator supports
  ML-DSA yet. WebAuthn is always a second factor on top of a password, and it remains resistant to
  phishing.
- **OIDC ID tokens** are signed by the provider (RS256/ES256…). They are fetched directly from it over
  TLS and verified; `none` and `HS*` are refused.

Check what your proxy negotiates (OpenSSL ≥ 3.5 on the client side):

```bash
echo | openssl s_client -connect portal.example.com:443 2>/dev/null | grep Negotiated
# Negotiated TLS1.3 group: X25519MLKEM768
```

## What is left to you

- **TLS, HSTS and the certificate** — on the reverse proxy. Portal-NG holds no certificate.
- **The IP allow-list on the administration** — the examples do `/admin` *and* `/api/admin/`; see
  [Deployment](deployment.md#the-ip-allow-list-on-the-administration).
- **The database password and the master key** — set before the first start, and backed up. See the
  [production checklist](install.md#production-checklist).
- **Who gets the admin role.** An administrator decides what every dashboard shows and points the status
  checks at arbitrary addresses, which makes the server reach them. That is the job, not a vulnerability.
