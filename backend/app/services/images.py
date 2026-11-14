"""Re-encoding of uploaded images.

An image dropped into the portal comes as it left the design tool, the phone or the stock photo
site: a 2 MB PNG for a logo the browser draws at 48 pixels, a 6 000 px photograph for a background.
The background is the worst case, because it is what the page paints first and the viewer waits on
it every single time.

So nothing is stored as it arrives. Every raster upload is decoded, scaled down to the largest size
the portal can actually display it at, stripped of its metadata and re-encoded to WebP, which every
browser the portal supports has read for years and which beats PNG and JPEG by a wide margin on
both flat artwork and photographs. Typical results: a 2.5 MB logo becomes ~40 KB, a 4 MB background
~250 KB.

Left untouched on purpose:

- **SVG** — already vector and tiny; re-encoding it to a raster would be a downgrade.
- **ICO** — several resolutions in one file, which is the point of the format.
- **Animated GIF and WebP** — a single-frame re-encode would silently drop the animation.
- Anything that comes out **bigger than it went in** (a 300-byte icon can beat its own WebP), unless
  it is a JPEG: those are re-encoded regardless, because that is what drops the EXIF block, and the
  EXIF of a photograph carries the GPS coordinates of where it was taken.
"""
import io
import logging

from PIL import Image, ImageOps

log = logging.getLogger("portal.images")

# A deliberately crafted file can declare enormous dimensions and expand into memory on decoding.
# Pillow refuses anything beyond this (~100 megapixels, far above any legitimate background).
Image.MAX_IMAGE_PIXELS = 100_000_000

# The largest useful size per use, in pixels. The portal never draws a logo larger than a header
# or a card; a background is drawn full-screen, and 2560 covers a 1440p display without pretending
# a 5K one will see the difference under a "cover" scaling.
BOUNDS = {
    "icon": (512, 512),
    "background": (2560, 2560),
}
DEFAULT_BOUND = (1024, 1024)

# Formats whose bytes are kept as they are.
PASSTHROUGH = {"svg", "ico"}

_QUALITY = {"icon": 90, "background": 82}


def _is_animated(im: Image.Image) -> bool:
    return getattr(im, "n_frames", 1) > 1


def optimize(data: bytes, ext: str, kind: str = "") -> tuple[bytes, str]:
    """Return the bytes to store and their extension, given the sniffed extension of the upload.

    Never raises: an image the portal cannot process is an image it stores unchanged, which is
    what it did before this existed. `kind` is a hint from the interface ("icon", "background");
    an unknown one gets the middle-ground bound.
    """
    if ext in PASSTHROUGH:
        return data, ext
    try:
        with Image.open(io.BytesIO(data)) as im:
            if _is_animated(im):
                return data, ext
            # Phones record the orientation in EXIF rather than rotating the pixels. Apply it here:
            # the EXIF block is about to be dropped, and without this the image would come out
            # sideways.
            im = ImageOps.exif_transpose(im)
            before = im.size
            im.thumbnail(BOUNDS.get(kind, DEFAULT_BOUND), Image.LANCZOS)
            # Palette and greyscale images are promoted so WebP keeps whatever transparency they had
            im = im.convert("RGBA" if ("A" in im.getbands() or "transparency" in im.info) else "RGB")
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=_QUALITY.get(kind, 85), method=6)
            out = buf.getvalue()
    except Exception:  # unreadable, truncated, a decompression bomb, an unsupported variant…
        log.warning("Could not re-encode a %s upload; stored as it arrived", ext, exc_info=True)
        return data, ext

    # A JPEG is always replaced even when it was smaller: the re-encode is what removes the EXIF,
    # and the EXIF of a photograph carries the place and the time it was taken.
    if len(out) >= len(data) and ext != "jpg":
        return data, ext
    log.info("Upload re-encoded: %s %dx%d %d B -> webp %dx%d %d B", ext, *before, len(data), *im.size, len(out))
    return out, "webp"
