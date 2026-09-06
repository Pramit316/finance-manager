"""Analytics service.

Calculates income, spending, cash flow, category totals, monthly trends,
and account balances.  All analytical queries use SQL aggregation — no
in-memory summing of full transaction sets.

Internal transfers are excluded from both income and spending totals
(both the +side and -side).  They appear only in the separate
internal_transfers metric.
"""

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, distinct

from app.models.account import Account
from app.models.transaction import Transaction, TransactionKind
from app.models.budget import MonthlyBudget, AllocationType
from app.services.filter_service import apply_transaction_filters

logger = logging.getLogger(__name__)

# Kinds that are excluded from income/spending totals
_EXCLUDED_FROM_INCOME_SPENDING = {TransactionKind.INTERNAL_TRANSFER}

# Kinds counted as spending
_SPENDING_KINDS = {
    TransactionKind.EXPENSE,
    TransactionKind.BANK_FEE,
    TransactionKind.TAX,
}


def _base_filtered_query(
    db: Session,
    *,
    date_from=None,
    date_to=None,
    account_id=None,
    source=None,
    transaction_kind=None,
    category=None,
    min_amount=None,
    max_amount=None,
    search=None,
):
    """Return a filtered Transaction query using the shared filter builder."""
    q = db.query(Transaction)
    return apply_transaction_filters(
        q,
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


def get_latest_account_balances(
    db: Session,
    *,
    account_id=None,
    source: str | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Calculate the latest known balance for each selected account.

    ``date_to`` is an as-of boundary for balances, rather than a transaction
    range boundary. This preserves the last known balance when an account has
    no transaction inside the dashboard's visible period.
    """
    account_query = db.query(Account).filter(Account.is_active == True)
    if account_id is not None:
        account_query = account_query.filter(Account.id == account_id)
    if source:
        account_query = account_query.filter(Account.institution == source)
    accounts = account_query.all()
    results = []

    for account in accounts:
        # Find the latest transaction that has a balance_after value
        txn_query = db.query(Transaction).filter(
            Transaction.account_id == account.id,
            Transaction.balance_after.isnot(None),
        )
        if date_to is not None:
            txn_query = txn_query.filter(Transaction.transaction_date <= date_to)

        latest_txn = (
            txn_query
            .order_by(
                Transaction.transaction_date.desc(),
                Transaction.transaction_timestamp.desc().nulls_last(),
                # Source row numbers represent statement order for sources
                # without transaction timestamps (for example Nabil PDF).
                Transaction.source_row_number.desc().nulls_last(),
                Transaction.id.desc(),
            )
            .first()
        )

        balance = latest_txn.balance_after if latest_txn else None
        balance_date = latest_txn.transaction_date if latest_txn else None

        results.append({
            "account_id": account.id,
            "account_name": account.name,
            "institution": account.institution,
            "currency": account.currency,
            "latest_balance": balance,
            "latest_balance_date": balance_date
        })

    return results


def get_analytics_summary(db: Session, **filters) -> dict:
    """Calculate summary totals using SQL aggregation.

    Internal transfers are excluded from income and spending.
    Both sides of a transfer cancel out (counted separately).
    """
    q = _base_filtered_query(db, **filters)

    row = q.with_entities(
        # Income: positive amounts that are NOT internal transfers
        func.coalesce(
            func.sum(
                case(
                    (
                        (Transaction.transaction_kind == TransactionKind.INCOME)
                        & (Transaction.is_internal_transfer.isnot(True))
                        & (Transaction.amount > 0),
                        Transaction.amount,
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        ).label("total_income"),
        # Spending: absolute value of negative amounts for EXPENSE/BANK_FEE/TAX
        func.coalesce(
            func.sum(
                case(
                    (
                        Transaction.transaction_kind.in_([
                            TransactionKind.EXPENSE,
                            TransactionKind.BANK_FEE,
                            TransactionKind.TAX,
                        ])
                        & (Transaction.is_internal_transfer.isnot(True))
                        & (Transaction.amount < 0),
                        func.abs(Transaction.amount),
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        ).label("total_spending"),
        # Internal transfers: count the negative side once per matched group.
        # A valid group has one outgoing and one incoming transaction.
        func.coalesce(
            func.sum(
                case(
                    (
                        (Transaction.transaction_kind == TransactionKind.INTERNAL_TRANSFER)
                        & (Transaction.amount < 0),
                        func.abs(Transaction.amount),
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        ).label("internal_transfers"),
        # Refunds (positive)
        func.coalesce(
            func.sum(
                case(
                    (
                        (Transaction.transaction_kind == TransactionKind.REFUND)
                        & (Transaction.is_internal_transfer.isnot(True))
                        & (Transaction.amount > 0),
                        Transaction.amount,
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        ).label("refunds"),
        # Bank fees
        func.coalesce(
            func.sum(
                case(
                    (
                        (Transaction.transaction_kind == TransactionKind.BANK_FEE)
                        & (Transaction.is_internal_transfer.isnot(True))
                        & (Transaction.amount < 0),
                        func.abs(Transaction.amount),
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        ).label("bank_fees"),
        # Tax
        func.coalesce(
            func.sum(
                case(
                    (
                        (Transaction.transaction_kind == TransactionKind.TAX)
                        & (Transaction.is_internal_transfer.isnot(True))
                        & (Transaction.amount < 0),
                        func.abs(Transaction.amount),
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        ).label("tax"),
        # Count
        func.count().label("transaction_count"),
    ).one()

    total_income = row.total_income
    total_spending = row.total_spending

    return {
        "total_income": total_income,
        "total_spending": total_spending,
        "net_cash_flow": total_income - total_spending,
        "internal_transfers": row.internal_transfers,
        "refunds": row.refunds,
        "bank_fees": row.bank_fees,
        "tax": row.tax,
        "transaction_count": row.transaction_count,
    }


def get_category_totals(db: Session, **filters) -> tuple[list[dict], Decimal]:
    """Calculate spending grouped by category.

    Returns (list_of_dicts, total_spending).
    """
    q = _base_filtered_query(db, **filters)

    # Only spending kinds
    q = q.filter(
        Transaction.transaction_kind.in_([
            TransactionKind.EXPENSE,
            TransactionKind.BANK_FEE,
            TransactionKind.TAX,
        ]),
        Transaction.is_internal_transfer.isnot(True),
        Transaction.amount < 0,
    )

    rows = (
        q.with_entities(
            func.coalesce(Transaction.category, "Uncategorized").label("cat"),
            func.sum(func.abs(Transaction.amount)).label("total"),
        )
        .group_by(func.coalesce(Transaction.category, "Uncategorized"))
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .all()
    )

    total = sum(r.total for r in rows) if rows else Decimal("0")
    results = []
    for r in rows:
        pct = float(r.total / total * 100) if total > 0 else 0.0
        results.append({"category": r.cat, "amount": r.total, "percentage": round(pct, 1)})

    return results, total


def get_income_by_category(db: Session, **filters) -> tuple[list[dict], Decimal]:
    """Income grouped by category."""
    q = _base_filtered_query(db, **filters)

    q = q.filter(
        Transaction.transaction_kind == TransactionKind.INCOME,
        Transaction.is_internal_transfer.isnot(True),
        Transaction.amount > 0,
    )

    rows = (
        q.with_entities(
            func.coalesce(Transaction.category, "Uncategorized").label("cat"),
            func.sum(Transaction.amount).label("total"),
        )
        .group_by(func.coalesce(Transaction.category, "Uncategorized"))
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    total = sum(r.total for r in rows) if rows else Decimal("0")
    results = []
    for r in rows:
        pct = float(r.total / total * 100) if total > 0 else 0.0
        results.append({"category": r.cat, "amount": r.total, "percentage": round(pct, 1)})

    return results, total


def get_spending_by_account(db: Session, **filters) -> tuple[list[dict], Decimal]:
    """Spending grouped by account."""
    q = _base_filtered_query(db, **filters)

    q = q.filter(
        Transaction.transaction_kind.in_([
            TransactionKind.EXPENSE,
            TransactionKind.BANK_FEE,
            TransactionKind.TAX,
        ]),
        Transaction.is_internal_transfer.isnot(True),
        Transaction.amount < 0,
    )

    rows = (
        q.join(Account, Transaction.account_id == Account.id)
        .with_entities(
            Account.id.label("account_id"),
            Account.name.label("account_name"),
            Account.institution.label("institution"),
            func.sum(func.abs(Transaction.amount)).label("total"),
        )
        .group_by(Account.id, Account.name, Account.institution)
        .order_by(func.sum(func.abs(Transaction.amount)).desc())
        .all()
    )

    total = sum(r.total for r in rows) if rows else Decimal("0")
    results = []
    for r in rows:
        pct = float(r.total / total * 100) if total > 0 else 0.0
        results.append({
            "account_id": r.account_id,
            "account_name": r.account_name,
            "institution": r.institution,
            "amount": r.total,
            "percentage": round(pct, 1),
        })

    return results, total


def get_monthly_trend(db: Session, **filters) -> list[dict]:
    """Monthly income/spending/net for a date range.

    Internal transfers excluded from income and spending.
    """
    q = _base_filtered_query(db, **filters)

    rows = (
        q.with_entities(
            extract("year", Transaction.transaction_date).label("yr"),
            extract("month", Transaction.transaction_date).label("mn"),
            # Income (excluding internal transfers)
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Transaction.transaction_kind == TransactionKind.INCOME)
                            & (Transaction.is_internal_transfer.isnot(True))
                            & (Transaction.amount > 0),
                            Transaction.amount,
                        ),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ).label("income"),
            # Spending
            func.coalesce(
                func.sum(
                    case(
                        (
                            Transaction.transaction_kind.in_([
                                TransactionKind.EXPENSE,
                                TransactionKind.BANK_FEE,
                                TransactionKind.TAX,
                            ])
                            & (Transaction.is_internal_transfer.isnot(True))
                            & (Transaction.amount < 0),
                            func.abs(Transaction.amount),
                        ),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ).label("spending"),
        )
        .group_by(
            extract("year", Transaction.transaction_date),
            extract("month", Transaction.transaction_date),
        )
        .order_by(
            extract("year", Transaction.transaction_date),
            extract("month", Transaction.transaction_date),
        )
        .all()
    )

    results = []
    for r in rows:
        month_str = f"{int(r.yr)}-{int(r.mn):02d}"
        results.append({
            "month": month_str,
            "income": r.income,
            "spending": r.spending,
            "net_cash_flow": r.income - r.spending,
        })

    return results


def get_unknown_transaction_count(db: Session, **filters) -> int:
    """Count of UNKNOWN / unclassified transactions."""
    q = _base_filtered_query(db, **filters)
    return q.filter(
        (Transaction.transaction_kind == TransactionKind.UNKNOWN)
        | (Transaction.transaction_kind.is_(None))
    ).count()


def get_distinct_categories(db: Session) -> list[str]:
    """Return all categories actually used in stored transactions."""
    rows = (
        db.query(distinct(Transaction.category))
        .filter(Transaction.category.isnot(None))
        .order_by(Transaction.category)
        .all()
    )
    return [r[0] for r in rows]


def get_budget_comparison(db: Session, year: int, month: int) -> dict:
    """Return deterministic planned-vs-actual figures for one calendar month."""
    budget = db.query(MonthlyBudget).filter(
        MonthlyBudget.year == year, MonthlyBudget.month == month
    ).first()
    if not budget:
        return None

    from calendar import monthrange
    date_from = date(year, month, 1)
    date_to = date(year, month, monthrange(year, month)[1])
    transactions = _base_filtered_query(db, date_from=date_from, date_to=date_to).all()
    genuine_income = sum(
        (t.amount for t in transactions
         if t.transaction_kind == TransactionKind.INCOME
         and t.is_internal_transfer is not True and t.amount > 0),
        Decimal("0"),
    )
    actual_investment = sum(
        (abs(t.amount) for t in transactions
         if t.category == "Investment" and t.amount < 0
         and t.transaction_kind != TransactionKind.INTERNAL_TRANSFER),
        Decimal("0"),
    )
    actual_by_category: dict[str, Decimal] = {}
    actual_consumption = Decimal("0")
    internal_transfers = Decimal("0")
    for txn in transactions:
        if txn.transaction_kind == TransactionKind.INTERNAL_TRANSFER and txn.amount < 0:
            internal_transfers += abs(txn.amount)
        if (
            txn.transaction_kind in _SPENDING_KINDS
            and txn.is_internal_transfer is not True
            and txn.amount < 0
        ):
            amount = abs(txn.amount)
            if txn.category != "Investment":
                actual_consumption += amount
                key = txn.category or "Uncategorized"
                actual_by_category[key] = actual_by_category.get(key, Decimal("0")) + amount

    planned_consumption = sum(
        (a.planned_amount for a in budget.allocations if a.allocation_type == AllocationType.CONSUMPTION),
        Decimal("0"),
    )
    planned_investment = sum(
        (a.planned_amount for a in budget.allocations if a.allocation_type == AllocationType.INVESTMENT),
        Decimal("0"),
    )
    # Keep an explicitly configured saving target, otherwise derive it from all allocations.
    planned_saving = budget.planned_saving
    if planned_saving is None:
        planned_saving = budget.expected_income - planned_consumption - planned_investment

    allocation_by_category = {a.category: a for a in budget.allocations}
    categories = set(allocation_by_category) | set(actual_by_category)
    comparisons = []
    for category in sorted(categories):
        allocation = allocation_by_category.get(category)
        planned = allocation.planned_amount if allocation else Decimal("0")
        actual = actual_by_category.get(category, Decimal("0"))
        variance = actual - planned
        comparisons.append({
            "category": category,
            "planned": planned,
            "actual": actual,
            "variance": variance,
            "percentage_used": float(actual / planned * 100) if planned else None,
            "status": "UNPLANNED" if not allocation and actual else (
                "OVER_PLAN" if variance > 0 else "ON_PLAN" if variance == 0 else "UNDER_PLAN"
            ),
            "allocation_type": allocation.allocation_type.value if allocation else "CONSUMPTION",
        })

    actual_saving = genuine_income - actual_consumption
    return {
        "year": year,
        "month": month,
        "planned_income": budget.expected_income,
        "actual_income": genuine_income,
        "income_variance": genuine_income - budget.expected_income,
        "planned_consumption": planned_consumption,
        "actual_consumption": actual_consumption,
        "consumption_variance": actual_consumption - planned_consumption,
        "planned_investment": planned_investment,
        "actual_investment": actual_investment,
        "investment_variance": actual_investment - planned_investment,
        "planned_saving": planned_saving,
        "actual_saving": actual_saving,
        "saving_variance": actual_saving - planned_saving,
        "internal_transfers": internal_transfers,
        "allocations": comparisons,
    }
