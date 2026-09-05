"""Transaction model — canonical financial transaction record."""

import enum
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal

from sqlalchemy import (
    DateTime, Date, Enum, Float, ForeignKey, Index, Integer,
    Numeric, String, Text, Boolean, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.statement_import import StatementSource


class TransactionKind(str, enum.Enum):
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    REFUND = "REFUND"
    BANK_FEE = "BANK_FEE"
    INTEREST = "INTEREST"
    TAX = "TAX"
    UNKNOWN = "UNKNOWN"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[StatementSource] = mapped_column(
        Enum(StatementSource, name="statement_source_enum", create_type=False),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    statement_import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("statement_imports.id"), nullable=True
    )

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    description_clean: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Canonical signed amount: positive = money in, negative = money out
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False
    )
    debit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )
    credit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )

    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="NPR")
    balance_after: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )

    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transaction_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Future enrichment fields — nullable in Phase 1
    transaction_kind: Mapped[TransactionKind | None] = mapped_column(
        Enum(TransactionKind, name="transaction_kind_enum"), nullable=True
    )
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_internal_transfer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    classification_source: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    classification_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    classification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    account = relationship("Account", back_populates="transactions")
    statement_import = relationship("StatementImport", back_populates="transactions")

    __table_args__ = (
        # Duplicate protection: same account + same transaction fingerprint = same row
        UniqueConstraint("account_id", "transaction_hash", name="uq_account_transaction_hash"),
        Index("ix_transactions_account_id", "account_id"),
        Index("ix_transactions_transaction_date", "transaction_date"),
        Index("ix_transactions_transaction_hash", "transaction_hash"),
        Index("ix_transactions_statement_import_id", "statement_import_id"),
    )
