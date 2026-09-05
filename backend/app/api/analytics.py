"""Analytics API endpoints."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analytics import (
    AccountBalanceResponse,
    AnalyticsCategoriesResponse,
    AnalyticsSummaryResponse,
    MonthlyTrendResponse,
    SpendingByAccountResponse,
    IncomeByCategoryResponse,
    UnknownCountResponse,
    DistinctCategoriesResponse,
)
from app.services import analytics

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_summary(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    account_id: Optional[uuid.UUID] = Query(None),
    source: Optional[str] = Query(None),
    transaction_kind: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[Decimal] = Query(None),
    max_amount: Optional[Decimal] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get financial summary (income, spending, cash flow)."""
    return analytics.get_analytics_summary(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source=source,
        transaction_kind=transaction_kind,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )


@router.get("/categories", response_model=AnalyticsCategoriesResponse)
def get_categories(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    account_id: Optional[uuid.UUID] = Query(None),
    source: Optional[str] = Query(None),
    transaction_kind: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[Decimal] = Query(None),
    max_amount: Optional[Decimal] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get spending grouped by category."""
    totals, grand_total = analytics.get_category_totals(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source=source,
        transaction_kind=transaction_kind,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )
    return AnalyticsCategoriesResponse(categories=totals, total=grand_total)


@router.get("/income-categories", response_model=IncomeByCategoryResponse)
def get_income_categories(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    account_id: Optional[uuid.UUID] = Query(None),
    source: Optional[str] = Query(None),
    transaction_kind: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[Decimal] = Query(None),
    max_amount: Optional[Decimal] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get income grouped by category."""
    totals, grand_total = analytics.get_income_by_category(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source=source,
        transaction_kind=transaction_kind,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )
    return IncomeByCategoryResponse(categories=totals, total=grand_total)


@router.get("/spending-by-account", response_model=SpendingByAccountResponse)
def get_spending_by_account(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    account_id: Optional[uuid.UUID] = Query(None),
    source: Optional[str] = Query(None),
    transaction_kind: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[Decimal] = Query(None),
    max_amount: Optional[Decimal] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get spending grouped by account."""
    totals, grand_total = analytics.get_spending_by_account(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source=source,
        transaction_kind=transaction_kind,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )
    return SpendingByAccountResponse(accounts=totals, total=grand_total)


@router.get("/monthly-trend", response_model=MonthlyTrendResponse)
def get_monthly_trend(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    account_id: Optional[uuid.UUID] = Query(None),
    source: Optional[str] = Query(None),
    transaction_kind: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[Decimal] = Query(None),
    max_amount: Optional[Decimal] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get monthly trend of income and spending."""
    trend = analytics.get_monthly_trend(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source=source,
        transaction_kind=transaction_kind,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )
    return MonthlyTrendResponse(months=trend)


@router.get("/unknown-count", response_model=UnknownCountResponse)
def get_unknown_count(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    account_id: Optional[uuid.UUID] = Query(None),
    source: Optional[str] = Query(None),
    transaction_kind: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[Decimal] = Query(None),
    max_amount: Optional[Decimal] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get count of unclassified transactions."""
    count = analytics.get_unknown_transaction_count(
        db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source=source,
        transaction_kind=transaction_kind,
        category=category,
        min_amount=min_amount,
        max_amount=max_amount,
        search=search,
    )
    return UnknownCountResponse(count=count)


@router.get("/distinct-categories", response_model=DistinctCategoriesResponse)
def get_distinct_categories(db: Session = Depends(get_db)):
    """Get all distinct categories in use."""
    categories = analytics.get_distinct_categories(db)
    return DistinctCategoriesResponse(categories=categories)


@router.get("/accounts", response_model=list[AccountBalanceResponse])
def get_account_balances(db: Session = Depends(get_db)):
    """Get latest balance for all active accounts."""
    return analytics.get_latest_account_balances(db)


@router.get("/budget")
def get_budget_comparison(year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12), db: Session = Depends(get_db)):
    result = analytics.get_budget_comparison(db, year, month)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Budget not found")
    return result

