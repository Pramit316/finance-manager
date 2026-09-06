"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


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
    SUPABASE_URL: str = ""
    SUPABASE_JWKS_URL: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # Legacy symmetric JWT secret (for backward-compatibility with HS256)
    SUPABASE_JWT_SECRET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

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

