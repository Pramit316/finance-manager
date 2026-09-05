"""Nabil Bank PDF statement parser.

Geometry-based extraction using pdfplumber.
Uses verified x-boundaries to assign words to columns.
Reconstructs multi-line descriptions.
Handles 3-page statements with repeated headers.
Opening Balance is metadata, not a transaction.
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import pdfplumber

from app.parsers.base import ParsedStatement, ParsedTransaction, StatementParser

logger = logging.getLogger(__name__)

# Verified stable x-boundary regions for column assignment
COL_BOUNDARIES = {
    "sn": (40, 130),
    "date": (130, 260),
    "description": (260, 410),
    "withdraw": (410, 520),
    "deposit": (520, 650),
    "balance": (650, 770),
}


class NabilStatementParser(StatementParser):
    """Parser for Nabil Bank electronic PDF statements."""

    def parse(self, file_bytes: bytes, filename: str) -> ParsedStatement:
        result = ParsedStatement(source="NABIL", currency="NPR")

        try:
            pdf = pdfplumber.open(
                __import__("io").BytesIO(file_bytes)
            )
        except Exception as e:
            result.errors.append(f"Failed to open PDF: {str(e)}")
            return result

        all_transactions = []

        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=True,
            )

            # Extract metadata from the first page
            if page_num == 0:
                self._extract_metadata(words, result)

            # Assign words to columns based on x-coordinates
            page_rows = self._extract_transaction_rows(words)
            
            # Build logical transactions for this page
            page_txns = self._build_transactions(page_rows, result)
            all_transactions.extend(page_txns)

        pdf.close()

        result.transactions = all_transactions
        
        # Calculate totals
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        for txn in result.transactions:
            if txn.debit_amount:
                total_debit += txn.debit_amount
            if txn.credit_amount:
                total_credit += txn.credit_amount
        result.total_debit = total_debit
        result.total_credit = total_credit

        return result

    def _extract_metadata(self, words: list, result: ParsedStatement) -> None:
        """Extract statement-level metadata from first page words."""
        text_content = " ".join(w["text"] for w in words)

        # Account Number
        acct_match = re.search(r"Account\s*Number\s*[:\s]*(\d+)", text_content, re.IGNORECASE)
        if acct_match:
            result.account_number = acct_match.group(1)

        # From Date
        from_match = re.search(r"From\s*Date\s*[:\s]*(\d{4}[-/]\d{2}[-/]\d{2})", text_content)
        if from_match:
            result.period_from = self._parse_date_str(from_match.group(1))

        # To Date
        to_match = re.search(r"To\s*Date\s*[:\s]*(\d{4}[-/]\d{2}[-/]\d{2})", text_content)
        if to_match:
            result.period_to = self._parse_date_str(to_match.group(1))

        # Opening Balance
        ob_match = re.search(r"Opening\s*Balance\s*[:\s]*([\d,]+\.?\d*)", text_content)
        if ob_match:
            result.opening_balance = self._parse_decimal(ob_match.group(1))

        # Closing Balance (from metadata, not the transaction row)
        cb_match = re.search(r"Closing\s*Balance\s*[:\s]*([\d,]+\.?\d*)", text_content)
        if cb_match:
            result.closing_balance = self._parse_decimal(cb_match.group(1))

        # Currency
        currency_match = re.search(r"Currency\s*(?:Code)?\s*[:\s]*(NPR|USD|INR)", text_content)
        if currency_match:
            result.currency = currency_match.group(1)

    def _extract_transaction_rows(self, words: list) -> list[dict]:
        """Assign words to columns based on x-coordinates and group by y-position."""
        # Find table start (below 'S.N' header)
        table_top = 0
        for w in words:
            if w["text"] in ("S.N", "S.N."):
                if w["top"] > table_top:
                    table_top = w["top"]

        # Filter words to transaction region and assign columns
        column_words = []
        for w in words:
            # Skip words above or part of the header
            if w["top"] < table_top + 5:
                continue
            
            # Skip wide disclaimer text at the bottom
            if w["x1"] - w["x0"] > 200:
                continue
                
            x_center = (w["x0"] + w["x1"]) / 2
            col = self._assign_column(x_center)
            if col:
                column_words.append({
                    "text": w["text"],
                    "column": col,
                    "top": w["top"],
                    "x0": w["x0"],
                })

        # Group words by approximate y position (same visual line)
        if not column_words:
            return []

        # Sort by vertical position then horizontal
        column_words.sort(key=lambda w: (w["top"], w["x0"]))

        # Group into visual lines by y-proximity
        lines = []
        current_line = [column_words[0]]
        for w in column_words[1:]:
            if abs(w["top"] - current_line[-1]["top"]) < 5:
                current_line.append(w)
            else:
                lines.append(current_line)
                current_line = [w]
        if current_line:
            lines.append(current_line)

        # Convert lines into row dicts
        rows = []
        for line in lines:
            row = {"top": line[0]["top"]}
            for col_name in COL_BOUNDARIES:
                col_words = [w for w in line if w["column"] == col_name]
                if col_words:
                    row[col_name] = " ".join(w["text"] for w in col_words)
            rows.append(row)

        return rows

    def _assign_column(self, x: float) -> Optional[str]:
        """Map an x-coordinate to a column name."""
        for col_name, (x_min, x_max) in COL_BOUNDARIES.items():
            if x_min <= x <= x_max:
                return col_name
        return None

    def _build_transactions(
        self, rows: list[dict], result: ParsedStatement
    ) -> list[ParsedTransaction]:
        """Build logical transactions from raw rows, handling multi-line descriptions."""
        # 1. Identify all 'main' rows which contain a serial number
        main_rows = []
        for row in rows:
            print("ROW IN:", row)
            sn_text = row.get("sn", "").strip()
            if sn_text.isdigit():
                main_rows.append({
                    "sn_num": int(sn_text),
                    "top": row["top"],
                    "rows": [],
                })

        print("MAIN ROWS COUNT:", len(main_rows))
        if not main_rows:
            return []

        # 2. Assign every valid row to the closest main row vertically
        for row in rows:
            # Skip rows that are clearly not part of transactions
            desc_lower = row.get("description", "").lower()
            if "opening balance" in desc_lower or "closing balance" in desc_lower:
                continue
            
            sn_text = row.get("sn", "").strip().lower()
            if sn_text in ("s.n", "s.n.", "sn"):
                continue

            # Find closest main row
            closest_main = min(main_rows, key=lambda m: abs(m["top"] - row["top"]))
            closest_main["rows"].append(row)

        # 3. Build transactions
        transactions = []
        for m in main_rows:
            # Sort rows for this transaction top-to-bottom
            m["rows"].sort(key=lambda r: r["top"])
            
            date_text = None
            desc_parts = []
            withdraw = None
            deposit = None
            balance = None

            for r in m["rows"]:
                if "date" in r and r["date"].strip():
                    # We might get multiple fragments in date column, but date usually comes first
                    if not date_text:
                        date_text = r["date"].strip()

                if "description" in r and r["description"].strip():
                    desc_parts.append(r["description"].strip())

                w_text = r.get("withdraw", "").strip()
                if w_text and w_text != "-" and withdraw is None:
                    withdraw = self._parse_decimal(w_text)

                d_text = r.get("deposit", "").strip()
                if d_text and d_text != "-" and deposit is None:
                    deposit = self._parse_decimal(d_text)

                b_text = r.get("balance", "").strip()
                if b_text and b_text != "-" and balance is None:
                    balance = self._parse_decimal(b_text)

            if not date_text:
                continue

            txn_date = self._parse_date_str(date_text)
            if not txn_date:
                continue

            description_raw = " ".join(desc_parts)

            # Canonical amount
            amount = Decimal("0")
            if withdraw:
                amount = -withdraw
            elif deposit:
                amount = deposit

            raw_payload = {
                "sn": m["sn_num"],
                "date": date_text,
                "description": description_raw,
                "withdraw": str(withdraw) if withdraw else None,
                "deposit": str(deposit) if deposit else None,
                "balance": str(balance) if balance else None,
            }

            txn = ParsedTransaction(
                source="NABIL",
                transaction_date=txn_date,
                transaction_timestamp=None,
                description_raw=description_raw,
                debit_amount=withdraw,
                credit_amount=deposit,
                amount=amount,
                balance_after=balance,
                source_reference=None,
                source_row_number=m["sn_num"],
                raw_payload=raw_payload,
            )
            transactions.append(txn)

        return transactions

    def _finalize_transaction(
        self, data: dict, counter: int
    ) -> Optional[ParsedTransaction]:
        """Convert accumulated transaction data into a ParsedTransaction."""
        txn_date = self._parse_date_str(data["date_text"])
        if txn_date is None:
            return None

        description_raw = " ".join(data["description_parts"])
        withdraw = data.get("withdraw")
        deposit = data.get("deposit")
        balance = data.get("balance")

        # Canonical amount
        amount = Decimal("0")
        if withdraw:
            amount = -withdraw
        elif deposit:
            amount = deposit

        raw_payload = {
            "sn": data["sn"],
            "date": data["date_text"],
            "description": description_raw,
            "withdraw": str(withdraw) if withdraw else None,
            "deposit": str(deposit) if deposit else None,
            "balance": str(balance) if balance else None,
        }

        return ParsedTransaction(
            source="NABIL",
            transaction_date=txn_date,
            transaction_timestamp=None,  # Nabil only provides date
            description_raw=description_raw,
            debit_amount=withdraw,
            credit_amount=deposit,
            amount=amount,
            balance_after=balance,
            source_reference=None,  # Nabil doesn't provide reference codes
            source_row_number=data["sn"],
            raw_payload=raw_payload,
        )

    def _parse_date_str(self, text: str) -> Optional[date]:
        """Parse a date string to date object."""
        if not text:
            return None
        text = text.strip()
        text = text.split(" ")[0]  # Drop time portion if present
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_decimal(self, text: str) -> Optional[Decimal]:
        """Parse a text value to Decimal."""
        if not text or text.strip() in ("", "-"):
            return None
        try:
            return Decimal(text.strip().replace(",", ""))
        except (InvalidOperation, ValueError):
            return None
