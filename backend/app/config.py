import urllib.parse
from pydantic import field_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine.url import make_url


def format_database_url(url: str) -> str:
    """Ensure special characters in the database password are correctly percent-encoded."""
    if not url or "://" not in url:
        return url

    # If it already parses cleanly with no '@' or '#' in host, return it
    try:
        parsed = make_url(url)
        if "@" not in (parsed.host or "") and "#" not in (parsed.host or ""):
            return parsed.render_as_string(hide_password=False)
    except Exception:
        pass

    prefix, remainder = url.split("://", 1)
    path_start = remainder.find("/")
    if path_start != -1:
        authority = remainder[:path_start]
        rest = remainder[path_start:]
    else:
        authority = remainder
        rest = ""

    at_idx = authority.rfind("@")
    if at_idx != -1:
        userinfo = authority[:at_idx]
        hostport = authority[at_idx + 1:]
        colon_idx = userinfo.find(":")
        if colon_idx != -1:
            username = userinfo[:colon_idx]
            raw_password = userinfo[colon_idx + 1:]
            unquoted = urllib.parse.unquote(raw_password)
            encoded_password = urllib.parse.quote(unquoted, safe="")
            return f"{prefix}://{username}:{encoded_password}@{hostport}{rest}"

    return url


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/finance_tracker"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    ENVIRONMENT: str = "development"

    # Supabase authentication
    # Recommended: SUPABASE_URL (e.g. https://<project-ref>.supabase.co) fetches
    # asymmetric public keys from the JWKS endpoint.
    SUPABASE_URL: str = "https://irvnzqygeoyjgwzdlxxd.supabase.co"
    SUPABASE_JWKS_URL: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # Legacy symmetric JWT secret (for backward-compatibility with HS256)
    SUPABASE_JWT_SECRET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def sanitize_database_url(cls, v: str) -> str:
        return format_database_url(v)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def jwks_url(self) -> str | None:
        """Derive the JWKS endpoint URL from SUPABASE_JWKS_URL or SUPABASE_URL."""
        if self.SUPABASE_JWKS_URL:
            return self.SUPABASE_JWKS_URL
        if self.SUPABASE_URL:
            return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    @property
    def auth_enabled(self) -> bool:
        """Auth is enabled when JWKS URL or JWT secret is configured."""
        return bool(self.jwks_url or self.SUPABASE_JWT_SECRET)


settings = Settings()

