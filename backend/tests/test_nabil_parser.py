"""Nabil Bank PDF parser tests.

Verifies:
- PDF has 3 pages
- 24 transactions parsed
- S.N sequence 1-24
- Opening Balance excluded from transactions
- From Date = 2026-07-10
- To Date = 2026-08-09
- Opening Balance = 266744.21
- Closing Balance = 215366.99
- Currency = NPR
- Multi-line descriptions reconstructed
- Withdrawal produces negative amount
- Deposit produces positive amount
- Total deposits = 12475.30
- Total withdrawals = 63852.52
- Running balance passes
- Statement reconciliation difference = 0.00
"""

from decimal import Decimal
from datetime import date

import pdfplumber
import pytest

from app.parsers.nabil import NabilStatementParser
from app.services.deduplication import compute_transaction_hash
from app.services.reconciliation import reconcile_statement, validate_running_balance


class TestNabilParser:
    """Test suite for Nabil Bank PDF statement parser."""

    @pytest.fixture(autouse=True)
    def setup(self, nabil_file_bytes, test_account_id):
        self.parser = NabilStatementParser()
        self.result = self.parser.parse(nabil_file_bytes, "sample_nabil.pdf")
        self.file_bytes = nabil_file_bytes
        self.account_id = test_account_id

    def test_no_errors(self):
        """Parser should not produce errors for valid sample."""
        assert not self.result.errors, f"Parser errors: {self.result.errors}"

    def test_pdf_has_3_pages(self):
        """PDF should have 3 pages."""
        import io
        pdf = pdfplumber.open(io.BytesIO(self.file_bytes))
        assert len(pdf.pages) == 3
        pdf.close()

    def test_source(self):
        assert self.result.source == "NABIL"

    def test_currency(self):
        assert self.result.currency == "NPR"

    def test_transaction_count(self):
        """Exactly 24 transactions should be parsed."""
        assert len(self.result.transactions) == 24

    def test_serial_number_sequence(self):
        """S.N should be 1 through 24."""
        sn_values = [t.source_row_number for t in self.result.transactions]
        assert sn_values == list(range(1, 25))

    def test_opening_balance_excluded(self):
        """Opening Balance row must not appear as a transaction."""
        for txn in self.result.transactions:
            assert "opening balance" not in txn.description_raw.lower()

    def test_from_date(self):
        """From Date should be 2026-07-10."""
        assert self.result.period_from == date(2026, 7, 10)

    def test_to_date(self):
        """To Date should be 2026-08-09."""
        assert self.result.period_to == date(2026, 8, 9)

    def test_opening_balance(self):
        """Opening Balance should be 266744.21."""
        assert self.result.opening_balance == Decimal("266744.21")

    def test_closing_balance(self):
        """Closing Balance should be 215366.99."""
        assert self.result.closing_balance == Decimal("215366.99")

    def test_withdrawal_negative(self):
        """Withdrawals should produce negative canonical amounts."""
        for txn in self.result.transactions:
            if txn.debit_amount and txn.debit_amount > 0:
                assert txn.amount < 0, (
                    f"Withdrawal should be negative: {txn.description_raw}"
                )

    def test_deposit_positive(self):
        """Deposits should produce positive canonical amounts."""
        for txn in self.result.transactions:
            if txn.credit_amount and txn.credit_amount > 0:
                assert txn.amount > 0, (
                    f"Deposit should be positive: {txn.description_raw}"
                )

    def test_total_deposits(self):
        """Total deposits should equal 12475.30."""
        total_deposits = sum(
            t.credit_amount for t in self.result.transactions if t.credit_amount
        )
        assert total_deposits == Decimal("12475.30")

    def test_total_withdrawals(self):
        """Total withdrawals should equal 63852.52."""
        total_withdrawals = sum(
            t.debit_amount for t in self.result.transactions if t.debit_amount
        )
        assert total_withdrawals == Decimal("63852.52")

    def test_reconciliation_difference_zero(self):
        """Statement reconciliation difference should be 0.00."""
        recon = reconcile_statement(self.result)
        assert recon.difference == Decimal("0.00"), (
            f"Reconciliation difference: {recon.difference}"
        )
        assert recon.passed

    def test_running_balance(self):
        """Running balance validation should pass."""
        errors = validate_running_balance(
            self.result.transactions,
            opening_balance=self.result.opening_balance,
            reverse_order=False,
        )
        assert not errors, f"Running balance errors: {errors}"

    def test_multi_line_descriptions(self):
        """Descriptions should be reconstructed from multiple visual lines."""
        # Verify at least some descriptions contain multiple words/fragments
        descriptions = [t.description_raw for t in self.result.transactions]
        long_descriptions = [d for d in descriptions if len(d) > 20]
        assert len(long_descriptions) > 0, "Expected some multi-part descriptions"

    def test_all_fingerprints_unique(self):
        """All 24 transactions should produce unique fingerprints."""
        hashes = set()
        for txn in self.result.transactions:
            h = compute_transaction_hash(txn, self.account_id)
            hashes.add(h)
        assert len(hashes) == 24, (
            f"Expected 24 unique hashes, got {len(hashes)}"
        )

    def test_decimal_values(self):
        """All monetary values should be Decimal."""
        for txn in self.result.transactions:
            assert isinstance(txn.amount, Decimal)
            if txn.debit_amount is not None:
                assert isinstance(txn.debit_amount, Decimal)
            if txn.credit_amount is not None:
                assert isinstance(txn.credit_amount, Decimal)
            if txn.balance_after is not None:
                assert isinstance(txn.balance_after, Decimal)
