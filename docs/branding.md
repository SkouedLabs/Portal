# Branding, images and themes

[Documentation](README.md) · [Portal-NG](../README.md)

Everything here is edited in **Admin › Branding** (the portal as a whole) or in the **editor › Appearance**
(one dashboard, overriding the portal). Both have a live preview, and nothing needs a redeploy.

## The portal identity

| Setting | What it changes |
|---|---|
| **Portal name** | The header, the sign-in page, and the browser tab title. |
| **Subtitle** | Under the name on the sign-in page. |
| **Logo** | The header, the sign-in page, and the fallback favicon. **Leave it empty for the bundled Portal-NG logo.** |
| **Favicon** | The browser tab. Falls back to the logo, then to the bundled one. |
| **Primary colour** | The accent, and the default sign-in background gradient. |
| **Sign-in message** | A notice on the sign-in page — a legal banner, or who to call. |
| **Footer** | At the bottom of every dashboard that does not define its own. |

## Colours and themes

A dashboard carries a **light** and a **dark** palette, each with ten colours: header, navigation bar,
hover, page background, card background, text, header text, card title, card subtitle, links. The defaults
are Homer's, so an imported Homer page looks like it did.

Leave a colour empty and the default is used — you only ever set the ones you actually want to change.
Each dashboard chooses which theme it opens in: light, dark, or follow the system. Visitors can switch,
and their choice is remembered in their browser.

## Backgrounds

Both the sign-in page and each dashboard take a background, of four kinds:

- **Default** — a gradient built from the primary colour.
- **Colour** — one flat colour.
- **Gradient** — two colours and an angle.
- **Image** — an uploaded or linked image, covering the page, with two adjustments: **darken** (0–90 %,
  an overlay so light text stays readable) and **blur** (in pixels).

Darken and blur are applied by the browser with CSS, not baked into the file, so changing them costs
nothing and the same image can be reused elsewhere.

## Images and how they are stored

A background is the heaviest thing on the page and the first thing the viewer waits for, so Portal-NG does
not store what you give it. **Every raster image is decoded, scaled down and re-encoded to WebP as it is
uploaded** — once, on the way in, rather than on every view.

| What you upload | Bounded to | Quality | Typical result |
|---|---|---|---|
| A logo, a favicon, a card image | 512 × 512 | 90 | a 2.5 MB PNG → about 35 KB |
| A page or sign-in background | 2560 × 2560 | 82 | a 6 MB photograph → about 250 KB |
| Anything the interface does not label | 1024 × 1024 | 85 | |

The field tells you what happened: *Compressed: 2.4 MB → 33 KB WEBP*.

Left exactly as it arrived, on purpose:

- **SVG** — already vector and tiny; rasterising it would be a downgrade.
- **ICO** — several resolutions in one file, which is the point of the format.
- **Animated GIF and WebP** — a single-frame re-encode would silently drop the animation.
- Anything that comes out **bigger** than it went in (a 300-byte icon can beat its own WebP), **except**
  JPEG: those are re-encoded regardless, because that is what drops the EXIF block — and the EXIF of a
  photograph carries the GPS coordinates of where it was taken.

Other things that keep pages light:

- Images are served with a **one-year immutable** `Cache-Control`. The names are random and never reused,
  so a changed image is a new address and there is no cache to invalidate.
- Card images are loaded **lazily**: a card far down a long dashboard is fetched when it is scrolled to.
- The **bundled logo and favicon** are in the frontend image, so they cost no database and no volume
  access.
- The sent file may be up to `MAX_UPLOAD_MB` (10 MB by default, see [Configuration](configuration.md)).
  That is the limit on what you *send*, not on what is kept — raise it if your sources are large, since
  what is stored is a fraction of it either way.

If you link an image by URL instead of uploading it, none of this applies: it is fetched by each visitor's
browser from wherever it lives, at whatever size it is. Upload it instead, which is also what makes the
portal work with [no internet access](install.md#offline-air-gapped-installation).

## Supported formats

PNG, JPEG, GIF, WebP, ICO and SVG. The format is detected from the **magic bytes** of the file, never from
its name or the `Content-Type` the browser claims, and anything unrecognised is refused. Uploads are
stored under random names and served with `Content-Security-Policy: sandbox`, so an SVG opened directly
cannot run a script. See [Security](security.md#uploads).
