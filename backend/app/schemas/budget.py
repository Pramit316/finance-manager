import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class BudgetAllocationInput(BaseModel):
    category: str = Field(min_length=1, max_length=255)
    planned_amount: Decimal = Field(ge=0)
    allocation_type: str = "CONSUMPTION"


class BudgetCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    expected_income: Decimal = Field(ge=0)
    planned_saving: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = None
    allocations: list[BudgetAllocationInput] = Field(default_factory=list)


class BudgetUpdate(BaseModel):
    expected_income: Optional[Decimal] = Field(default=None, ge=0)
    planned_saving: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = None
    allocations: Optional[list[BudgetAllocationInput]] = None


class BudgetAllocationResponse(BudgetAllocationInput):
    id: uuid.UUID


class BudgetResponse(BaseModel):
    id: uuid.UUID
    year: int
    month: int
    expected_income: Decimal
    planned_saving: Optional[Decimal]
    notes: Optional[str]
    allocations: list[BudgetAllocationResponse]

    model_config = {"from_attributes": True}