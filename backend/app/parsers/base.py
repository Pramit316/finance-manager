"""Base parser interface and parsed data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class ParsedTransaction:
    """A single parsed transaction from a source statement."""

    source: str
    transaction_date: date
    transaction_timestamp: Optional[datetime]
    description_raw: str
    debit_amount: Optional[Decimal]
    credit_amount: Optional[Decimal]
    amount: Decimal  # Canonical signed amount
    balance_after: Optional[Decimal]
    source_reference: Optional[str]
    source_row_number: Optional[int]
    raw_payload: Optional[dict[str, Any]] = None
    # Additional fields for fingerprinting
    channel: Optional[str] = None


@dataclass
class ParsedStatement:
    """Result of parsing a complete financial statement."""

    source: str
    account_number: Optional[str] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    currency: str = "NPR"
    total_debit: Optional[Decimal] = None
    total_credit: Optional[Decimal] = None
    transactions: list[ParsedTransaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class StatementParser(ABC):
    """Abstract base for source-specific statement parsers."""

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> ParsedStatement:
        """Parse a financial statement file and return structured data."""
        ...
