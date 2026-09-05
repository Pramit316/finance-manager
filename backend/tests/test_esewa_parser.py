"""eSewa parser tests.

Verifies:
- Correct sheet parsed
- 41 transactions returned
- Metadata excluded
- Total row excluded
- Summary rows excluded
- Debit is negative canonical amount
- Credit is positive canonical amount
- Decimal values used
- Source reference preserved
- Duplicate reference codes do not collapse rows
- Both 1ME7CUJ rows survive
- Both 1LY10GX rows survive
- Their fingerprints differ
- Balance validation succeeds
- Total debit = 8548.15
- Total credit = 8446.75
"""

from decimal import Decimal

import pytest

from app.parsers.esewa import EsewaStatementParser
from app.services.deduplication import compute_transaction_hash
from app.services.reconciliation import validate_running_balance


class TestEsewaParser:
    """Test suite for eSewa XLS statement parser."""

    @pytest.fixture(autouse=True)
    def setup(self, esewa_file_bytes, test_account_id):
        self.parser = EsewaStatementParser()
        self.result = self.parser.parse(esewa_file_bytes, "sample_esewa.xls")
        self.account_id = test_account_id

    def test_no_errors(self):
        """Parser should not produce errors for valid sample."""
        assert not self.result.errors, f"Parser errors: {self.result.errors}"

    def test_source(self):
        assert self.result.source == "ESEWA"

    def test_currency(self):
        assert self.result.currency == "NPR"

    def test_transaction_count(self):
        """Exactly 41 transactions should be parsed."""
        assert len(self.result.transactions) == 41

    def test_total_debit(self):
        """Total debit should equal 8548.15."""
        total_debit = sum(
            t.debit_amount for t in self.result.transactions if t.debit_amount
        )
        assert total_debit == Decimal("8548.15")

    def test_total_credit(self):
        """Total credit should equal 8446.75."""
        total_credit = sum(
            t.credit_amount for t in self.result.transactions if t.credit_amount
        )
        assert total_credit == Decimal("8446.75")

    def test_debit_is_negative(self):
        """All debit transactions should have negative canonical amount."""
        for txn in self.result.transactions:
            if txn.debit_amount and txn.debit_amount > 0:
                assert txn.amount < 0, (
                    f"Debit transaction should be negative: {txn.description_raw}"
                )

    def test_credit_is_positive(self):
        """All credit transactions should have positive canonical amount."""
        for txn in self.result.transactions:
            if txn.credit_amount and txn.credit_amount > 0:
                assert txn.amount > 0, (
                    f"Credit transaction should be positive: {txn.description_raw}"
                )

    def test_decimal_values(self):
        """All monetary values should be Decimal."""
        for txn in self.result.transactions:
            assert isinstance(txn.amount, Decimal)
            if txn.debit_amount is not None:
                assert isinstance(txn.debit_amount, Decimal)
            if txn.credit_amount is not None:
                assert isinstance(txn.credit_amount, Decimal)

    def test_source_reference_preserved(self):
        """All transactions should have a source reference."""
        for txn in self.result.transactions:
            assert txn.source_reference, (
                f"Missing reference for row {txn.source_row_number}"
            )

    def test_duplicate_reference_1ME7CUJ_not_collapsed(self):
        """Both rows with reference 1ME7CUJ must survive."""
        matches = [
            t for t in self.result.transactions if t.source_reference == "1ME7CUJ"
        ]
        assert len(matches) == 2, (
            f"Expected 2 rows with ref 1ME7CUJ, got {len(matches)}"
        )

    def test_duplicate_reference_1LY10GX_not_collapsed(self):
        """Both rows with reference 1LY10GX must survive."""
        matches = [
            t for t in self.result.transactions if t.source_reference == "1LY10GX"
        ]
        assert len(matches) == 2, (
            f"Expected 2 rows with ref 1LY10GX, got {len(matches)}"
        )

    def test_duplicate_reference_1ME7CUJ_different_fingerprints(self):
        """Rows with same reference 1ME7CUJ must have different fingerprints."""
        matches = [
            t for t in self.result.transactions if t.source_reference == "1ME7CUJ"
        ]
        assert len(matches) == 2
        hash1 = compute_transaction_hash(matches[0], self.account_id)
        hash2 = compute_transaction_hash(matches[1], self.account_id)
        assert hash1 != hash2, "Same reference but different transactions must have different hashes"

    def test_duplicate_reference_1LY10GX_different_fingerprints(self):
        """Rows with same reference 1LY10GX must have different fingerprints."""
        matches = [
            t for t in self.result.transactions if t.source_reference == "1LY10GX"
        ]
        assert len(matches) == 2
        hash1 = compute_transaction_hash(matches[0], self.account_id)
        hash2 = compute_transaction_hash(matches[1], self.account_id)
        assert hash1 != hash2, "Same reference but different transactions must have different hashes"

    def test_all_fingerprints_unique(self):
        """All 41 transactions should produce unique fingerprints."""
        hashes = set()
        for txn in self.result.transactions:
            h = compute_transaction_hash(txn, self.account_id)
            hashes.add(h)
        assert len(hashes) == 41, (
            f"Expected 41 unique hashes, got {len(hashes)}"
        )

    def test_running_balance(self):
        """Running balance validation should pass for eSewa sample."""
        # eSewa is newest-first. Derive opening balance from oldest transaction.
        txns = self.result.transactions
        if txns:
            oldest = txns[-1]  # Last in newest-first order
            opening = oldest.balance_after
            if oldest.debit_amount and oldest.debit_amount > 0:
                opening += oldest.debit_amount
            if oldest.credit_amount and oldest.credit_amount > 0:
                opening -= oldest.credit_amount

            errors = validate_running_balance(
                txns, opening_balance=opening, reverse_order=True
            )
            assert not errors, f"Running balance errors: {errors}"

    def test_metadata_excluded(self):
        """No metadata-like descriptions should appear as transactions."""
        for txn in self.result.transactions:
            desc_lower = txn.description_raw.lower()
            assert "statement report" not in desc_lower
            assert "from date" not in desc_lower
            assert "to date" not in desc_lower
            assert "generated on" not in desc_lower
