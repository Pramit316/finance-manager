"""Transaction schemas."""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: uuid.UUID
    source: str
    account_id: uuid.UUID
    statement_import_id: Optional[uuid.UUID] = None
    transaction_date: date
    transaction_timestamp: Optional[datetime] = None
    description_raw: str
    description_clean: Optional[str] = None
    amount: Decimal
    debit_amount: Optional[Decimal] = None
    credit_amount: Optional[Decimal] = None
    currency: str
    balance_after: Optional[Decimal] = None
    source_reference: Optional[str] = None
    source_row_number: Optional[int] = None
    transaction_hash: str
    transaction_kind: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    is_internal_transfer: Optional[bool] = None
    transfer_group_id: Optional[uuid.UUID] = None
    classification_source: Optional[str] = None
    created_at: datetime
    is_manual: bool = False
    payment_method: Optional[str] = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    page: int
    page_size: int


class TransactionUpdate(BaseModel):
    transaction_kind: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    merchant: Optional[str] = None


class ManualTransactionCreate(BaseModel):
    account_id: uuid.UUID
    transaction_date: date
    description: str
    amount: Decimal
    direction: str
    category: str
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    payment_method: str
    notes: Optional[str] = None


class ManualTransactionUpdate(BaseModel):
    transaction_date: Optional[date] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    direction: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
