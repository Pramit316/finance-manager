"""Analytics schemas."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class AccountBalanceResponse(BaseModel):
    account_id: uuid.UUID
    account_name: str
    institution: str
    currency: str
    latest_balance: Optional[Decimal]
    latest_balance_date: Optional[date]


class AnalyticsSummaryResponse(BaseModel):
    total_income: Decimal
    total_spending: Decimal
    net_cash_flow: Decimal
    internal_transfers: Decimal
    refunds: Decimal
    bank_fees: Decimal
    tax: Decimal
    transaction_count: int


class CategoryTotal(BaseModel):
    category: str
    amount: Decimal
    percentage: Optional[float] = None


class AnalyticsCategoriesResponse(BaseModel):
    categories: list[CategoryTotal]
    total: Optional[Decimal] = None


class MonthlyTrendItem(BaseModel):
    month: str  # "2026-07" format
    income: Decimal
    spending: Decimal
    net_cash_flow: Decimal


class MonthlyTrendResponse(BaseModel):
    months: list[MonthlyTrendItem]


class SpendingByAccountItem(BaseModel):
    account_id: uuid.UUID
    account_name: str
    institution: str
    amount: Decimal
    percentage: Optional[float] = None


class SpendingByAccountResponse(BaseModel):
    accounts: list[SpendingByAccountItem]
    total: Optional[Decimal] = None


class IncomeByCategoryItem(BaseModel):
    category: str
    amount: Decimal
    percentage: Optional[float] = None


class IncomeByCategoryResponse(BaseModel):
    categories: list[IncomeByCategoryItem]
    total: Optional[Decimal] = None


class UnknownCountResponse(BaseModel):
    count: int


class DistinctCategoriesResponse(BaseModel):
    categories: list[str]
