"""StatementImport model — tracks each uploaded statement file and its processing results."""

import enum
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal

from sqlalchemy import (
    DateTime, Date, Enum, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    IMPORTED = "IMPORTED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ReconciliationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class StatementSource(str, enum.Enum):
    ESEWA = "ESEWA"
    NABIL = "NABIL"
    STANDARD_CHARTERED = "STANDARD_CHARTERED"
    MANUAL = "MANUAL"
    GMAIL_TRANSACTION_ALERT = "GMAIL_TRANSACTION_ALERT"


class StatementImport(Base):
    __tablename__ = "statement_imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[StatementSource] = mapped_column(
        Enum(StatementSource, name="statement_source_enum"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    opening_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )
    closing_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    rows_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_debit: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )
    total_credit: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )

    reconciliation_difference: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, name="reconciliation_status_enum"),
        nullable=False,
        default=ReconciliationStatus.PENDING,
    )

    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status_enum"),
        nullable=False,
        default=ImportStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    account = relationship("Account", back_populates="statement_imports")
    transactions = relationship("Transaction", back_populates="statement_import")
