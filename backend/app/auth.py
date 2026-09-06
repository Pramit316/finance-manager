"""Supabase JWT authentication middleware.

Verifies the Bearer token from the Authorization header.
Supports:
1. Recommended asymmetric signing (ES256, RS256) via Supabase project JWKS endpoint.
2. Legacy symmetric signing (HS256) via SUPABASE_JWT_SECRET fallback.

In development (when neither SUPABASE_URL / JWKS nor SUPABASE_JWT_SECRET is configured),
auth is bypassed so local testing without Supabase credentials works seamlessly.
"""

import logging
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

# Optional bearer — won't raise 403 automatically; we handle it ourselves
_bearer_scheme = HTTPBearer(auto_error=False)

# Cached PyJWKClient instance
_jwks_client: jwt.PyJWKClient | None = None
_jwks_client_url: str | None = None

# Supported asymmetric algorithms for Supabase tokens
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256", "ES384", "RS384", "ES512", "RS512"]


def get_jwks_client() -> jwt.PyJWKClient | None:
    """Get or instantiate the cached PyJWKClient for the configured JWKS URL."""
    global _jwks_client, _jwks_client_url
    url = settings.jwks_url
    if not url:
        return None
    if _jwks_client is None or _jwks_client_url != url:
        _jwks_client = jwt.PyJWKClient(
            url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=300,
        )
        _jwks_client_url = url
    return _jwks_client


def verify_jwt(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict[str, Any] | None:
    """FastAPI dependency that verifies the Supabase JWT.

    Returns the decoded JWT payload on success.
    Returns None (and skips auth) when auth is disabled (local dev).
    Raises HTTP 401 when auth is enabled but the token is missing/invalid/expired.
    """
    if not settings.auth_enabled:
        # Local development without Supabase — skip auth
        return None

    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as e:
        logger.warning("Failed to decode token header: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token")

    alg = header.get("alg")
    if not alg:
        logger.warning("Token missing 'alg' in header")
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        # Asymmetric signing (ES256, RS256, etc.) or tokens with a Key ID (kid)
        if alg in ASYMMETRIC_ALGORITHMS or (header.get("kid") and alg != "HS256"):
            jwks_client = get_jwks_client()
            if jwks_client is None:
                logger.warning("Received asymmetric token (%s) but JWKS endpoint is not configured", alg)
                raise HTTPException(status_code=401, detail="Invalid token")

            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                key = signing_key.key
            except jwt.PyJWKClientError as e:
                logger.warning("JWKS key lookup failed: %s", e)
                raise HTTPException(status_code=401, detail="Invalid token")

            payload = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience=settings.SUPABASE_JWT_AUDIENCE,
            )

        # Legacy symmetric signing (HS256)
        elif alg == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                logger.warning("Received HS256 token but SUPABASE_JWT_SECRET is not configured")
                raise HTTPException(status_code=401, detail="Invalid token")

            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=settings.SUPABASE_JWT_AUDIENCE,
            )

        else:
            logger.warning("Unsupported JWT algorithm: %s", alg)
            raise HTTPException(status_code=401, detail="Invalid token")

        # Explicit validation: Reject anon keys and ensure a valid user subject is present
        if payload.get("role") == "anon":
            logger.warning("Anon key rejected for user-authenticated endpoint")
            raise HTTPException(status_code=401, detail="Invalid token")

        if not payload.get("sub"):
            logger.warning("Token payload missing user 'sub' identifier")
            raise HTTPException(status_code=401, detail="Invalid token")

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during JWT verification: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token")
