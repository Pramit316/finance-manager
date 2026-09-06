"""Small adapter around Google OAuth and Gmail API clients."""

from datetime import datetime, timezone

from app.config import settings
from app.services.gmail_security import decrypt_token, encrypt_token

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _client_config() -> dict:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not settings.GOOGLE_REDIRECT_URI:
        raise RuntimeError("Google OAuth settings are not configured")
    return {"web": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
    }}


def build_authorization_url(state: str) -> str:
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    url, _ = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url


def exchange_code(code: str):
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=settings.GOOGLE_REDIRECT_URI)
    flow.fetch_token(code=code)
    return flow.credentials


def gmail_service(connection):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=decrypt_token(connection.encrypted_access_token) if connection.encrypted_access_token else None,
        refresh_token=decrypt_token(connection.encrypted_refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(__import__("google.auth.transport.requests", fromlist=["Request"]).Request())
        connection.encrypted_access_token = encrypt_token(credentials.token)
        connection.token_expiry = credentials.expiry
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def credential_values(credentials) -> dict:
    return {
        "encrypted_access_token": encrypt_token(credentials.token) if credentials.token else None,
        "encrypted_refresh_token": encrypt_token(credentials.refresh_token),
        "token_expiry": credentials.expiry or datetime.now(timezone.utc),
    }