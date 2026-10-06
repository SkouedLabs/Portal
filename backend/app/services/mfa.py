"""Multi-factor authentication for local and LDAP accounts: TOTP, WebAuthn, recovery codes.

OIDC accounts are not concerned: MFA is the identity provider's job.

Post-quantum note: TOTP is an HMAC (symmetric, unaffected by Shor). WebAuthn
authenticators sign with ES256 / EdDSA / RS256 today; ML-DSA COSE algorithms
are not supported by hardware keys yet. WebAuthn remains phishing-resistant and is
always combined with the password (Argon2id / LDAP) as a second factor.
"""
import json
import secrets
import time
from datetime import timedelta

import pyotp
import segno
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..config import get_settings
from ..models import AuthChallenge, MfaFactor, RecoveryCode, User, utcnow
from ..security import decrypt_secret, encrypt_secret, new_token, token_digest
from .settings import get_section

CHALLENGE_TTL = {"mfa": 300, "enroll": 600, "totp_setup": 600, "webauthn_reg": 300, "webauthn_auth": 300}
MAX_ATTEMPTS = 5
RECOVERY_CODES = 10
MFA_SOURCES = ("local", "ldap")


class MfaError(Exception):
    pass


# --- Policy -----------------------------------------------------------------------

def methods_enabled(db: Session) -> list[str]:
    cfg = get_section(db, "mfa")
    return [m for m, on in (("totp", cfg["totp_enabled"]), ("webauthn", cfg["webauthn_enabled"])) if on]


def user_factors(db: Session, user: User, *, usable_only: bool = False) -> list[MfaFactor]:
    factors = db.scalars(select(MfaFactor).where(MfaFactor.user_id == user.id).order_by(MfaFactor.id)).all()
    if usable_only:
        enabled = methods_enabled(db)
        factors = [f for f in factors if f.kind in enabled]
    return list(factors)


def enrolment_required(db: Session, user: User, is_admin: bool) -> bool:
    if user.source not in MFA_SOURCES or not methods_enabled(db):
        return False
    enforce = get_section(db, "mfa")["enforce"]
    return enforce == "all" or (enforce == "admins" and is_admin)


# --- Challenges -------------------------------------------------------------------

def create_challenge(db: Session, user: User, purpose: str, *, source: str | None = None, data: dict | None = None) -> str:
    token = new_token()
    db.add(AuthChallenge(id=token_digest(token), user_id=user.id, purpose=purpose, auth_source=source, data=data or {}))
    db.commit()
    return token


def get_challenge(db: Session, token: str | None, purposes: tuple[str, ...], user_id: int | None = None) -> AuthChallenge:
    if not token:
        raise MfaError("Missing challenge")
    ch = db.get(AuthChallenge, token_digest(token))
    if ch is None or ch.purpose not in purposes or (user_id is not None and ch.user_id != user_id):
        raise MfaError("Invalid or expired challenge, please start again")
    if ch.created_at < utcnow() - timedelta(seconds=CHALLENGE_TTL[ch.purpose]) or ch.attempts >= MAX_ATTEMPTS:
        db.delete(ch)
        db.commit()
        raise MfaError("Invalid or expired challenge, please start again")
    return ch


def fail_attempt(db: Session, ch: AuthChallenge) -> None:
    ch.attempts += 1
    db.commit()


def purge_challenges(db: Session) -> None:
    db.execute(delete(AuthChallenge).where(AuthChallenge.created_at < utcnow() - timedelta(seconds=max(CHALLENGE_TTL.values()))))


# --- TOTP ---------------------------------------------------------------------------

def totp_begin(db: Session, user: User) -> dict:
    secret = pyotp.random_base32(length=32)  # 160 bits
    issuer = get_section(db, "branding")["portal_name"] or "Portal-NG"
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=issuer)
    # QR code generated server-side as SVG: works without internet access.
    qr = segno.make(uri, error="m").svg_data_uri(scale=5, border=2, dark="#111", light="#fff")
    setup = create_challenge(db, user, "totp_setup", data={"secret": encrypt_secret(secret)})
    return {"setup_token": setup, "secret": secret, "uri": uri, "qr": qr}


def _totp_match(secret: str, code: str, last_step: int) -> int | None:
    """Returns the matched time step (±1 window), refusing reuse of an already used step."""
    code = "".join(c for c in code if c.isdigit())
    if len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    now = int(time.time()) // 30
    for step in (now - 1, now, now + 1):
        if step > last_step and secrets.compare_digest(totp.at(step * 30), code):
            return step
    return None


def totp_finish(db: Session, user: User, setup_token: str, code: str, name: str) -> MfaFactor:
    ch = get_challenge(db, setup_token, ("totp_setup",), user.id)
    secret = decrypt_secret(ch.data["secret"])
    step = _totp_match(secret, code, 0)
    if step is None:
        fail_attempt(db, ch)
        raise MfaError("Invalid code")
    factor = MfaFactor(user_id=user.id, kind="totp", name=name or "Authenticator app",
                       secret=encrypt_secret(secret), last_used_step=step)
    db.add(factor)
    db.delete(ch)
    db.commit()
    return factor


def totp_verify(db: Session, user: User, code: str) -> bool:
    for f in user_factors(db, user, usable_only=True):
        if f.kind != "totp":
            continue
        step = _totp_match(decrypt_secret(f.secret), code, f.last_used_step)
        if step is not None:
            f.last_used_step, f.last_used_at = step, utcnow()
            db.commit()
            return True
    return False


# --- Recovery codes -----------------------------------------------------------------

def _norm(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


def regenerate_recovery_codes(db: Session, user: User) -> list[str]:
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = []
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(RECOVERY_CODES):
        raw = "".join(secrets.choice(alphabet) for _ in range(16))  # 80 bits
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}")
        db.add(RecoveryCode(user_id=user.id, code_hash=token_digest(raw)))
    db.commit()
    return codes


def clear(db: Session, user: User) -> None:
    """Remove every factor and recovery code of a user (admin reset)."""
    db.execute(delete(MfaFactor).where(MfaFactor.user_id == user.id))
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.execute(delete(AuthChallenge).where(AuthChallenge.user_id == user.id))
    db.commit()


def recovery_remaining(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(RecoveryCode).where(
        RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))) or 0


def recovery_verify(db: Session, user: User, code: str) -> bool:
    digest = token_digest(_norm(code))
    row = db.scalar(select(RecoveryCode).where(
        RecoveryCode.user_id == user.id, RecoveryCode.code_hash == digest, RecoveryCode.used_at.is_(None)))
    if row is None:
        return False
    row.used_at = utcnow()
    db.commit()
    return True


# --- WebAuthn -----------------------------------------------------------------------

def _rp() -> tuple[str, str]:
    s = get_settings()
    return s.webauthn_rp_id, s.public_url


def webauthn_register_begin(db: Session, user: User) -> dict:
    rp_id, _ = _rp()
    existing = [f for f in user_factors(db, user) if f.kind == "webauthn"]
    opts = generate_registration_options(
        rp_id=rp_id,
        rp_name=get_section(db, "branding")["portal_name"] or "Portal-NG",
        user_id=f"portal-ng:{user.id}".encode(),
        user_name=user.username,
        user_display_name=user.display_name or user.username,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(f.credential_id)) for f in existing],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.EDDSA,
            COSEAlgorithmIdentifier.ECDSA_SHA_512,
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PSS_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    token = create_challenge(db, user, "webauthn_reg", data={"challenge": bytes_to_base64url(opts.challenge)})
    return {"registration_token": token, "options": json.loads(options_to_json(opts))}


def webauthn_register_finish(db: Session, user: User, token: str, credential: dict, name: str) -> MfaFactor:
    ch = get_challenge(db, token, ("webauthn_reg",), user.id)
    rp_id, origin = _rp()
    try:
        v = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(ch.data["challenge"]),
            expected_rp_id=rp_id,
            expected_origin=origin,
        )
    except Exception as exc:
        fail_attempt(db, ch)
        raise MfaError(f"Security key registration failed: {exc}") from exc
    factor = MfaFactor(
        user_id=user.id, kind="webauthn", name=name or "Security key",
        credential_id=bytes_to_base64url(v.credential_id),
        public_key=bytes_to_base64url(v.credential_public_key),
        sign_count=v.sign_count,
    )
    db.add(factor)
    db.delete(ch)
    db.commit()
    return factor


def webauthn_auth_options(db: Session, user: User, ch: AuthChallenge) -> dict:
    rp_id, _ = _rp()
    creds = [f for f in user_factors(db, user, usable_only=True) if f.kind == "webauthn"]
    if not creds:
        raise MfaError("No security key registered")
    opts = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(f.credential_id)) for f in creds],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    ch.data = {**(ch.data or {}), "webauthn": bytes_to_base64url(opts.challenge)}
    db.commit()
    return json.loads(options_to_json(opts))


def webauthn_verify(db: Session, user: User, ch: AuthChallenge, credential: dict) -> bool:
    expected = (ch.data or {}).get("webauthn")
    raw_id = credential.get("rawId") or credential.get("id") or ""
    factor = db.scalar(select(MfaFactor).where(
        MfaFactor.user_id == user.id, MfaFactor.kind == "webauthn", MfaFactor.credential_id == raw_id))
    if not expected or factor is None:
        return False
    rp_id, origin = _rp()
    try:
        v = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(expected),
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=base64url_to_bytes(factor.public_key),
            credential_current_sign_count=factor.sign_count,
        )
    except Exception:
        return False
    factor.sign_count, factor.last_used_at = v.new_sign_count, utcnow()
    db.commit()
    return True


def factor_out(f: MfaFactor) -> dict:
    return {
        "id": f.id, "kind": f.kind, "name": f.name,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "last_used_at": f.last_used_at.isoformat() if f.last_used_at else None,
    }
