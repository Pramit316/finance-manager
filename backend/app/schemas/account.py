"""Account schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str
    account_number: str | None = None
    institution: str
    account_type: str  # BANK or WALLET
    currency: str = "NPR"


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    account_number: str | None = None
    institution: str
    account_type: str
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
