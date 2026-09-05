"""Regression tests for the Standard Chartered statement adapter."""

from datetime import date
from decimal import Decimal

from app.models.transaction import TransactionKind
from app.parsers.standard_chartered import StandardCharteredStatementParser
from app.services.classification import classify_transaction
from app.services.deduplication import compute_transaction_hash


def test_standard_chartered_sample(standard_chartered_file_bytes):
    result = StandardCharteredStatementParser().parse(
        standard_chartered_file_bytes, "sample_standard_charter.pdf"
    )

    assert not result.errors
    assert result.source == "STANDARD_CHARTERED"
    assert result.account_number == "32382575201"
    assert result.period_from == date(2026, 7, 25)
    assert result.period_to == date(2026, 8, 23)
    assert result.currency == "NPR"
    assert result.closing_balance == Decimal("63177.00")
    assert len(result.transactions) == 4
    assert result.total_debit == Decimal("10208.00")
    assert result.total_credit == Decimal("48263.00")

    salary, fee, charge, transfer = result.transactions
    assert salary.credit_amount == Decimal("48263.00")
    assert salary.amount == Decimal("48263.00")
    assert "51SHRSAL" in salary.description_raw
    assert "STS SUSPENSE" in salary.description_raw
    assert fee.debit_amount == Decimal("200.00")
    assert fee.amount == Decimal("-200.00")
    assert charge.debit_amount == Decimal("8.00")
    assert "IBFT CHARGES" in charge.description_raw
    assert transfer.debit_amount == Decimal("10000.00")
    assert transfer.amount == Decimal("-10000.00")
    assert "IBFT" in transfer.description_raw

    fee_model = type("Fee", (), {"description_raw": fee.description_raw, "amount": fee.amount})()
    transfer_model = type("Transfer", (), {"description_raw": transfer.description_raw, "amount": transfer.amount})()
    assert classify_transaction(fee_model)["transaction_kind"] == TransactionKind.BANK_FEE
    assert classify_transaction(transfer_model)["transaction_kind"] == TransactionKind.INTERNAL_TRANSFER

    hashes = [compute_transaction_hash(txn, "account-1") for txn in result.transactions]
    assert len(set(hashes)) == 4
    repeated_hashes = [compute_transaction_hash(txn, "account-1") for txn in result.transactions]
    assert hashes == repeated_hashes