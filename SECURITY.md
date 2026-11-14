# Security policy

## Reporting a vulnerability

**Please do not open a public issue.**

Use GitHub's private reporting form: **Security › Advisories › Report a vulnerability** on
<https://github.com/SkouedLabs/Portal/security/advisories/new>. It is private between you and the
maintainers, and it is the only channel — no address is published here, so there is nothing to keep up to
date and nothing to scrape.

Helpful in a report:

- what an attacker gets out of it, and what they need to start (an account? which role? a session?);
- the smallest sequence of requests that shows it, and the version (`GET /api/health`);
- anything about the deployment that matters (behind which proxy, LDAP or OIDC, two-step verification,
  the built-in TLS mode).

You can expect an acknowledgement within a few days and, if the finding holds, a fix and a published
advisory crediting you unless you ask otherwise. This is a project maintained on spare time: there is no
paid support and no promised deadline, and saying so plainly seems better than a service level nobody can
hold to.

## Supported versions

The latest release is the one that gets fixes. There is no long-term support branch.

## Scope

In scope — anything that lets someone:

- see a dashboard, or edit one, that their account may not (the rules in `app/deps.py` are the single
  decision point, and a way around them is a finding);
- sign in as someone else, keep a session they should have lost, or escalate to administrator;
- get past **two-step verification**, replay a TOTP code, or use a recovery code twice;
- recover a secret at rest — the LDAP bind password, the OIDC client secret, a TOTP secret — or the master
  key that protects them;
- make the instance reach a host it was not pointed at by an administrator, run code, or read files
  outside its data directory;
- inject script or CSS into a page through dashboard content, an uploaded file, or the Homer import —
  dashboard content is editable by non-administrators and is meant to be treated as untrusted;
- bypass the sign-in throttling, or use the sign-in form to find out which accounts exist.

Out of scope:

- anything that needs an **administrator** account to begin with, where an administrator is *meant* to be
  able to do it. An administrator points a status check at an arbitrary URL and the server goes there;
  that is the feature, not a vulnerability.
- missing hardening that the operator is responsible for and the documentation says so: HTTPS and HSTS at
  the reverse proxy, the IP allow-list on the administration, the database password, where `SECRET_KEY`
  lives. See the [production checklist](docs/install.md#production-checklist).
- denial of service through sheer volume.
- reports from a scanner with no demonstrated impact.

## What the project does on its own

The three containers run as non-root with a read-only root filesystem, every capability dropped and
`no-new-privileges`; the database has no published port and no route out of the project. Passwords are
Argon2id, secrets at rest are AES-256-GCM under a key derived from the master key, and only digests of
session and recovery tokens are stored. Uploads are identified by their magic bytes, stored under random
names, re-encoded to strip metadata, and served sandboxed.

What is covered, what is hardened, and what is left to the operator is written down in
[Security](docs/security.md).
