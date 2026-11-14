"""Portal-NG.

The version is stamped into the image at build time by the publish workflow (PORTAL_NG_VERSION
build argument, taken from the git tag). A build from a checkout reports "dev", which is the
honest answer: there is nothing to bump in the source, the tag is the release.
"""
import os

__version__ = os.getenv("PORTAL_NG_VERSION") or "dev"
