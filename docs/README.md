# Portal-NG documentation

[Portal-NG](../README.md) · [Changelog](../CHANGELOG.md) · [Contributing](../CONTRIBUTING.md) · [Security policy](../SECURITY.md)

Everything about running Portal-NG, building your dashboards and opening them to your users. Start with
[Getting started](install.md); the rest is read when you need it.

## Run it

| Page | What is in it |
|---|---|
| [Getting started](install.md) | Requirements, first start, the production checklist, updating, backing up, and an offline (air-gapped) installation. |
| [Deployment](deployment.md) | Behind nginx or Traefik (TLS, HSTS, an IP allow-list on the administration), the built-in TLS mode, and rootless Podman with Quadlet units. |
| [Configuration](configuration.md) | Every environment variable, with its default and what it changes — and what is configured from the interface instead. |
| [Architecture](architecture.md) | The three containers, what talks to what, where each piece of data really lives, and the layout of the repository. |

## Build your portal

| Page | What is in it |
|---|---|
| [Dashboards and the editor](dashboards.md) | Sections, cards, icons, tags, navigation links, the message banner, the layout and the themes — and the YAML view. |
| [Branding, images and themes](branding.md) | The portal name, the logo and the favicon, the colours, the sign-in page and dashboard backgrounds, and how uploaded images are stored. |
| [Migrating from Homer](homer.md) | Importing an existing Homer instance with its pages, its colours and its local images, and what does not convert. |

## Open it to your users

| Page | What is in it |
|---|---|
| [Users, rights and authentication](users-and-rights.md) | Local accounts, LDAP / Active Directory, OpenID Connect, group synchronisation, two-step verification, rights per dashboard, and the break-glass switch. |
| [Security](security.md) | The hardened containers, the post-quantum posture, what protects the sign-in and the uploads, and what is left to the operator. |

## Watch it

| Page | What is in it |
|---|---|
| [Status checks and logs](monitoring.md) | How applications are probed and what the colours mean; the navigation and administration logs, their filters, statistics and export. |
| [Operations](operations.md) | The volumes and what is in them, backups and restores, log retention, the database schema, and upgrading. |
| [Development](development.md) | Running the backend and the frontend on your machine, the checks CI runs, how to contribute, and the licence. |
