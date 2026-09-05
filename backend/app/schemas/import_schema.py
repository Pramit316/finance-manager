"""Import result schemas."""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ImportResultResponse(BaseModel):
    import_id: uuid.UUID
    source: str
    status: str
    filename: str
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    currency: Optional[str] = None
    rows_read: int
    rows_parsed: int
    rows_inserted: int
    duplicate_rows: int
    invalid_rows: int
    total_debit: Optional[Decimal] = None
    total_credit: Optional[Decimal] = None
    reconciliation_status: str
    reconciliation_difference: Optional[Decimal] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
