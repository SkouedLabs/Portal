# Migrating from Homer

[Documentation](README.md) · [Portal-NG](../README.md)

Portal-NG keeps Homer's layout and its configuration format, so an existing instance comes over as it is,
images included.

Go to **Admin › Dashboards › Import from Homer** and select Homer's `assets` folder (the one containing
`config.yml`), or pick the files one by one, or paste a `config.yml`. Everything runs **in your browser**
until you confirm, and nothing needs internet access.

## What it does

- `config.yml` becomes a dashboard. Each additional Homer page (`page2.yml`…) becomes another dashboard,
  merged with `config.yml` the way Homer does it — colours, background and message are inherited.
- Homer page links such as `#page2` are rewritten to point at the new dashboards.
- **Local images** referenced by the configuration (card logos, the header logo, `background-image`) are
  found among the selected files and uploaded to the portal. Only the images actually used are uploaded,
  once each, and each one is [scaled and re-encoded](branding.md#images-and-how-they-are-stored) on the
  way in — a background keeps its full-page bound, a card logo does not.
- Remote image URLs are kept as they are.
- Homer `Ping` cards become [status checks](monitoring.md#status-checks).

A **review screen** then shows, for each dashboard, the title, the slug, the visibility, which images were
found or are missing, and what could not be converted. Nothing is written until you confirm.

## What does not convert

Listed in the review, so there are no surprises afterwards:

- smart cards other than `Ping` — imported as plain links;
- `quick` links and custom stylesheets;
- remote messages (`message.url`);
- colours the portal does not accept;
- anything refused for security reasons: `javascript:` URLs, CSS injection. HTML in the title, the message
  and the footer is reduced to text.

## Two things to know

- **Homer's root `logo.png` sits next to `index.html`, outside `assets`.** Add it to the selection with
  "Select files" if you want it imported.
- **Imported dashboards are restricted** — only administrators see them. Set their access rules afterwards
  in Admin › Dashboards, or from the groups and users pages. See
  [Users and rights](users-and-rights.md#access-rules).

## One page at a time

To merge a single Homer page into a dashboard that already exists, use the **YAML** tab of the editor
instead: it reads and writes Homer's `config.yml` format for that one dashboard. It does not carry images,
which is why the importer above exists. See [Dashboards](dashboards.md#the-yaml-view).
