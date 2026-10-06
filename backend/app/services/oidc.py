"""OpenID Connect connector (Authorization Code + PKCE S256)."""
import logging
import time
from urllib.parse import urlencode

import httpx
import jwt

from ..config import get_settings
from ..security import constant_time_equals, new_token, pkce_challenge
from .identity import ExternalGroup, ExternalIdentity
from .trust import ssl_context

log = logging.getLogger("portal.oidc")

# The signing algorithm is chosen by the IdP; "none" and HS* are refused.
ALLOWED_ALGS = ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"]

_discovery_cache: dict[str, tuple[float, dict]] = {}


class OidcError(Exception):
    pass


def redirect_uri() -> str:
    return f"{get_settings().public_url}/api/auth/oidc/callback"


def with_trust(db, cfg: dict) -> dict:
    """Attach the SSL context (system + trusted CAs from the admin panel) to the connector config."""
    return {**cfg, "_ssl": ssl_context(db, bool(cfg.get("verify_tls", True)))}


def _client(cfg: dict) -> httpx.Client:
    verify = cfg.get("_ssl") or bool(cfg.get("verify_tls", True))
    return httpx.Client(timeout=10, verify=verify, follow_redirects=False)


def discover(cfg: dict, *, force: bool = False) -> dict:
    issuer = (cfg.get("issuer") or "").rstrip("/")
    if not issuer:
        raise OidcError("Issuer is not configured")
    cached = _discovery_cache.get(issuer)
    if cached and not force and time.time() - cached[0] < 3600:
        return cached[1]
    with _client(cfg) as c:
        r = c.get(f"{issuer}/.well-known/openid-configuration")
        r.raise_for_status()
        meta = r.json()
        r = c.get(meta["jwks_uri"])
        r.raise_for_status()
        meta["_jwks"] = r.json()
    if meta.get("issuer", "").rstrip("/") != issuer:
        raise OidcError(f"Issuer mismatch: {meta.get('issuer')}")
    _discovery_cache[issuer] = (time.time(), meta)
    return meta


def build_authorization(cfg: dict) -> tuple[str, str, str, str]:
    """Returns (url, state, code_verifier, nonce)."""
    meta = discover(cfg)
    state, nonce, verifier = new_token(), new_token(), new_token(48)
    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri(),
        "scope": cfg.get("scopes") or "openid",
        "state": state,
        "nonce": nonce,
        "code_challenge": pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    return f"{meta['authorization_endpoint']}?{urlencode(params)}", state, verifier, nonce


def _verify_id_token(cfg: dict, meta: dict, id_token: str, nonce: str) -> dict:
    header = jwt.get_unverified_header(id_token)
    alg = header.get("alg")
    if alg not in ALLOWED_ALGS:
        raise OidcError(f"Signing algorithm refused: {alg}")
    jwks = jwt.PyJWKSet.from_dict(meta["_jwks"])
    kid = header.get("kid")
    keys = [k for k in jwks.keys if kid is None or k.key_id == kid]
    if not keys:
        # key rotation on the IdP side: reload once
        meta = discover(cfg, force=True)
        keys = [k for k in jwt.PyJWKSet.from_dict(meta["_jwks"]).keys if kid is None or k.key_id == kid]
    if not keys:
        raise OidcError("Unknown signing key")
    claims = jwt.decode(
        id_token,
        key=keys[0].key,
        algorithms=[alg],
        audience=cfg["client_id"],
        issuer=meta["issuer"],
        leeway=60,
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )
    if not constant_time_equals(str(claims.get("nonce", "")), nonce):
        raise OidcError("Invalid nonce")
    return claims


def exchange_code(cfg: dict, code: str, verifier: str, nonce: str) -> ExternalIdentity:
    meta = discover(cfg)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "code_verifier": verifier,
    }
    auth = None
    if cfg.get("token_auth_method") == "client_secret_post":
        data |= {"client_id": cfg["client_id"], "client_secret": cfg.get("client_secret", "")}
    else:
        auth = (cfg["client_id"], cfg.get("client_secret", ""))
        data["client_id"] = cfg["client_id"]

    with _client(cfg) as c:
        r = c.post(meta["token_endpoint"], data=data, auth=auth, headers={"Accept": "application/json"})
        if r.status_code != 200:
            raise OidcError(f"Code exchange refused ({r.status_code}): {r.text[:200]}")
        tokens = r.json()
        if "id_token" not in tokens:
            raise OidcError("Response has no id_token")
        claims = _verify_id_token(cfg, meta, tokens["id_token"], nonce)

        groups_claim = cfg.get("groups_claim") or "groups"
        if (groups_claim not in claims or cfg.get("username_claim") not in claims) and meta.get("userinfo_endpoint"):
            r = c.get(meta["userinfo_endpoint"], headers={"Authorization": f"Bearer {tokens['access_token']}"})
            if r.status_code == 200:
                info = r.json()
                if info.get("sub") == claims["sub"]:
                    claims = {**info, **claims}

    raw_groups = _claim(claims, groups_claim) or []
    if isinstance(raw_groups, str):
        raw_groups = [raw_groups]
    groups = [ExternalGroup(external_id=str(g), name=str(g).rsplit("/", 1)[-1] or str(g)) for g in raw_groups]

    username = str(_claim(claims, cfg.get("username_claim") or "preferred_username") or claims.get("email") or claims["sub"])
    return ExternalIdentity(
        source="oidc",
        external_id=str(claims["sub"]),
        username=username,
        email=claims.get("email"),
        display_name=claims.get("name") or username,
        groups=groups,
    )


def _claim(claims: dict, path: str):
    """Supports nested claims, e.g. "realm_access.roles" (Keycloak)."""
    cur = claims
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur
