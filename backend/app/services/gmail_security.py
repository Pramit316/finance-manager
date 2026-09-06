"""OAuth state and token encryption helpers for Gmail."""

import base64
import hashlib
import hmac
import json
import time
from cryptography.fernet import Fernet

from app.config import settings


def _key() -> bytes:
    if not settings.GMAIL_TOKEN_ENCRYPTION_KEY:
        raise RuntimeError("GMAIL_TOKEN_ENCRYPTION_KEY is not configured")
    return settings.GMAIL_TOKEN_ENCRYPTION_KEY.encode("ascii")


def encrypt_token(token: str) -> str:
    return Fernet(_key()).encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    return Fernet(_key()).decrypt(token.encode()).decode()


def create_oauth_state(user_id: str) -> str:
    payload = {"user_id": user_id, "expires_at": int(time.time()) + 600}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_key(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def validate_oauth_state(state: str) -> str:
    try:
        encoded, signature = state.split(".", 1)
        expected = hmac.new(_key(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid OAuth state")
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if int(payload["expires_at"]) < int(time.time()):
            raise ValueError("Expired OAuth state")
        return str(payload["user_id"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid OAuth state") from exc