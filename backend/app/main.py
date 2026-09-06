"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import verify_jwt
from app.config import settings
from app.api import accounts, imports, transactions, analytics, budgets

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Ensure all tables exist on startup (idempotent, safe on Supabase and local DB)
    try:
        from app.database import engine, Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.warning("Could not auto-initialize tables on startup: %s", e)
    yield


app = FastAPI(
    title="FinTrack API",
    description="Personal finance tracking — statement ingestion and transaction management",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return structured JSON error instead of blank 500."""
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
    )


# All /api routes require authentication (when auth is enabled)
_auth = [Depends(verify_jwt)]

app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"], dependencies=_auth)
app.include_router(imports.router, prefix="/api/imports", tags=["imports"], dependencies=_auth)
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"], dependencies=_auth)
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"], dependencies=_auth)
app.include_router(budgets.router, prefix="/api/budgets", tags=["budgets"], dependencies=_auth)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    """Diagnostic endpoint to verify database connectivity and table presence."""
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected", "database": "healthy"}
    except Exception as e:
        return {"status": "error", "error_type": type(e).__name__, "detail": str(e)}

