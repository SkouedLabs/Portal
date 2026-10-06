"""Custom trust store: root / intermediate CAs added from the admin panel (internal PKI).

The CAs are added *on top of* the system trust store and used for every outgoing
TLS connection: LDAPS / StartTLS, the OIDC provider and the status checks.
"""
import os
import re
import ssl
import threading
from dataclasses import dataclass
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import TrustedCA

SYSTEM_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
_PEM_RE = re.compile(rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)


class CertificateError(ValueError):
    pass


@dataclass
class ParsedCert:
    pem: str
    subject: str
    issuer: str
    fingerprint_sha256: str
    not_before: datetime
    not_after: datetime
    is_ca: bool
    common_name: str


def _name(n: x509.Name) -> str:
    return n.rfc4514_string()


def parse_bundle(data: bytes) -> list[ParsedCert]:
    """Accepts one or several PEM certificates, or a single DER certificate."""
    blocks = _PEM_RE.findall(data)
    try:
        certs = [x509.load_pem_x509_certificate(b) for b in blocks] if blocks else [x509.load_der_x509_certificate(data)]
    except ValueError as exc:
        raise CertificateError(f"Unreadable certificate: {exc}") from exc
    if not certs:
        raise CertificateError("No certificate found")
    out = []
    for c in certs:
        try:
            bc = c.extensions.get_extension_for_class(x509.BasicConstraints).value
            is_ca = bc.ca
        except x509.ExtensionNotFound:
            is_ca = c.subject == c.issuer  # old self-signed roots without the extension
        cn = c.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        fp = c.fingerprint(hashes.SHA256()).hex().upper()
        out.append(ParsedCert(
            pem=c.public_bytes(serialization.Encoding.PEM).decode(),
            subject=_name(c.subject),
            issuer=_name(c.issuer),
            fingerprint_sha256=":".join(fp[i:i + 2] for i in range(0, len(fp), 2)),
            not_before=c.not_valid_before_utc,
            not_after=c.not_valid_after_utc,
            is_ca=is_ca,
            common_name=str(cn[0].value) if cn else _name(c.subject),
        ))
    return out


# --- Cached SSL context ---------------------------------------------------------
# Rebuilt when the set of CAs changes (several workers: each checks the DB "version").
_lock = threading.Lock()
_cache: dict = {"version": None, "pem": "", "ctx": None, "insecure": None}


def _version(db: Session) -> tuple:
    return tuple(db.execute(select(func.count(TrustedCA.id), func.max(TrustedCA.id), func.max(TrustedCA.created_at))).one())


def custom_pem(db: Session) -> str:
    _refresh(db)
    return _cache["pem"]


def _refresh(db: Session) -> None:
    v = _version(db)
    if v == _cache["version"]:
        return
    with _lock:
        pem = "\n".join(db.scalars(select(TrustedCA.pem).order_by(TrustedCA.id)).all())
        ctx = ssl.create_default_context()
        if pem:
            ctx.load_verify_locations(cadata=pem)
        _cache.update(version=v, pem=pem, ctx=ctx)


def ssl_context(db: Session, verify: bool = True) -> ssl.SSLContext:
    """System CAs + custom CAs. With verify=False, an explicit no-verification context."""
    if not verify:
        if _cache["insecure"] is None:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            _cache["insecure"] = ctx
        return _cache["insecure"]
    _refresh(db)
    return _cache["ctx"]


def ldap_ca_kwargs(db: Session, extra_pem: str = "") -> dict:
    """ldap3 Tls() arguments: system bundle file + custom CAs (+ the LDAP-specific CA, if any)."""
    data = "\n".join(p for p in (custom_pem(db), extra_pem) if p)
    kwargs: dict = {}
    if data:
        kwargs["ca_certs_data"] = data
        # ldap3 only loads the system store when no CA is given: add it explicitly.
        if os.path.isfile(SYSTEM_BUNDLE):
            kwargs["ca_certs_file"] = SYSTEM_BUNDLE
    return kwargs
