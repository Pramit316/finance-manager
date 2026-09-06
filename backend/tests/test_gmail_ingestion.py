import base64
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base
from app.models.account import Account, AccountType
from app.models.gmail import GmailConnection, GmailMessage
from app.models.transaction import Transaction, TransactionKind
from app.services import gmail_ingestion


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"


class _Call:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class _Messages:
    def __init__(self, messages):
        self.messages = messages

    def list(self, **kwargs):
        return _Call({"messages": [{"id": key} for key in self.messages]})

    def get(self, *, id, **kwargs):
        return _Call(self.messages[id])


class _Users:
    def __init__(self, messages):
        self._messages = _Messages(messages)

    def messages(self):
        return self._messages


class _Service:
    def __init__(self, messages):
        self._users = _Users(messages)

    def users(self):
        return self._users


def _encoded(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _message(message_id, body, *, sender="txn-alert@nabilbank.com"):
    return {
        "id": message_id,
        "internalDate": "1788698220000",
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "From", "value": sender}],
            "body": {"data": _encoded(body)},
        },
    }


def test_gmail_sync_is_idempotent_and_classifies_same_day_alerts(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    account = Account(name="Nabil", institution="NABIL", account_type=AccountType.BANK, account_number="34108963")
    db.add(account)
    db.commit()
    connection = GmailConnection(user_id="user-1", email="user@example.com", encrypted_refresh_token="refresh", encrypted_access_token="access")
    db.add(connection)
    db.commit()

    messages = {
        "m-1": _message("m-1", "Transaction Date: 2026-09-06 12:37\nTransaction Type: Credit\nTransaction Amount: 10,924.00\nAvailable Balance: 204,264.96\nRemarks: FON:IBFT:1:SHIVA H"),
        "m-2": _message("m-2", "Transaction Date: 2026-09-06 12:38\nTransaction Type: Debit\nTransaction Amount: 1,269.00\nAvailable Balance: 202,995.96\nRemarks: POS PUR/50009142/BHATBH ATEN"),
        "m-3": _message("m-3", "Transaction Date: 2026-09-06 12:38\nTransaction Type: Debit\nTransaction Amount: 1,269.00\nAvailable Balance: 202,995.96\nRemarks: POS PUR/50009142/BHATBH ATEN"),
    }
    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: _Service(messages))

    first = gmail_ingestion.sync_nabil_alerts(db, connection)
    second = gmail_ingestion.sync_nabil_alerts(db, connection)

    assert first["emails_found"] == 3
    assert first["new_transactions"] == 2
    assert first["duplicates_skipped"] == 1
    assert second["duplicates_skipped"] == 3
    assert db.query(Transaction).count() == 2
    assert db.query(GmailMessage).filter(GmailMessage.status == "IMPORTED").count() == 2
    assert db.query(Transaction).filter(Transaction.transaction_kind == TransactionKind.EXPENSE).count() == 1
    assert db.query(Transaction).filter(Transaction.amount == Decimal("10924.00")).one().balance_after == Decimal("204264.96")


def test_gmail_sync_records_unsupported_sender_as_failed(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    account = Account(name="Nabil", institution="NABIL", account_type=AccountType.BANK)
    db.add(account)
    db.commit()
    connection = GmailConnection(user_id="user-2", email="user@example.com", encrypted_refresh_token="refresh")
    db.add(connection)
    db.commit()
    messages = {"bad": _message("bad", "Transaction Date: 2026-09-06 12:37", sender="other@example.com")}
    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: _Service(messages))

    result = gmail_ingestion.sync_nabil_alerts(db, connection)

    assert result["failed"] == 1
    assert db.query(GmailMessage).one().status == "FAILED"
