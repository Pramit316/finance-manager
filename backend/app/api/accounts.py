"""Account API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account, AccountType
from app.schemas.account import AccountCreate, AccountResponse

router = APIRouter()


@router.post("/", response_model=AccountResponse, status_code=201)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    """Create a new financial account."""
    try:
        account_type = AccountType(data.account_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid account type: {data.account_type}. Must be BANK or WALLET.",
        )

    account = Account(
        name=data.name,
        institution=data.institution,
        account_type=account_type,
        currency=data.currency,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/", response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    """List all active financial accounts."""
    return db.query(Account).filter(Account.is_active == True).all()


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a specific account by ID."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account
