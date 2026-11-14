# Operations

[Documentation](README.md) · [Portal-NG](../README.md)

## The volumes

| Volume | What is in it |
|---|---|
| `db-data` | PostgreSQL: dashboards, users, groups, rights, settings, logs. The LDAP/OIDC and TOTP secrets, **encrypted**. |
| `app-data` | The master key (`/data/secret_key`) and the uploaded images (`/data/uploads/`). |

Certificates are not here: they live on the reverse proxy.

## Backups

**Both volumes, together.** `db-data` on its own cannot be decrypted: the secrets it holds are encrypted
with a key derived from the master key in `app-data`.

```bash
# Database
docker compose exec -T db pg_dump -U portal portal > portal-$(date +%F).sql

# Master key and uploads
docker run --rm -v portal-ng_app-data:/data -v "$PWD:/out" alpine \
  tar czf /out/app-data-$(date +%F).tar.gz -C /data .
```

Restoring is the same two steps in reverse: restore `app-data` **first**, then load the dump into a
database created by a started stack.

With Podman: `podman volume export portal-ng-data > data.tar` and
`podman exec portal-ng-db pg_dump -U portal portal > portal.sql`.

Test a restore before you need one. A backup of `db-data` without `app-data` looks fine right up to the
moment someone tries to sign in through LDAP.

## Upgrading

```bash
docker compose pull      # or: docker compose build --pull, to build from the checkout
docker compose up -d
```

The schema is created and extended at startup, so there is no migration step. Both volumes are kept. Pin
`PORTAL_NG_VERSION` to a release in production so that an upgrade is something you decide rather than
something that happens.

The version actually running is reported by the backend:

```bash
curl -s http://127.0.0.1:8080/api/health
# {"status":"ok","version":"1.2.0"}
```

It says `dev` for an image built from a checkout — there is nothing to bump in the source, the git tag is
the release. What a given upgrade needs is in the [changelog](../CHANGELOG.md).

### Coming from a version where the frontend handled TLS

The frontend now serves plain HTTP on `127.0.0.1:8080` and no longer uses the `certs` volume. Put a
reverse proxy in front, or enable the [built-in TLS
mode](deployment.md#built-in-tls-without-a-reverse-proxy). The old volume can be removed:

```bash
docker volume rm portal-ng_certs
```

## The database schema

The schema is created at startup with `create_all`, and **new tables and new models are added
automatically**. What it does *not* do is alter an existing column. Adding Alembic is the prerequisite for
any such change in production — until then, a column that has to change needs a migration path written by
hand, and the [changelog](../CHANGELOG.md) will say so.

## Log retention

Configured in **Admin › Branding**: 90 days by default, with the purge running every 6 hours. What is
recorded, and what can be turned off, is in [Logs](monitoring.md#retention-and-what-gets-logged).

## Routine checks

- `docker compose ps` — all three healthy. The backend's health check is `/api/health` and touches no
  database, so it reports the process, not the stack.
- `docker compose logs backend` — warnings worth acting on: the default administrator password still in
  use, a plaintext LDAP connection, an upload that could not be re-encoded.
- **Admin › Logs**, filtered on authentication failures.
- **Admin › Users**, the effective access column, after any change to an LDAP filter — an LDAP group that
  the synchronisation stops finding is kept when it carries rights, and reported rather than deleted.
- The size of `app-data` if many backgrounds get uploaded. Images are
  [re-encoded](branding.md#images-and-how-they-are-stored) on the way in, so this grows slowly, but
  replaced images are not deleted: a background swapped ten times leaves ten files.
