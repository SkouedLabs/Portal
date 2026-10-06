"""Cryptographic primitives.

Post-quantum resistant choices: the application uses NO classical asymmetric
cryptography (RSA/ECC) for its own needs. Only symmetric / hash-based
primitives are used, whose security is only reduced quadratically by Grover's
algorithm:

* Passwords        : Argon2id (RFC 9106), m=64 MiB, t=3, p=4
* Session tokens   : 256 random bits (CSPRNG), stored as SHA3-256 digests
* Secrets at rest  : AES-256-GCM, key derived with HKDF-SHA3-512 (128-bit post-quantum security)
* Comparisons      : constant time (hmac.compare_digest)

Transport (TLS 1.3) uses the X25519MLKEM768 hybrid key exchange (ML-KEM, FIPS 203),
configured in nginx (frontend) and negotiated automatically by OpenSSL 3.5 in the
backend for outgoing connections (LDAPS, OIDC IdP).
"""
import base64
import hashlib
import hmac
import os
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import get_settings

_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4, hash_len=32, salt_len=16)

# Dummy hash so that response time is the same when the user does not exist.
_DUMMY_HASH = _ph.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _ph.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


def new_token(nbytes: int = 32) -> str:
    """Random token, 256 bits by default."""
    return secrets.token_urlsafe(nbytes)


def token_digest(token: str) -> str:
    return hashlib.sha3_256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _derive_key(purpose: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA3_512(),
        length=32,
        salt=b"portal-ng/v1",
        info=purpose,
    ).derive(get_settings().secret_key.encode())


_ENC_PREFIX = "enc:v1:"


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _derive_key(b"settings-encryption")
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), b"portal-ng-setting")
    return _ENC_PREFIX + base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    if not value.startswith(_ENC_PREFIX):
        return value
    raw = base64.urlsafe_b64decode(value[len(_ENC_PREFIX):])
    key = _derive_key(b"settings-encryption")
    return AESGCM(key).decrypt(raw[:12], raw[12:], b"portal-ng-setting").decode()


def pkce_challenge(verifier: str) -> str:
    # S256 is mandated by RFC 7636 (SHA-256 stays robust against Grover: 128-bit preimage resistance).
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
