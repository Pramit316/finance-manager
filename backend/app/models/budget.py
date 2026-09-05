"""Monthly planning models."""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AllocationType(str, enum.Enum):
    CONSUMPTION = "CONSUMPTION"
    INVESTMENT = "INVESTMENT"


class MonthlyBudget(Base):
    __tablename__ = "monthly_budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_income: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    planned_saving: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    allocations = relationship("BudgetAllocation", back_populates="budget", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("year", "month", name="uq_monthly_budget_year_month"),)


class BudgetAllocation(Base):
    __tablename__ = "budget_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monthly_budget_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("monthly_budgets.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    allocation_type: Mapped[AllocationType] = mapped_column(Enum(AllocationType, name="allocation_type_enum"), nullable=False, default=AllocationType.CONSUMPTION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    budget = relationship("MonthlyBudget", back_populates="allocations")
    __table_args__ = (UniqueConstraint("monthly_budget_id", "category", name="uq_budget_allocation_category"),)