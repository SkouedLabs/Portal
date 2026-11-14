# Development

[Documentation](README.md) · [Portal-NG](../README.md)

How to contribute — what a change should look like, and how it is reviewed — is in
[CONTRIBUTING.md](../CONTRIBUTING.md). This page is about getting the thing running on your machine.

## With Docker, which is the short way

```bash
docker compose up -d --build     # or: make up
docker compose logs -f backend   # or: make logs
```

Rebuild after a change: `docker compose up -d --build backend` (or `frontend`). `make` is a convenience,
never a requirement — every target is one command, visible in the [Makefile](../Makefile).

## On the host, for a fast loop

The frontend's dev server proxies `/api` to `http://localhost:8000`, so run the backend first.

```bash
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATA_DIR=./data DATABASE_URL=postgresql+psycopg://portal:portal@localhost:5432/portal
uvicorn app.main:app --reload

# Frontend, in another terminal
cd frontend && npm install && npm run dev
```

You still need a PostgreSQL to point at. The simplest is the one from the compose file:

```bash
docker compose up -d db
docker compose port db 5432      # publish it first if you want to reach it from the host
```

## The checks CI runs

Everything in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), on every pull request and before
every release:

| Job | What it proves |
|---|---|
| **Frontend tests and build** | `npm ci` against the lock file, then `npm test` and `npm run build`. |
| **Backend checks** | The application imports — every module, every router, every Pydantic model — and the image pipeline still scales down, re-encodes, and leaves SVG and unreadable files alone. |
| **Images build** | Both Dockerfiles build. |
| **The stack starts and answers** | `docker compose up --wait`, then the health endpoint, the public configuration, the built frontend, the bundled logo, and a sign-in attempt. It fails on a traceback in the backend log even if the endpoints answered. |

Run them locally:

```bash
make test         # the frontend test suite, in a node:24-alpine container
make typecheck    # builds the frontend in the same way
make smoke        # starts the stack and checks it answers, then tears it down
```

### The test suite

`frontend/test/` holds it, and `npm test` runs it. There is no framework: `test/run.mjs` uses esbuild to
bundle each case — which is what makes the application's own extensionless imports resolve the way Vite
resolves them — jsdom stands in for the browser, and a failed assertion is a non-zero exit.

| File | What it covers |
|---|---|
| `test/homer.mjs` | Parsing a Homer `config.yml`, finding its local images and what each one is for, converting it to a dashboard, exporting it back and re-parsing the result. |
| `test/router.mjs` | The guard from `src/router.js`: an anonymous visitor redirected to the sign-in page with `?next=`, a non-administrator bounced off `/admin`, nested routes, route params, the catch-all, `resolve()` and `replace()`. |

Both exist because they are what a dependency bump breaks: these cases caught js-yaml dropping its
default export, and they are what made a vue-router major safe to take.

On the **Python side there is no suite yet**, which is the honest state of this repository and a good
place to contribute. The backend job builds the OpenAPI schema — which runs every router and every model
— and exercises the image pipeline; the stack job starts the real compose file, which catches a bad
health check, an nginx template that does not render, or a read-only filesystem the application needs to
write to. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Conventions

- **English** in the code, the comments, the commit messages and the interface.
- Comments explain **why**, never what the line below already says, and never what changed — that is what
  the history is for.
- Python 3.13 with type hints; Vue 3 with `<script setup>` on the frontend.
- Authorization goes through the existing choke points in `app/deps.py`. A new endpoint does not invent
  its own rule about who may read a dashboard.
- Dependencies: `backend/requirements.txt` and `frontend/package-lock.json`, both in the commit.

## Releasing

Nothing in the source carries the version. A release is a tag:

```bash
git tag v1.2.0 && git push origin v1.2.0
```

[`publish.yml`](../.github/workflows/publish.yml) then runs the whole CI workflow as a gate, builds both
images, and pushes them to Docker Hub (`skouedlabs/portal-ng-*`) and GitHub Packages
(`ghcr.io/skouedlabs/portal-ng-*`) from a single build, so both registries carry the same digest. The tag
is stamped into the backend image and is what `/api/health` reports.

A push to `dev` publishes the `dev` tag and a `dev-<sha>` one. Merging into `main` publishes nothing: a
release is a deliberate act.

## Licence

Apache 2.0 — [LICENSE](../LICENSE), [NOTICE](../NOTICE). Source files carry no licence header; the
`LICENSE` file covers the whole repository. By opening a pull request you agree your contribution is
licensed under it. There is no CLA.
