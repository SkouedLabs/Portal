# Changelog

Notable changes to Portal-NG. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).

A release is a git tag (`v1.2.0`). The tag is stamped into the backend image and is what
`GET /api/health` reports; an image built from a checkout reports `dev`.

## [Unreleased]

### Added

- **A default logo.** Portal-NG now ships with its own logo and favicon
  (`frontend/public/logo.png`, `favicon.png`, `apple-touch-icon.png`), used by the header, the sign-in
  page and the browser tab whenever the branding defines none. The icon placeholders that stood in for a
  missing logo are gone. Setting a logo in Admin › Branding still overrides it; clearing the field now
  returns to the bundled one rather than to nothing.
- **Uploaded images are scaled down and re-encoded** (`backend/app/services/images.py`). Every raster
  upload is decoded, bounded to the size it will actually be drawn at — 512 px for a logo or a card image,
  2560 px for a page background — and re-encoded to WebP, once, on the way in. A 2.5 MB PNG logo becomes
  about 35 KB; a 6 MB photographic background about 250 KB. The upload field reports what it saved.
  SVG, ICO and animated images are stored untouched, as is anything that would come out bigger — except
  JPEG, which is re-encoded regardless, because that is what drops the EXIF block and with it the GPS
  coordinates of where the photograph was taken. An image the server cannot decode is stored as it
  arrived, exactly as before. See [Branding](docs/branding.md#images-and-how-they-are-stored).
- **A version in `GET /api/health`**, stamped into the image at build time from the git tag.
- **Continuous integration** ([`ci.yml`](.github/workflows/ci.yml)): the frontend tests and build, a
  backend check that builds the OpenAPI schema and exercises the image pipeline, both image builds, and a
  run that starts the real compose file and verifies the stack answers — failing on a traceback in the
  backend log even when the endpoints answered.
- **Published images** ([`publish.yml`](.github/workflows/publish.yml)): `skouedlabs/portal-ng-backend`
  and `skouedlabs/portal-ng-frontend` on Docker Hub, and the same builds with the same digests on
  `ghcr.io/skouedlabs/`. A push to `dev` publishes `dev` and `dev-<sha>`; a `v*` tag publishes the
  version, the major.minor, and `latest`. Merging into `main` publishes nothing.
- **A test suite**, in `frontend/test/` (`npm test`, `make test`), covering the Homer import/export
  round-trip and the routing. No framework: esbuild bundles each case so the application's own imports
  resolve the way Vite resolves them, and jsdom stands in for the browser. It is what made the
  dependency majors below safe to take — it caught js-yaml dropping its default export.
- **Project documentation** split into [`docs/`](docs/README.md), one page per subject, with the README
  reduced to what a newcomer needs in the first five minutes.
- **The usual project files**: [LICENSE](LICENSE) (Apache 2.0), [NOTICE](NOTICE),
  [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
  [SECURITY.md](SECURITY.md), this changelog, a [Makefile](Makefile), an `.editorconfig`, issue and pull
  request templates, and Dependabot.

### Changed

- **The backend image is Alpine**, 255 MB instead of 364 MB. Alpine 3.24 carries OpenSSL 3.5.9 — newer
  than Debian trixie's 3.5.7 — and was checked to negotiate X25519MLKEM768 against a server offering it,
  so the post-quantum key exchange on outgoing connections is unchanged. Python dependencies install from
  musl wheels only (`--only-binary`), so no compiler is ever present in the image. All three containers
  are now Alpine-based.
- **Dependencies brought up to date.** Backend: Python 3.13 → 3.14, and the floors raised to the versions
  actually built against (FastAPI 0.162, SQLAlchemy 2.0.57, Pillow 13, cryptography 50, pydantic 2.14,
  psycopg 3.3, webauthn 3). Frontend: Node 22 → 24, Vite 6 → 8, `@vitejs/plugin-vue` 5 → 6, vue-router
  4 → 5, js-yaml 4 → 5, Font Awesome 6 → 7, nginx-unprivileged 1.29 → 1.30. PostgreSQL stays on 17: a
  major there would need `pg_upgrade` on existing data, which is not something a rebuild should do.
- **js-yaml 5 removed its default export**, so `src/homerYaml.js` and `vite.config.js` now use named
  imports. The Homer round-trip test covers this.
- **GitHub Actions brought up to date** (`checkout` v4 → v7, `setup-node` v4 → v7, `setup-python` v5 → v7,
  `login-action` v3 → v4, `setup-buildx-action` v3 → v4, `metadata-action` v5 → v6, `build-push-action`
  v6 → v7), which also clears the Node 20 deprecation warnings on every run. The runner is pinned to
  `ubuntu-24.04` rather than `ubuntu-latest`, so the migration to Ubuntu 26 is a decision rather than a
  surprise in the middle of a release.
- **The repository moved to `SkouedLabs/Portal`**, and the images to the `skouedlabs` namespace, from
  `emeryn`. The compose file and the Quadlet units point at `skouedlabs/portal-ng-backend` and
  `skouedlabs/portal-ng-frontend`; set `PORTAL_NG_IMAGE_NAMESPACE` to pull from somewhere else, and
  `PORTAL_NG_VERSION` to pin a release instead of `latest`.
- **`docker compose up -d` now pulls rather than builds.** Add `--build` to build from the checkout, which
  is what [Development](docs/development.md) does.
- **`MAX_UPLOAD_MB` default raised from 5 to 10**, and nginx's `client_max_body_size` from 8 MB to 16 MB
  so the backend is what returns a readable `413`. The limit is on what is *sent*: what is stored is a
  fraction of it now that uploads are re-encoded.
- The bundled logo and favicon are served with a one-day `Cache-Control` instead of `no-cache`; they only
  change with an upgrade.

### Removed

- `frontend/public/favicon.svg`, replaced by the logo-derived `favicon.png`.
