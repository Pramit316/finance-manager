"""FastAPI application entry point."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import verify_jwt
from app.config import settings
from app.api import accounts, imports, transactions, analytics, budgets

app = FastAPI(
    title="FinTrack API",
    description="Personal finance tracking — statement ingestion and transaction management",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

