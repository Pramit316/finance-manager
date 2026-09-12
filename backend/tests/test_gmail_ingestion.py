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
        self.list_calls = 0
        self.get_calls = 0
        self.list_kwargs = []

    def list(self, **kwargs):
        self.list_calls += 1
        self.list_kwargs.append(kwargs)
        return _Call({"messages": [{"id": key} for key in self.messages]})

    def get(self, *, id, **kwargs):
        self.get_calls += 1
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


def _message(message_id, body, *, sender="txn-alert@nabilbank.com", thread_id=None):
    return {
        "id": message_id,
        "threadId": thread_id or f"thread-{message_id}",
        "internalDate": "1788698220000",
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "From", "value": sender}],
            "body": {"data": _encoded(body)},
        },
    }


def _html_message(message_id, html_body, plain_body, *, sender="txn-alert@nabilbank.com"):
    return {
        "id": message_id,
        "internalDate": "1788698220000",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [{"name": "From", "value": sender}],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _encoded(plain_body)}},
                {
                    "mimeType": "multipart/related",
                    "parts": [{"mimeType": "text/html", "body": {"data": _encoded(html_body)}}],
                },
            ],
        },
    }


def _account_db(*account_numbers):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for index, account_number in enumerate(account_numbers):
        db.add(Account(name=f"Nabil {index}", institution="NABIL", account_type=AccountType.BANK, account_number=account_number))
    db.commit()
    return db


def test_masked_nabil_account_matches_full_account():
    db = _account_db("3410017508963")
    assert gmail_ingestion._account_for_alert(db, "341#####08963").account_number == "3410017508963"


def test_masked_nabil_account_rejects_incorrect_prefix_and_suffix():
    db = _account_db("3410017508963")
    for masked in ("342#####08963", "341#####08964"):
        try:
            gmail_ingestion._account_for_alert(db, masked)
        except ValueError as exc:
            assert str(exc) == "NABIL alert account does not match an existing account"
        else:
            raise AssertionError("mismatched masked account was accepted")


def test_masked_nabil_account_rejects_ambiguous_matches():
    db = _account_db("3410017508963", "3419999908963")
    try:
        gmail_ingestion._account_for_alert(db, "341#####08963")
    except ValueError as exc:
        assert str(exc) == "NABIL account mapping is ambiguous"
    else:
        raise AssertionError("ambiguous masked account was accepted")


def test_account_mapping_normalizes_formatting_and_supports_generic_masks():
    db = _account_db("12345-0000-67890")
    assert gmail_ingestion._account_for_alert(db, "12345****67890").account_number == "12345-0000-67890"


def test_gmail_sync_is_idempotent_and_classifies_same_day_alerts(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    account = Account(name="Nabil", institution="NABIL", account_type=AccountType.BANK, account_number="3410017508963")
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
    service = _Service(messages)
    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: service)

    first = gmail_ingestion.sync_nabil_alerts(db, connection)
    second = gmail_ingestion.sync_nabil_alerts(db, connection)

    assert first["emails_found"] == 3
    assert first["new_transactions"] == 2
    assert first["duplicates_skipped"] == 1
    assert first["transaction_duplicates"] == 1
    assert second["emails_already_processed"] == 3
    assert second["transaction_duplicates"] == 0
    assert service._users._messages.get_calls == 3
    assert all(call["maxResults"] <= 50 for call in service._users._messages.list_kwargs)
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


def test_failed_gmail_message_is_retried_instead_of_marked_already_processed(monkeypatch):
    db = _account_db("3410017508963")
    connection = GmailConnection(user_id="user-retry", email="user@example.com", encrypted_refresh_token="refresh")
    db.add(connection)
    db.commit()
    record = GmailMessage(
        connection_id=connection.id, gmail_message_id="retry-1", sender="txn-alert@nabilbank.com",
        status="FAILED", failure_reason="temporary parser failure",
    )
    db.add(record)
    db.commit()
    messages = {
        "retry-1": _message(
            "retry-1",
            "Transaction Date: 2026-09-11 12:40\nTransaction Type: Debit\nTransaction Amount: 25.00\nAvailable Balance: 369,659.96\nRemarks: retry",
        ),
    }
    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: _Service(messages))

    result = gmail_ingestion.sync_nabil_alerts(db, connection)

    assert result["emails_already_processed"] == 0
    assert result["emails_parsed"] == 1
    assert result["transactions_imported"] == 1
    assert db.query(GmailMessage).one().status == "IMPORTED"


def test_normal_sync_fetches_only_new_messages_and_returns_backfill_token(monkeypatch):
    db = _account_db("3410017508963")
    connection = GmailConnection(user_id="user-batch", email="user@example.com", encrypted_refresh_token="refresh")
    db.add(connection)
    db.commit()
    existing = GmailMessage(
        connection_id=connection.id, gmail_message_id="old-1", sender="txn-alert@nabilbank.com", status="IMPORTED",
    )
    db.add(existing)
    db.commit()
    messages = {"old-1": _message("old-1", "ignored"), "new-1": _message("new-1", "Transaction Date: 2026-09-11 12:40\nTransaction Type: Debit\nTransaction Amount: 25.00\nAvailable Balance: 369,659.96\nRemarks: new")}
    service = _Service(messages)
    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: service)

    result = gmail_ingestion.sync_nabil_alerts(db, connection, backfill=True, batch_size=25)

    assert result["emails_found"] == 2
    assert result["emails_already_processed"] == 1
    assert result["emails_fetched"] == 1
    assert result["transactions_imported"] == 1
    assert service._users._messages.get_calls == 1


def test_quota_exhaustion_defers_without_recording_mass_failures(monkeypatch):
    db = _account_db("3410017508963")
    connection = GmailConnection(user_id="user-quota", email="user@example.com", encrypted_refresh_token="refresh")
    db.add(connection)
    db.commit()
    calls = {"count": 0}

    def quota_request():
        calls["count"] += 1
        raise gmail_ingestion.QuotaDeferred("message list")

    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: _Service({}))
    monkeypatch.setattr(gmail_ingestion, "time", type("Clock", (), {"sleep": staticmethod(lambda _: None)}))
    result = None
    try:
        monkeypatch.setattr(gmail_ingestion, "_execute_gmail_request", lambda *args, **kwargs: quota_request())
        result = gmail_ingestion.sync_nabil_alerts(db, connection)
    finally:
        assert calls["count"] == 1

    assert result["quota_deferred"] == 1
    assert result["failed"] == 0
    assert result["emails_fetched"] == 0


def test_three_messages_in_one_thread_are_processed_independently(monkeypatch):
    db = _account_db("3410017508963")
    connection = GmailConnection(user_id="user-thread", email="user@example.com", encrypted_refresh_token="refresh")
    db.add(connection)
    db.commit()
    shared_thread = "nabil-thread-1"
    messages = {
        "message-1": _message(
            "message-1",
            "Transaction Date: 2026-09-11 12:40\nTransaction Type: Debit\nTransaction Amount: 25.00\nAvailable Balance: 369,659.96\nRemarks: NQR-1",
            thread_id=shared_thread,
        ),
        "message-2": _message(
            "message-2",
            "Transaction Date: 2026-09-11 13:40\nTransaction Type: Credit\nTransaction Amount: 100.00\nAvailable Balance: 369,759.96\nRemarks: NQR-2",
            thread_id=shared_thread,
        ),
        "message-3": _message(
            "message-3",
            "Transaction Date: 2026-09-11 14:40\nTransaction Type: Debit\nTransaction Amount: 40.00\nAvailable Balance: 369,719.96\nRemarks: NQR-3",
            thread_id=shared_thread,
        ),
    }
    service = _Service(messages)
    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: service)

    result = gmail_ingestion.sync_nabil_alerts(db, connection)

    assert result["emails_found"] == 3
    assert result["emails_fetched"] == 3
    assert result["emails_parsed"] == 3
    assert result["transactions_imported"] == 3
    assert result["transaction_duplicates"] == 0
    assert service._users._messages.get_calls == 3
    assert db.query(GmailMessage).count() == 3
    assert {row.gmail_message_id for row in db.query(GmailMessage).all()} == {"message-1", "message-2", "message-3"}
    assert db.query(Transaction).count() == 3
    assert {row.source_reference for row in db.query(Transaction).all()} == {"message-1", "message-2", "message-3"}


def test_gmail_sync_reads_nested_html_and_commits_one_transaction(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    account = Account(name="Nabil", institution="NABIL", account_type=AccountType.BANK, account_number="3410017508963")
    db.add(account)
    db.commit()
    connection = GmailConnection(user_id="user-3", email="user@example.com", encrypted_refresh_token="refresh")
    db.add(connection)
    db.commit()
    html_body = """
    <p>Please find transaction details for your account number 341#####08963 as below:</p>
    <table>
      <tr><th>Transaction Date</th><th>Transaction Type</th><th>Transaction Amount</th><th>Available Balance</th><th>Remarks</th></tr>
      <tr><td>2026-09-11 12:40</td><td>Debit</td><td>25.00</td><td>369,659.96</td><td>NQR-7969339,sandwich-Sandwich Hub NQR-7969339,san</td></tr>
    </table>
    """
    messages = {
        "html-1": _html_message(
            "html-1", html_body,
            "Transaction Date: wrong fallback content",
        ),
    }
    monkeypatch.setattr(gmail_ingestion, "gmail_service", lambda _: _Service(messages))

    first = gmail_ingestion.sync_nabil_alerts(db, connection)
    second = gmail_ingestion.sync_nabil_alerts(db, connection)

    transaction = db.query(Transaction).one()
    assert first["emails_found"] == 1
    assert first["bodies_read"] == 1
    assert first["parsed"] == 1
    assert first["imported"] == 1
    assert first["failed"] == 0
    assert second["emails_already_processed"] == 1
    assert second["transaction_duplicates"] == 0
    assert second["imported"] == 0
    assert transaction.amount == Decimal("-25.00")
    assert transaction.balance_after == Decimal("369659.96")
    assert transaction.description_raw == "NQR-7969339,sandwich-Sandwich Hub NQR-7969339,san"
    assert transaction.source_reference == "html-1"
    assert db.query(GmailMessage).one().status == "IMPORTED"
