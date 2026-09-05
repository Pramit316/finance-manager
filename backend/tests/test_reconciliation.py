"""Reconciliation service tests."""

from decimal import Decimal
from datetime import date, datetime, timezone

import pytest

from app.parsers.base import ParsedStatement, ParsedTransaction
from app.services.reconciliation import reconcile_statement, validate_running_balance


class TestReconciliation:

    def test_nabil_reconciliation(self):
        """Nabil fixture reconciliation should pass with 0.00 difference."""
        statement = ParsedStatement(
            source="NABIL",
            opening_balance=Decimal("266744.21"),
            closing_balance=Decimal("215366.99"),
            transactions=[
                ParsedTransaction(
                    source="NABIL",
                    transaction_date=date(2026, 7, 10),
                    transaction_timestamp=None,
                    description_raw="Withdraw",
                    debit_amount=Decimal("63852.52"),
                    credit_amount=None,
                    amount=Decimal("-63852.52"),
                    balance_after=None,
                    source_reference=None,
                    source_row_number=1,
                ),
                ParsedTransaction(
                    source="NABIL",
                    transaction_date=date(2026, 7, 10),
                    transaction_timestamp=None,
                    description_raw="Deposit",
                    debit_amount=None,
                    credit_amount=Decimal("12475.30"),
                    amount=Decimal("12475.30"),
                    balance_after=None,
                    source_reference=None,
                    source_row_number=2,
                ),
            ],
        )
        result = reconcile_statement(statement)
        assert result.passed
        assert result.difference == Decimal("0.00")

    def test_reconciliation_failure(self):
        """Reconciliation should fail when totals don't match."""
        statement = ParsedStatement(
            source="NABIL",
            opening_balance=Decimal("1000"),
            closing_balance=Decimal("2000"),
            transactions=[
                ParsedTransaction(
                    source="NABIL",
                    transaction_date=date(2026, 7, 10),
                    transaction_timestamp=None,
                    description_raw="Deposit",
                    debit_amount=None,
                    credit_amount=Decimal("500"),
                    amount=Decimal("500"),
                    balance_after=None,
                    source_reference=None,
                    source_row_number=1,
                ),
            ],
        )
        result = reconcile_statement(statement)
        assert not result.passed
        assert result.difference != Decimal("0")

    def test_running_balance_pass(self):
        """Running balance should pass for correct sequences."""
        txns = [
            ParsedTransaction(
                source="NABIL",
                transaction_date=date(2026, 7, 10),
                transaction_timestamp=None,
                description_raw="Withdrawal",
                debit_amount=Decimal("100"),
                credit_amount=None,
                amount=Decimal("-100"),
                balance_after=Decimal("900"),
                source_reference=None,
                source_row_number=1,
            ),
            ParsedTransaction(
                source="NABIL",
                transaction_date=date(2026, 7, 11),
                transaction_timestamp=None,
                description_raw="Deposit",
                debit_amount=None,
                credit_amount=Decimal("200"),
                amount=Decimal("200"),
                balance_after=Decimal("1100"),
                source_reference=None,
                source_row_number=2,
            ),
        ]
        errors = validate_running_balance(txns, opening_balance=Decimal("1000"))
        assert not errors

    def test_running_balance_fail(self):
        """Running balance should fail for incorrect sequences."""
        txns = [
            ParsedTransaction(
                source="NABIL",
                transaction_date=date(2026, 7, 10),
                transaction_timestamp=None,
                description_raw="Withdrawal",
                debit_amount=Decimal("100"),
                credit_amount=None,
                amount=Decimal("-100"),
                balance_after=Decimal("950"),  # Wrong!
                source_reference=None,
                source_row_number=1,
            ),
        ]
        errors = validate_running_balance(txns, opening_balance=Decimal("1000"))
        assert len(errors) > 0
