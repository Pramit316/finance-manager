"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import accounts, imports, transactions, analytics, budgets

app = FastAPI(
    title="Personal Finance AI",
    description="Personal finance tracking — statement ingestion and transaction management",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(imports.router, prefix="/api/imports", tags=["imports"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["budgets"])


@app.get("/health")
def health():
    return {"status": "ok"}
