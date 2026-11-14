# Contributing to Portal-NG

Thanks for taking the time. This file is short on purpose: it says what you need to run the project, what
a change is expected to look like, and how it gets reviewed.

## Before you write code

- **A bug**: open an issue with what you did, what happened and what you expected. The version
  (`GET /api/health`) and the relevant log lines help more than anything else.
- **A feature**: open an issue first and say what problem it solves. Portal-NG deliberately stays close to
  what a company portal needs, and the cheapest change is the one that turns out to be unnecessary.
- **A security issue**: do not open an issue. See [SECURITY.md](SECURITY.md).

Small, obvious fixes (a typo, a wrong link, an off-by-one in a message) need no issue — send the pull
request.

## Running it

Docker is the only prerequisite; nothing is installed on the host.

```bash
docker compose up -d --build     # or: make up      -> http://localhost:8080
make typecheck                   # build the frontend
make smoke                       # start the stack and check that it answers
```

Running the backend or the frontend directly on your machine is described in
[Development](docs/development.md).

## What a change should look like

- **Keep the diff about one thing.** Reformatting, renaming and fixing in one pull request makes the
  change impossible to review.
- **Match the surrounding code.** Same naming, same comment density, same idiom. Comments explain *why*,
  never what the line below already says, and never what changed — that is what the history is for.
- **English** in the code, the comments, the commit messages and the interface.
- **Type hints** on the Python side (the code is written for Python 3.13). Vue 3 with `<script setup>` on
  the frontend; `make typecheck` must pass.
- **Authorization goes through the existing choke points.** `app/deps.py` decides who may read or edit a
  dashboard, and nothing bypasses it — not a new endpoint, not a background job. If you need a new kind of
  restriction, add it there rather than in a caller.
- **Dashboard content is untrusted input.** It is editable by people who are not administrators, so a new
  field that ends up in the page is validated like any other — see
  [Security](docs/security.md#content-written-by-your-users).
- **The schema is created with `create_all`.** A new table or a new model is picked up on the next start;
  **changing an existing column is not**, and needs a migration path, which this project does not have
  yet. Say so in the pull request if your change needs one.
- **Dependencies.** `backend/requirements.txt` and `frontend/package-lock.json`, both in the commit, both
  as small as you can keep them. A portal that works offline cannot afford a dependency that phones home.

## Tests

There is **no unit test suite yet** — that is the honest state of this repository, and it is a good place
to contribute. In the meantime, CI starts the real compose file and checks that the stack answers, which
is what catches most of what breaks here.

If you add behaviour that can be tested without a browser — the image pipeline, the Homer conversion, the
rights computation — adding the test with it is very welcome, and starting the suite is more welcome
still.

Whatever you change, say in the pull request **what you did in the running application** to check it.

## Documentation

A feature that is not documented does not exist for the person who has to operate it. A change that adds
or alters behaviour updates, as needed:

- the page in **[docs/](docs/README.md)** that covers the subject — one page per subject, and the
  [index](docs/README.md) lists them;
- the **[README](README.md)**, only if the change is something a newcomer has to know in the first five
  minutes;
- the docstring at the top of the module, when the change is about *how* something works.

## Pull requests

- Branch off `main`, one subject per branch.
- Say in the description what the change does and why, and how you checked it.
- CI runs the frontend build, the backend checks, both image builds and the stack check on every push.
  Keep it green.
- By opening a pull request you agree that your contribution is licensed under the
  [Apache License 2.0](LICENSE), like the rest of the project. There is no CLA.

Source files carry no licence header: `LICENSE` covers the whole repository.

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
