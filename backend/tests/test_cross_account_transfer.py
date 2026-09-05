"""Regression coverage for bank-to-bank transfer matching."""

from datetime import date
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()

from app.models.account import Account, AccountType
from app.models.statement_import import StatementImport, StatementSource, ImportStatus
from app.models.transaction import Transaction, TransactionKind
from app.services import analytics, classification, internal_transfer


def test_standard_chartered_to_nabil_transfer_is_not_income(test_db):
    standard_chartered = Account(
        name="Standard Chartered", institution="STANDARD_CHARTERED",
        account_type=AccountType.BANK, account_number="32382575201",
    )
    nabil = Account(
        name="Nabil", institution="NABIL", account_type=AccountType.BANK,
        account_number="3410017508963",
    )
    test_db.add_all([standard_chartered, nabil])
    test_db.commit()
    standard_import = StatementImport(
        account_id=standard_chartered.id, source=StatementSource.STANDARD_CHARTERED,
        filename="standard.pdf", file_hash="standard", status=ImportStatus.IMPORTED,
    )
    nabil_import = StatementImport(
        account_id=nabil.id, source=StatementSource.NABIL,
        filename="nabil.pdf", file_hash="nabil", status=ImportStatus.IMPORTED,
    )
    test_db.add_all([standard_import, nabil_import])
    test_db.commit()
    outgoing = Transaction(
        account_id=standard_chartered.id, statement_import_id=standard_import.id,
        source=StatementSource.STANDARD_CHARTERED, transaction_date=date(2026, 7, 28),
        description_raw="693287555 PRAMIT BHATTARAI| IBFT|0401", amount=Decimal("-10000"),
        debit_amount=Decimal("10000"), currency="NPR", transaction_hash=str(uuid.uuid4()),
    )
    incoming = Transaction(
        account_id=nabil.id, statement_import_id=nabil_import.id,
        source=StatementSource.NABIL, transaction_date=date(2026, 7, 28),
        description_raw="ACCOUNTFT:Pramit Bhattarai Try", amount=Decimal("10000"),
        credit_amount=Decimal("10000"), currency="NPR", transaction_hash=str(uuid.uuid4()),
    )
    test_db.add_all([outgoing, incoming])
    test_db.commit()

    classification.run_classification(test_db)
    assert incoming.transaction_kind == TransactionKind.INCOME
    internal_transfer.match_internal_transfers(test_db)
    test_db.refresh(outgoing)
    test_db.refresh(incoming)

    assert outgoing.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    assert incoming.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    assert outgoing.is_internal_transfer is True
    assert incoming.is_internal_transfer is True
    assert outgoing.transfer_group_id == incoming.transfer_group_id
    assert incoming.classification_source == "MATCHING"
    summary = analytics.get_analytics_summary(test_db)
    assert summary["total_income"] == Decimal("0")
    assert summary["total_spending"] == Decimal("0")
    assert summary["internal_transfers"] == Decimal("10000")

    # Re-running the repair path is idempotent and leaves the same pair linked.
    result = internal_transfer.repair_and_match_transfers(test_db)
    test_db.refresh(outgoing)
    test_db.refresh(incoming)
    assert result["matching"]["transfer_groups_created"] == 0
    assert outgoing.transfer_group_id == incoming.transfer_group_id
    assert incoming.transaction_kind == TransactionKind.INTERNAL_TRANSFER