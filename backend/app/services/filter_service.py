"""Shared transaction filter builder.

Provides a single reusable function that applies filter parameters to a
SQLAlchemy query over the Transaction model.  Used by:
- transaction list endpoint
- all analytics endpoints

This ensures consistent filtering logic across the application.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Query

from app.models.transaction import Transaction, TransactionKind


def apply_transaction_filters(
    query: Query,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    account_id: Optional[uuid.UUID] = None,
    source: Optional[str] = None,
    transaction_kind: Optional[str] = None,
    category: Optional[str] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    search: Optional[str] = None,
) -> Query:
    """Apply standard filters to a Transaction query.

    Parameters
    ----------
    query : Query
        An existing SQLAlchemy query on Transaction (or joined model).
    date_from / date_to : date, optional
        Inclusive date range filter on transaction_date.
    account_id : UUID, optional
        Filter to a single account.
    source : str, optional
        Filter by statement source (e.g. "ESEWA", "NABIL").
    transaction_kind : str, optional
        Comma-separated transaction kinds (e.g. "EXPENSE,INCOME").
    category : str, optional
        Exact category match.
    min_amount / max_amount : Decimal, optional
        Filter by absolute amount range (applies to abs(amount)).
    search : str, optional
        Case-insensitive search across description_raw, merchant,
        and source_reference.
    """
    if date_from is not None:
        query = query.filter(Transaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.filter(Transaction.transaction_date <= date_to)
    if account_id is not None:
        query = query.filter(Transaction.account_id == account_id)
    if source:
        query = query.filter(Transaction.source == source)
    if transaction_kind:
        kinds = [k.strip() for k in transaction_kind.split(",") if k.strip()]
        if len(kinds) == 1:
            try:
                query = query.filter(
                    Transaction.transaction_kind == TransactionKind(kinds[0])
                )
            except ValueError:
                pass  # Invalid kind — skip filter
        elif kinds:
            valid_kinds = []
            for k in kinds:
                try:
                    valid_kinds.append(TransactionKind(k))
                except ValueError:
                    pass
            if valid_kinds:
                query = query.filter(Transaction.transaction_kind.in_(valid_kinds))
    if category:
        query = query.filter(Transaction.category == category)
    if min_amount is not None:
        from sqlalchemy import func
        query = query.filter(func.abs(Transaction.amount) >= min_amount)
    if max_amount is not None:
        from sqlalchemy import func
        query = query.filter(func.abs(Transaction.amount) <= max_amount)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Transaction.description_raw.ilike(pattern),
                Transaction.merchant.ilike(pattern),
                Transaction.source_reference.ilike(pattern),
            )
        )
    return query
