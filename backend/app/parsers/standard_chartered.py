"""Standard Chartered transaction-history PDF parser."""

import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import pdfplumber

from app.parsers.base import ParsedStatement, ParsedTransaction, StatementParser


class StandardCharteredStatementParser(StatementParser):
    """Parse the embedded-text Standard Chartered transaction table."""

    _DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

    def parse(self, file_bytes: bytes, filename: str) -> ParsedStatement:
        result = ParsedStatement(source="STANDARD_CHARTERED", currency="NPR")
        try:
            pdf = pdfplumber.open(io.BytesIO(file_bytes))
        except Exception as exc:
            result.errors.append(f"Failed to open PDF: {exc}")
            return result

        try:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            self._extract_metadata(text, result)
            transactions = []
            for page in pdf.pages:
                table = page.extract_table()
                if not table or not self._is_transaction_table(table[0]):
                    continue
                for row_number, row in enumerate(table[1:], start=1):
                    transaction = self._parse_row(row, row_number)
                    if transaction:
                        transactions.append(transaction)
            if not transactions:
                result.errors.append("Could not locate Standard Chartered transaction table")
            result.transactions = transactions
            result.total_debit = sum((t.debit_amount or Decimal("0") for t in transactions), Decimal("0"))
            result.total_credit = sum((t.credit_amount or Decimal("0") for t in transactions), Decimal("0"))
        finally:
            pdf.close()
        return result

    def _is_transaction_table(self, header: list[str | None]) -> bool:
        normalized = {str(value or "").strip().lower() for value in header}
        return {"date", "description", "withdrawal", "deposit", "balance"}.issubset(normalized)

    def _extract_metadata(self, text: str, result: ParsedStatement) -> None:
        period = re.search(r"from\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        if period:
            result.period_from = self._parse_date(period.group(1))
            result.period_to = self._parse_date(period.group(2))
        account = re.search(r"Account Number\s+(\d+)", text, re.IGNORECASE)
        if account:
            result.account_number = account.group(1)
        currency = re.search(r"Account Currency\s+([A-Z]{3})", text, re.IGNORECASE)
        if currency:
            result.currency = currency.group(1).upper()
        available = re.search(r"Available Balance\s+([\d,]+\.\d{2})", text, re.IGNORECASE)
        if available:
            result.closing_balance = self._decimal(available.group(1))

    def _parse_row(self, row: list[str | None], row_number: int) -> Optional[ParsedTransaction]:
        if len(row) < 5 or not row[0] or not self._DATE_RE.match(row[0].strip()):
            return None
        transaction_date = self._parse_date(row[0].strip())
        description = " ".join((row[1] or "").split())
        withdrawal = self._decimal(row[2])
        deposit = self._decimal(row[3])
        balance = self._decimal(row[4])
        if transaction_date is None or (withdrawal is None and deposit is None):
            return None
        amount = -withdrawal if withdrawal is not None else deposit
        return ParsedTransaction(
            source="STANDARD_CHARTERED",
            transaction_date=transaction_date,
            transaction_timestamp=None,
            description_raw=description,
            debit_amount=withdrawal,
            credit_amount=deposit,
            amount=amount,
            balance_after=balance,
            source_reference=None,
            source_row_number=row_number,
            raw_payload={
                "date": row[0], "description": row[1], "withdrawal": row[2],
                "deposit": row[3], "balance": row[4],
            },
        )

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        try:
            return datetime.strptime(value, "%d/%m/%Y").date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _decimal(value: str | None) -> Optional[Decimal]:
        if not value or value.strip() in {"", "-"}:
            return None
        try:
            return Decimal(value.strip().replace(",", ""))
        except (InvalidOperation, ValueError):
            return None