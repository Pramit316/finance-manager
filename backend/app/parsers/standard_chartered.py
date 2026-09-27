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
                tables = page.extract_tables()
                for table in tables:
                    if not table or not self._is_transaction_table(table[0]):
                        continue
                    
                    # Determine column indices from header
                    header = [str(value or "").strip().lower() for value in table[0]]
                    col_map = {}
                    for i, col in enumerate(header):
                        if col in ["date", "txn date", "value date"]:
                            col_map["date"] = i
                        elif col in ["description", "particulars", "details", "transaction details"]:
                            col_map["description"] = i
                        elif col in ["withdrawal", "withdrawals", "debit"]:
                            col_map["withdrawal"] = i
                        elif col in ["deposit", "deposits", "credit"]:
                            col_map["deposit"] = i
                        elif col in ["balance"]:
                            col_map["balance"] = i
                            
                    for row_number, row in enumerate(table[1:], start=1):
                        transaction = self._parse_row(row, row_number, col_map)
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
        normalized = [str(value or "").strip().lower() for value in header]
        
        has_date = any(w in normalized for w in ["date", "txn date", "value date"])
        has_desc = any(w in normalized for w in ["description", "particulars", "details", "transaction details"])
        has_withdraw = any(w in normalized for w in ["withdrawal", "withdrawals", "debit"])
        has_deposit = any(w in normalized for w in ["deposit", "deposits", "credit"])
        has_balance = any(w in normalized for w in ["balance"])
        
        return has_date and has_desc and (has_withdraw or has_deposit) and has_balance

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

    def _parse_row(self, row: list[str | None], row_number: int, col_map: dict[str, int]) -> Optional[ParsedTransaction]:
        if not col_map:
            return None
            
        date_idx = col_map.get("date")
        desc_idx = col_map.get("description")
        withdraw_idx = col_map.get("withdrawal")
        deposit_idx = col_map.get("deposit")
        balance_idx = col_map.get("balance")
        
        # Ensure we don't go out of bounds
        def get_val(idx: Optional[int]) -> str | None:
            if idx is not None and idx < len(row):
                return row[idx]
            return None
            
        date_val = get_val(date_idx)
        if not date_val or not self._DATE_RE.match(date_val.strip()):
            return None
            
        transaction_date = self._parse_date(date_val.strip())
        description = " ".join((get_val(desc_idx) or "").split())
        withdrawal = self._decimal(get_val(withdraw_idx))
        deposit = self._decimal(get_val(deposit_idx))
        balance = self._decimal(get_val(balance_idx))
        
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
                "date": date_val, 
                "description": get_val(desc_idx), 
                "withdrawal": get_val(withdraw_idx),
                "deposit": get_val(deposit_idx), 
                "balance": get_val(balance_idx),
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