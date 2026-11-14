# Status checks and logs

[Documentation](README.md) · [Portal-NG](../README.md)

## Status checks

Tick **"Check status"** on a card in the editor and it gets a coloured dot with the HTTP code and the
latency of the application behind it.

| Dot | Meaning |
|---|---|
| 🟢 Green | 2xx or 3xx — it answered |
| 🟠 Orange | 4xx — reachable, but it said no (asking for authentication, most often) |
| 🔴 Red | 5xx, a timeout, or a TLS error |
| ⚪ Grey | Not probed yet |

**The backend probes, not the browser.** That is the whole design, and it buys three things:

- it works for **internal applications** the viewer's browser may not reach;
- it honours the **certificate authorities** from Admin › Certificates, so an internal PKI is not an
  error;
- there is **no CORS and no mixed-content problem**, because the browser never makes the request.

Results are **cached** — 30 seconds by default — so a hundred people looking at the same dashboard do not
produce a hundred requests to the application. Only `http(s)` URLs, on cards an editor has flagged, are
ever probed.

Settings are in **Admin › Branding**: whether checks run at all, the timeout (5 s by default) and the
cache duration. Each dashboard also sets how often the browser refreshes the dots.

> A card points wherever an editor says, and the backend will go there. That is the feature, and it is why
> the right to edit a dashboard is worth giving deliberately — see
> [Users and rights](users-and-rights.md#access-rules).

## Logs

**Admin › Logs** holds what happened, in one place:

| Category | What is recorded |
|---|---|
| Navigation | Dashboards viewed, links opened |
| Authentication | Sign-ins and failures, the method used, MFA events |
| Administration | Changes to dashboards, users, groups, settings; uploads |

Each entry carries the time, the account, the **real client IP** (from `X-Forwarded-For`, trusted only
from `TRUSTED_PROXIES` — see [Deployment](deployment.md)), and what was acted on.

- **Filters** on category, account, period and free text, with auto-refresh.
- **CSV export** of the current filter.
- **Admin › Overview** turns the same data into statistics: the most used dashboards and links, sign-ins
  over time, failures.

### Retention and what gets logged

In **Admin › Branding**:

- **Retention** — 90 days by default. The purge runs every 6 hours.
- **Log views** and **log clicks** can each be turned off, if recording what individuals open is more than
  you want to keep. Authentication and administration events are always recorded.

Container logs are separate and go to Docker or journald as usual (`docker compose logs backend`). They
hold startup messages, warnings — the default administrator password, a plaintext LDAP connection — and
the generated administrator password when `INITIAL_ADMIN_PASSWORD` is left empty.
