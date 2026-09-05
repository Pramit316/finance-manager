"""Statement reconciliation service.

Validates financial statements at two levels:
1. Statement-level: opening + deposits - withdrawals = closing
2. Running-balance: each row's balance matches previous + movement
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.parsers.base import ParsedStatement, ParsedTransaction


@dataclass
class ReconciliationResult:
    """Result of a statement reconciliation check."""

    passed: bool = False
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    calculated_closing: Optional[Decimal] = None
    total_deposits: Decimal = Decimal("0")
    total_withdrawals: Decimal = Decimal("0")
    difference: Decimal = Decimal("0")
    running_balance_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def reconcile_statement(statement: ParsedStatement) -> ReconciliationResult:
    """Perform statement-level reconciliation.

    For sources with opening/closing balances:
        opening + total_credit - total_debit should equal closing balance.
    """
    result = ReconciliationResult()

    if statement.opening_balance is None or statement.closing_balance is None:
        result.warnings.append(
            "Opening or closing balance not available — cannot reconcile at statement level"
        )
        return result

    result.opening_balance = statement.opening_balance
    result.closing_balance = statement.closing_balance

    # Sum deposits (credits) and withdrawals (debits)
    total_deposits = Decimal("0")
    total_withdrawals = Decimal("0")
    for txn in statement.transactions:
        if txn.credit_amount and txn.credit_amount > 0:
            total_deposits += txn.credit_amount
        if txn.debit_amount and txn.debit_amount > 0:
            total_withdrawals += txn.debit_amount

    result.total_deposits = total_deposits
    result.total_withdrawals = total_withdrawals

    calculated_closing = statement.opening_balance + total_deposits - total_withdrawals
    result.calculated_closing = calculated_closing
    result.difference = calculated_closing - statement.closing_balance

    # Allow tiny tolerance for floating-point edge cases (though we use Decimal)
    result.passed = abs(result.difference) < Decimal("0.01")

    return result


def validate_running_balance(
    transactions: list[ParsedTransaction],
    opening_balance: Optional[Decimal] = None,
    reverse_order: bool = False,
) -> list[str]:
    """Validate transaction-to-transaction running balance.

    Args:
        transactions: List of parsed transactions in chronological order.
        opening_balance: The starting balance before the first transaction.
        reverse_order: If True, transactions are in newest-first order and will be reversed.

    Returns:
        List of error messages for balance mismatches.
    """
    errors = []

    if not transactions:
        return errors

    # Work in chronological order
    txns = list(reversed(transactions)) if reverse_order else list(transactions)

    if opening_balance is None:
        # Try to derive from first transaction
        # For newest-first statements (eSewa), we need the last row's balance
        return errors

    prev_balance = opening_balance

    for i, txn in enumerate(txns):
        if txn.balance_after is None:
            continue

        expected = prev_balance
        if txn.credit_amount and txn.credit_amount > 0:
            expected += txn.credit_amount
        if txn.debit_amount and txn.debit_amount > 0:
            expected -= txn.debit_amount

        if abs(expected - txn.balance_after) >= Decimal("0.01"):
            errors.append(
                f"Row {txn.source_row_number or i}: expected balance {expected}, "
                f"got {txn.balance_after}"
            )

        prev_balance = txn.balance_after

    return errors
