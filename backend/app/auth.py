"""Supabase JWT authentication middleware.

Verifies the Bearer token from the Authorization header against the
Supabase JWT secret. In production, every API request must include
a valid Supabase access token.

In development (when SUPABASE_JWT_SECRET is not set), auth is
bypassed so local development works without Supabase.
"""

import logging

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

# Optional bearer — won't raise 403 automatically; we handle it ourselves
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_jwt(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict | None:
    """FastAPI dependency that verifies the Supabase JWT.

    Returns the decoded JWT payload on success.
    Returns None (and skips auth) when auth is disabled (local dev).
    Raises HTTP 401 when auth is enabled but the token is missing/invalid.
    """
    if not settings.auth_enabled:
        # Local development without Supabase — skip auth
        return None

    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token")
