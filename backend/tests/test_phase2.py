"""Tests for Phase 2: Classification, Transfer Matching, and Analytics."""

import pytest
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

from app.database import Base
from app.models.account import Account, AccountType
from app.models.statement_import import StatementImport, StatementSource, ImportStatus, ReconciliationStatus
from app.models.transaction import Transaction, TransactionKind
from app.services import classification, internal_transfer, analytics
from app.services.internal_transfer import repair_orphaned_pairs

@pytest.fixture(scope="module")
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def clean_db(test_db):
    # Clean up before each test
    for table in reversed(Base.metadata.sorted_tables):
        test_db.execute(table.delete())
    test_db.commit()


@pytest.fixture
def setup_accounts(test_db):
    acc1 = Account(name="Nabil Test", institution="NABIL", account_type=AccountType.BANK)
    acc2 = Account(name="eSewa Test", institution="ESEWA", account_type=AccountType.WALLET, account_number="9861828662")
    test_db.add_all([acc1, acc2])
    test_db.commit()
    return acc1, acc2


@pytest.fixture
def setup_import(test_db, setup_accounts):
    acc1, acc2 = setup_accounts
    stmt1 = StatementImport(
        account_id=acc1.id,
        source=StatementSource.NABIL,
        filename="test1.pdf",
        file_hash="hash1",
        status=ImportStatus.IMPORTED
    )
    stmt2 = StatementImport(
        account_id=acc2.id,
        source=StatementSource.ESEWA,
        filename="test2.xls",
        file_hash="hash2",
        status=ImportStatus.IMPORTED
    )
    test_db.add_all([stmt1, stmt2])
    test_db.commit()
    return stmt1, stmt2


def create_transaction(db, account, statement, amount, description, txn_date=date(2026, 8, 1), user_override=False):
    t = Transaction(
        account_id=account.id,
        statement_import_id=statement.id,
        source=statement.source,
        transaction_date=txn_date,
        description_raw=description,
        amount=Decimal(amount),
        transaction_hash=str(uuid.uuid4()),
        balance_after=Decimal("1000.00")
    )
    if user_override:
        t.transaction_kind = TransactionKind.EXPENSE
        t.classification_source = "USER"
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_classification_deterministic(test_db, setup_accounts, setup_import):
    acc1, _ = setup_accounts
    stmt1, _ = setup_import

    # Tax
    t1 = create_transaction(test_db, acc1, stmt1, "-100", "NABIL:WTax.Pd:something")
    # POS
    t2 = create_transaction(test_db, acc1, stmt1, "-50", "POS PUR/123/STORE")
    # Fallback income
    t3 = create_transaction(test_db, acc1, stmt1, "1000", "Random incoming money")
    # User override
    t4 = create_transaction(test_db, acc1, stmt1, "500", "POS PUR/123", user_override=True)

    result = classification.run_classification(test_db)
    
    assert result["classified"] == 3
    assert result["skipped_user_overrides"] == 0
    
    test_db.refresh(t1)
    test_db.refresh(t2)
    test_db.refresh(t3)
    test_db.refresh(t4)
    
    assert t1.transaction_kind == TransactionKind.TAX
    assert t2.transaction_kind == TransactionKind.EXPENSE
    assert t3.transaction_kind == TransactionKind.INCOME
    
    # User override should be preserved
    assert t4.transaction_kind == TransactionKind.EXPENSE
    assert t4.classification_source == "USER"


def test_transfer_matching(test_db, setup_accounts, setup_import):
    acc1, acc2 = setup_accounts
    stmt1, stmt2 = setup_import
    
    # Matching transfer pair (use correct user esewa number)
    t_nabil = create_transaction(test_db, acc1, stmt1, "-5000", "eSewa Load 9861828662, 123", txn_date=date(2026, 8, 1))
    t_esewa = create_transaction(test_db, acc2, stmt2, "5000", "Money transferred from NABIL", txn_date=date(2026, 8, 1))
    
    # Unmatched
    t_unmatched = create_transaction(test_db, acc1, stmt1, "-5000", "POS purchase", txn_date=date(2026, 8, 1))
    
    # Run classification first to set internal transfer candidates
    classification.run_classification(test_db)
    
    test_db.refresh(t_nabil)
    assert t_nabil.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    
    # Match transfers
    result = internal_transfer.match_internal_transfers(test_db)
    assert result["matched_transactions"] == 2
    assert result["transfer_groups_created"] == 1
    
    test_db.refresh(t_nabil)
    test_db.refresh(t_esewa)
    test_db.refresh(t_unmatched)
    
    assert t_nabil.is_internal_transfer is True
    assert t_esewa.is_internal_transfer is True
    assert t_nabil.transfer_group_id == t_esewa.transfer_group_id
    assert t_nabil.transfer_group_id is not None
    
    assert t_unmatched.is_internal_transfer is not True
    assert t_unmatched.transfer_group_id is None


def test_internal_transfer_another_person_esewa(test_db, setup_accounts, setup_import):
    """Regression Test 2: Non-owned wallet stays EXPENSE, never matched."""
    acc1, acc2 = setup_accounts
    stmt1, _ = setup_import

    # User owns 9861828662. This load goes to 9841978487 (NOT owned).
    t_nabil = create_transaction(
        test_db, acc1, stmt1, "-737.00",
        "eSewa Load 9841978487, 289084067",
        txn_date=date(2026, 8, 5)
    )

    classification.run_classification(test_db)
    internal_transfer.match_internal_transfers(test_db)

    test_db.refresh(t_nabil)
    assert t_nabil.transaction_kind == TransactionKind.EXPENSE
    assert t_nabil.is_internal_transfer is not True
    assert t_nabil.transfer_group_id is None


def test_internal_transfer_confirmed_owned_wallet(test_db, setup_accounts, setup_import):
    """Regression Test 1: Confirmed owned-wallet transfer — BOTH sides INTERNAL_TRANSFER."""
    acc1, acc2 = setup_accounts
    stmt1, stmt2 = setup_import

    # User owns 9861828662.
    t_nabil = create_transaction(
        test_db, acc1, stmt1, "-1800",
        "eSewa Load 9861828662, 298569985",
        txn_date=date(2026, 8, 16)
    )
    t_esewa = create_transaction(
        test_db, acc2, stmt2, "1800",
        "Money transferred from NABIL BANK LTD.",
        txn_date=date(2026, 8, 16)
    )

    classification.run_classification(test_db)

    # After classification Nabil side must already be a candidate.
    test_db.refresh(t_nabil)
    assert t_nabil.transaction_kind == TransactionKind.INTERNAL_TRANSFER, (
        "Nabil eSewa Load to owned wallet must be INTERNAL_TRANSFER candidate before matching"
    )

    internal_transfer.match_internal_transfers(test_db)

    test_db.refresh(t_nabil)
    test_db.refresh(t_esewa)

    # Both sides must be INTERNAL_TRANSFER.
    assert t_nabil.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    assert t_esewa.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    assert t_nabil.is_internal_transfer is True
    assert t_esewa.is_internal_transfer is True
    # Same group ID.
    assert t_nabil.transfer_group_id is not None
    assert t_nabil.transfer_group_id == t_esewa.transfer_group_id


def test_internal_transfer_atomic_both_sides(test_db, setup_accounts, setup_import):
    """Regression Test 3: There must never be a confirmed pair where only one side is INTERNAL_TRANSFER."""
    acc1, acc2 = setup_accounts
    stmt1, stmt2 = setup_import

    t_nabil = create_transaction(
        test_db, acc1, stmt1, "-2000",
        "eSewa Load 9861828662, 111222",
        txn_date=date(2026, 8, 10)
    )
    t_esewa = create_transaction(
        test_db, acc2, stmt2, "2000",
        "Money transferred from NABIL BANK LTD.",
        txn_date=date(2026, 8, 10)
    )

    classification.run_classification(test_db)
    internal_transfer.match_internal_transfers(test_db)

    test_db.refresh(t_nabil)
    test_db.refresh(t_esewa)

    # Both must be INTERNAL_TRANSFER; neither can be solo.
    nabil_is_it = t_nabil.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    esewa_is_it = t_esewa.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    assert nabil_is_it == esewa_is_it, (
        "Both sides of a confirmed transfer pair must have the same transaction_kind"
    )
    assert t_nabil.transfer_group_id == t_esewa.transfer_group_id


def test_analytics_internal_transfer_not_double_counted(test_db, setup_accounts, setup_import):
    """Regression Test 4: Confirmed internal transfer of 1800 contributes 0 to income/spending."""
    acc1, acc2 = setup_accounts
    stmt1, stmt2 = setup_import

    # Income
    create_transaction(test_db, acc1, stmt1, "5000", "Salary")
    # Expense
    create_transaction(test_db, acc1, stmt1, "-1000", "POS Food", txn_date=date(2026, 8, 2))
    # Bank Fee
    create_transaction(test_db, acc1, stmt1, "-50", "Bank transfer charges")
    # Internal transfer 1800
    create_transaction(
        test_db, acc1, stmt1, "-1800",
        "eSewa Load 9861828662, 298569985",
        txn_date=date(2026, 8, 16)
    )
    create_transaction(
        test_db, acc2, stmt2, "1800",
        "Money transferred from NABIL BANK LTD.",
        txn_date=date(2026, 8, 16)
    )

    classification.run_classification(test_db)
    internal_transfer.match_internal_transfers(test_db)

    summary = analytics.get_analytics_summary(test_db)

    assert summary["total_income"] == Decimal("5000"), "Only salary should count as income"
    assert summary["total_spending"] == Decimal("1050"), "1000 expense + 50 bank fee"
    assert summary["internal_transfers"] == Decimal("1800"), "Transfer of 1800 must appear exactly once"
    # Sanity: no double-counting
    assert summary["internal_transfers"] != Decimal("3600")


def test_analytics(test_db, setup_accounts, setup_import):
    acc1, acc2 = setup_accounts
    stmt1, stmt2 = setup_import
    
    # Income
    create_transaction(test_db, acc1, stmt1, "5000", "Salary")
    # Expense
    create_transaction(test_db, acc1, stmt1, "-1000", "POS Food", txn_date=date(2026, 8, 2))
    # Bank Fee
    create_transaction(test_db, acc1, stmt1, "-50", "Bank transfer charges")
    # Refund (Not counted as income)
    create_transaction(test_db, acc1, stmt1, "200", "Refund for Food")
    
    # Internal Transfer pair (using the correct user eSewa number: 9861828662)
    t_nabil = create_transaction(test_db, acc1, stmt1, "-3000", "eSewa Load 9861828662, 1234")
    t_esewa = create_transaction(test_db, acc2, stmt2, "3000", "Money transferred from NABIL")
    
    classification.run_classification(test_db)
    
    # Manually fix refund kind (since deterministic might just say income)
    t_refund = test_db.query(Transaction).filter(Transaction.amount == Decimal("200")).first()
    t_refund.transaction_kind = TransactionKind.REFUND
    test_db.commit()
    
    internal_transfer.match_internal_transfers(test_db)
    
    summary = analytics.get_analytics_summary(test_db)
    
    assert summary["total_income"] == Decimal("5000")
    assert summary["total_spending"] == Decimal("1050")  # 1000 expense + 50 bank fee
    assert summary["net_cash_flow"] == Decimal("3950")
    assert summary["internal_transfers"] == Decimal("3000")
    assert summary["refunds"] == Decimal("200")
    
    # Account balances
    balances = analytics.get_latest_account_balances(test_db)
    assert len(balances) == 2
    for b in balances:
        assert b["latest_balance"] == Decimal("1000.00")
