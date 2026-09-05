"""Transaction API endpoints."""

import uuid
import hashlib
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transaction import Transaction, TransactionKind
from app.models.account import Account
from app.models.statement_import import StatementSource
from app.schemas.transaction import (
    TransactionListResponse, TransactionResponse, TransactionUpdate,
    ManualTransactionCreate, ManualTransactionUpdate,
)
from app.services import classification, internal_transfer
from app.services.filter_service import apply_transaction_filters

router = APIRouter()

_PAYMENT_METHODS = {"CASH", "MANUAL_OTHER"}


def _manual_amount(amount: Decimal, direction: str) -> Decimal:
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be greater than zero")
    if direction not in {"EXPENSE", "INCOME"}:
        raise HTTPException(status_code=422, detail="Direction must be EXPENSE or INCOME")
    return -abs(amount) if direction == "EXPENSE" else abs(amount)


def _validate_payment_method(payment_method: str) -> None:
    if payment_method not in _PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="Payment method must be CASH or MANUAL_OTHER")


@router.post("/manual", response_model=TransactionResponse, status_code=201)
def create_manual_transaction(data: ManualTransactionCreate, db: Session = Depends(get_db)):
    """Create a user-entered transaction in the canonical transaction table."""
    account = db.query(Account).filter(Account.id == data.account_id, Account.is_active == True).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    _validate_payment_method(data.payment_method)
    amount = _manual_amount(data.amount, data.direction)
    fingerprint = hashlib.sha256(
        f"manual:{uuid.uuid4()}".encode()
    ).hexdigest()
    txn = Transaction(
        source=StatementSource.MANUAL,
        account_id=account.id,
        transaction_date=data.transaction_date,
        description_raw=data.description,
        description_clean=data.description,
        amount=amount,
        currency=account.currency,
        transaction_hash=fingerprint,
        transaction_kind=TransactionKind(data.direction),
        category=data.category,
        subcategory=data.subcategory,
        merchant=data.merchant,
        classification_source="USER",
        classification_confidence=1.0,
        classification_reason="Manual transaction",
        is_manual=True,
        payment_method=data.payment_method,
        raw_payload={"notes": data.notes} if data.notes else None,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.patch("/manual/{transaction_id}", response_model=TransactionResponse)
def update_manual_transaction(transaction_id: uuid.UUID, data: ManualTransactionUpdate, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not txn.is_manual or txn.source != StatementSource.MANUAL:
        raise HTTPException(status_code=403, detail="Imported transaction financial fields cannot be edited")
    if data.payment_method is not None:
        _validate_payment_method(data.payment_method)
        txn.payment_method = data.payment_method
    if data.transaction_date is not None:
        txn.transaction_date = data.transaction_date
    if data.description is not None:
        txn.description_raw = data.description
        txn.description_clean = data.description
    if data.amount is not None or data.direction is not None:
        direction = data.direction or ("INCOME" if txn.amount >= 0 else "EXPENSE")
        txn.amount = _manual_amount(data.amount if data.amount is not None else abs(txn.amount), direction)
        txn.transaction_kind = TransactionKind(direction)
    if data.direction is not None:
        txn.transaction_kind = TransactionKind(data.direction)
    for field in ("category", "subcategory", "merchant"):
        value = getattr(data, field)
        if value is not None:
            setattr(txn, field, value)
    if data.notes is not None:
        txn.raw_payload = {"notes": data.notes}
    txn.classification_source = "USER"
    txn.classification_confidence = 1.0
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/manual/{transaction_id}", status_code=204)
def delete_manual_transaction(transaction_id: uuid.UUID, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not txn.is_manual or txn.source != StatementSource.MANUAL:
        raise HTTPException(status_code=403, detail="Imported transactions cannot be deleted here")
    db.delete(txn)
    db.commit()


@router.get("/", response_model=TransactionListResponse)
def list_transactions(
    account_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    source: Optional[str] = Query(None),
    transaction_kind: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[Decimal] = Query(None),
    max_amount: Optional[Decimal] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List transactions with optional filtering and pagination."""
    query = db.query(Transaction)
    
    query = apply_transaction_filters(
        query,
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

    total = query.count()

    transactions = (
        query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return TransactionListResponse(
        transactions=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """Manually update transaction classification fields."""
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if data.transaction_kind is not None:
        txn.transaction_kind = TransactionKind(data.transaction_kind)
    if data.category is not None:
        txn.category = data.category
    if data.subcategory is not None:
        txn.subcategory = data.subcategory
    if data.merchant is not None:
        txn.merchant = data.merchant
        
    # Mark as user overridden
    txn.classification_source = "USER"
    txn.classification_confidence = 1.0
    txn.classification_reason = "Manual override"
    
    db.commit()
    db.refresh(txn)
    return txn


@router.post("/run-classification")
def run_automatic_classification(db: Session = Depends(get_db)):
    """Run deterministic classification on unclassified transactions."""
    result = classification.run_classification(db)
    return result


@router.post("/reclassify-all")
def reclassify_all_transactions(db: Session = Depends(get_db)):
    """Safely run classification on all existing transactions (skips USER overrides)."""
    result = internal_transfer.repair_and_match_transfers(db)
    return result


@router.post("/match-transfers")
def match_internal_transfers_endpoint(db: Session = Depends(get_db)):
    """Run internal transfer matching between accounts."""
    result = internal_transfer.match_internal_transfers(db)
    return result
