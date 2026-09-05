"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/finance_tracker"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    ENVIRONMENT: str = "development"

    # Supabase JWT verification
    # Found in Supabase Dashboard → Settings → API → JWT Secret
    SUPABASE_JWT_SECRET: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def auth_enabled(self) -> bool:
        """Auth is enabled when a JWT secret is configured."""
        return bool(self.SUPABASE_JWT_SECRET)


settings = Settings()

