# Dashboards and the editor

[Documentation](README.md) · [Portal-NG](../README.md)

A dashboard is one page: a header, an optional message banner, navigation links, and **sections** of
**cards**. It is what Homer calls a page, with one difference that changes everything — there can be
several, each with its own look and its own audience.

Create one in **Admin › Dashboards › New**, then open the **editor**. Everything below is edited there,
with a live preview beside it.

## Sections and cards

- A **section** is a titled group of cards, with an optional icon.
- A **card** is a link: a name, a subtitle, a URL, and either a **Font Awesome icon** or an **uploaded
  image**. It can also carry tags, a background colour, and a [status check](monitoring.md#status-checks).
- The **icon picker** searches the 2 000+ Font Awesome Free icons, bundled locally so it works with no
  internet access. Click the magnifier in any icon field.
- Cards open in the same tab or a new one, as you choose per card.

## The rest of the page

| Element | What it is |
|---|---|
| **Header** | The dashboard logo (or the portal logo), the title and the subtitle. It can be turned off. |
| **Navigation links** | The row of links in the bar: other dashboards, an intranet, a ticketing tool. |
| **Message banner** | A coloured notice at the top (info, success, warning, danger) with a title, an icon and some text. Useful for a maintenance window. |
| **Search** | Press `/` to filter the cards by name, subtitle, tag or URL. |
| **Layout** | Columns (1 to 5) or a list, and the default theme: light, dark, or follow the system. |
| **Footer** | Per dashboard, falling back to the portal footer. |

Colours, backgrounds and themes are in [Branding, images and themes](branding.md) — they work the same
way for a dashboard as for the whole portal, the dashboard overriding the portal.

## Who sees it

Each dashboard has a **visibility** and a set of **access rules**:

- **All signed-in users** — everyone who is signed in sees it. Rules then only grant the right to *edit*.
- **Restricted** — only the listed groups and users see it.

A rule targets a group (local, LDAP or OIDC) or a single user, with **View** or **View + edit**. This is
covered in full, including how to grant rights to an LDAP or OIDC group that has never signed in yet, in
[Users, rights and authentication](users-and-rights.md#access-rules).

Imported and newly created dashboards are **restricted** by default: nobody but an administrator sees them
until you say so.

## The YAML view

The editor has a **YAML** tab that reads and writes Homer's `config.yml` format for the dashboard you are
editing. It is there for three things:

- **reviewing a large change** as a diff rather than through the form;
- **copying a dashboard** between instances — export here, import there;
- **importing a single Homer page** into a dashboard that already exists. Homer `Ping` cards become status
  checks.

Importing a whole Homer instance, with its pages and its images, is a different and better path:
[Migrating from Homer](homer.md).

What the YAML view refuses is what the rest of the portal refuses — `javascript:`, `data:`, `vbscript:`
and `file:` URLs, colours and icon classes that would inject CSS or HTML, and status URLs that are not
`http(s)`. Dashboard content is editable by non-administrators, so it is validated like untrusted input,
because it is.
