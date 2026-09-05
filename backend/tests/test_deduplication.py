"""Deduplication service tests."""

from decimal import Decimal
from datetime import date, datetime, timezone

import pytest

from app.parsers.base import ParsedTransaction
from app.services.deduplication import compute_transaction_hash


class TestDeduplication:
    """Test fingerprint/deduplication logic."""

    def _make_esewa_txn(self, **kwargs):
        defaults = {
            "source": "ESEWA",
            "transaction_date": date(2026, 8, 1),
            "transaction_timestamp": datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
            "description_raw": "Test payment",
            "debit_amount": Decimal("100"),
            "credit_amount": None,
            "amount": Decimal("-100"),
            "balance_after": Decimal("500"),
            "source_reference": "ABC123",
            "source_row_number": 1,
            "channel": "Web",
        }
        defaults.update(kwargs)
        return ParsedTransaction(**defaults)

    def test_same_transaction_same_hash(self):
        """Identical transactions should produce the same hash."""
        txn1 = self._make_esewa_txn()
        txn2 = self._make_esewa_txn()
        account_id = "test-account"
        assert compute_transaction_hash(txn1, account_id) == compute_transaction_hash(txn2, account_id)

    def test_different_amount_different_hash(self):
        """Different amounts should produce different hashes."""
        txn1 = self._make_esewa_txn(debit_amount=Decimal("100"), amount=Decimal("-100"))
        txn2 = self._make_esewa_txn(debit_amount=Decimal("200"), amount=Decimal("-200"))
        account_id = "test-account"
        assert compute_transaction_hash(txn1, account_id) != compute_transaction_hash(txn2, account_id)

    def test_same_reference_different_description_different_hash(self):
        """Same reference but different description should produce different hashes."""
        txn1 = self._make_esewa_txn(description_raw="Payment A")
        txn2 = self._make_esewa_txn(description_raw="Payment B")
        account_id = "test-account"
        assert compute_transaction_hash(txn1, account_id) != compute_transaction_hash(txn2, account_id)

    def test_different_account_different_hash(self):
        """Same transaction on different accounts should produce different hashes."""
        txn = self._make_esewa_txn()
        hash1 = compute_transaction_hash(txn, "account-1")
        hash2 = compute_transaction_hash(txn, "account-2")
        assert hash1 != hash2

    def test_nabil_description_normalization(self):
        """Nabil hashes should normalize whitespace in descriptions."""
        txn1 = ParsedTransaction(
            source="NABIL",
            transaction_date=date(2026, 8, 1),
            transaction_timestamp=None,
            description_raw="MPAY\nLXBLNPKA;16615826630",
            debit_amount=Decimal("100"),
            credit_amount=None,
            amount=Decimal("-100"),
            balance_after=Decimal("500"),
            source_reference=None,
            source_row_number=1,
        )
        txn2 = ParsedTransaction(
            source="NABIL",
            transaction_date=date(2026, 8, 1),
            transaction_timestamp=None,
            description_raw="MPAY LXBLNPKA;16615826630",
            debit_amount=Decimal("100"),
            credit_amount=None,
            amount=Decimal("-100"),
            balance_after=Decimal("500"),
            source_reference=None,
            source_row_number=1,
        )
        account_id = "test-account"
        assert compute_transaction_hash(txn1, account_id) == compute_transaction_hash(txn2, account_id)
