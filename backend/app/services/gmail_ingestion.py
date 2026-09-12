"""Manual Gmail ingestion for Nabil transaction alerts."""

import base64
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from email.utils import parseaddr

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.account import Account
from app.models.gmail import GmailConnection, GmailMessage
from app.models.statement_import import ImportStatus, ReconciliationStatus, StatementImport, StatementSource
from app.models.transaction import Transaction
from app.parsers.base import ParsedTransaction
from app.parsers.nabil_email import NabilEmailParser
from app.services.deduplication import compute_transaction_hash
from app.services.gmail_client import gmail_service

logger = logging.getLogger(__name__)


def _decode(data: str | None) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode() + b"=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _body(payload: dict) -> tuple[str, bool]:
    plain = html = ""
    stack = [payload]
    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        data = _decode(part.get("body", {}).get("data"))
        if mime == "text/plain" and data:
            plain = data
        elif mime == "text/html" and data:
            html = data
        stack.extend(part.get("parts", []))
    return (html, True) if html else (plain, False)


def _mime_types(payload: dict) -> list[str]:
    types: list[str] = []
    stack = [payload]
    while stack:
        part = stack.pop()
        mime = part.get("mimeType")
        if mime:
            types.append(mime)
        stack.extend(part.get("parts", []))
    return types


def _headers(payload: dict) -> dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}


def _account_for_alert(db: Session, account_number: str | None) -> Account:
    accounts = db.query(Account).filter(Account.institution == "NABIL", Account.is_active == True).all()
    if not accounts:
        raise ValueError("No active NABIL account exists")
    if account_number:
        digits = re.sub(r"\D", "", account_number)
        matches = [a for a in accounts if not a.account_number or digits.endswith(re.sub(r"\D", "", a.account_number)) or re.sub(r"\D", "", a.account_number).endswith(digits)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError("NABIL account mapping is ambiguous")
        raise ValueError("NABIL alert account does not match an existing account")
    if len(accounts) != 1:
        raise ValueError("NABIL account mapping is ambiguous")
    return accounts[0]


def sync_nabil_alerts(db: Session, connection: GmailConnection) -> dict:
    service = gmail_service(connection)
    query = f"from:{settings.GMAIL_ALLOWED_SENDER}"
    logger.info("Searching Gmail for Nabil alerts with sender filter %s", settings.GMAIL_ALLOWED_SENDER)
    listed = []
    page_token = None
    while True:
        page = service.users().messages().list(userId="me", q=query, pageToken=page_token).execute()
        listed.extend(page.get("messages", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            break
    logger.info("Gmail search found %d messages", len(listed))
    result = {
        "emails_found": len(listed), "bodies_read": 0, "parsed": 0,
        "imported": 0, "duplicates": 0, "failed": 0, "failure_reasons": [],
        "new_transactions": 0, "duplicates_skipped": 0, "failures": [],
    }
    stmt = StatementImport(
        source=StatementSource.GMAIL_TRANSACTION_ALERT,
        account_id=_account_for_alert(db, None).id if listed else uuid.uuid4(),
        filename=f"gmail-sync-{datetime.now(timezone.utc).isoformat()}",
        file_hash=hashlib.sha256("|".join(m["id"] for m in listed).encode()).hexdigest(),
        status=ImportStatus.PARSING,
        reconciliation_status=ReconciliationStatus.NOT_AVAILABLE,
    ) if listed else None
    if stmt:
        db.add(stmt)
        db.flush()

    parser = NabilEmailParser()
    for listed_message in listed:
        message_id = listed_message.get("id", "")
        if db.query(GmailMessage).filter(GmailMessage.connection_id == connection.id, GmailMessage.gmail_message_id == message_id).first():
            result["duplicates_skipped"] += 1
            result["duplicates"] += 1
            logger.info("Skipped previously processed Gmail message")
            continue
        record = GmailMessage(connection_id=connection.id, gmail_message_id=message_id, sender=settings.GMAIL_ALLOWED_SENDER, status="PROCESSING")
        db.add(record)
        try:
            message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
            payload = message.get("payload", {})
            headers = _headers(payload)
            sender = parseaddr(headers.get("from", ""))[1].lower()
            if sender != settings.GMAIL_ALLOWED_SENDER.lower():
                raise ValueError("Unsupported sender")
            body, is_html = _body(payload)
            mime_types = _mime_types(payload)
            logger.info(
                "Gmail message %s: sender=%s mime_types=%s html_body=%s plain_body=%s",
                message_id, sender, mime_types, "text/html" in mime_types, "text/plain" in mime_types,
            )
            if not body:
                raise ValueError("No HTML/text body")
            result["bodies_read"] += 1
            received_at = datetime.fromtimestamp(int(message.get("internalDate", "0")) / 1000, tz=timezone.utc)
            alert = parser.parse(body, sender=sender, received_at=received_at, is_html=is_html)
            result["parsed"] += 1
            logger.info(
                "Parsed Gmail message %s: date=%s type=%s amount=%s balance=%s remarks_found=%s",
                message_id, alert.transaction_timestamp.isoformat(),
                "Credit" if alert.is_credit else "Debit", alert.amount,
                alert.balance_after, bool(alert.remarks),
            )
            account = _account_for_alert(db, alert.account_number)
            logger.info("Mapped Gmail message %s to NABIL account %s", message_id, account.id)
            parsed = ParsedTransaction(
                source="GMAIL_TRANSACTION_ALERT", transaction_date=alert.transaction_timestamp.date(), transaction_timestamp=alert.transaction_timestamp,
                description_raw=alert.remarks or "Nabil transaction alert", debit_amount=None if alert.is_credit else alert.amount,
                credit_amount=alert.amount if alert.is_credit else None, amount=alert.amount if alert.is_credit else -alert.amount,
                balance_after=alert.balance_after, source_reference=message_id, source_row_number=None,
                raw_payload={"gmail_message_id": message_id, "sender": sender, "received_at": received_at.isoformat(), "remarks": alert.remarks},
            )
            txn_hash = compute_transaction_hash(parsed, str(account.id))
            existing = db.query(Transaction).filter(Transaction.account_id == account.id, Transaction.transaction_hash == txn_hash).first()
            if existing:
                record.status = "DUPLICATE"
                result["duplicates_skipped"] += 1
                result["duplicates"] += 1
                logger.info("Skipped duplicate Gmail transaction")
            else:
                txn = Transaction(source=StatementSource.GMAIL_TRANSACTION_ALERT, account_id=account.id, statement_import_id=stmt.id, transaction_date=parsed.transaction_date, transaction_timestamp=parsed.transaction_timestamp, description_raw=parsed.description_raw, amount=parsed.amount, debit_amount=parsed.debit_amount, credit_amount=parsed.credit_amount, currency=account.currency, balance_after=parsed.balance_after, source_reference=message_id, transaction_hash=txn_hash, raw_payload=parsed.raw_payload)
                db.add(txn)
                db.flush()
                record.transaction_id = txn.id
                record.status = "IMPORTED"
                result["new_transactions"] += 1
                result["imported"] += 1
                stmt.rows_inserted = (stmt.rows_inserted or 0) + 1
                logger.info("Imported transaction from Gmail message")
            db.flush()
        except Exception as exc:
            record.status = "FAILED"
            record.failure_reason = str(exc)[:500]
            result["failed"] += 1
            result["failures"].append({"message_id": message_id, "reason": record.failure_reason})
            result["failure_reasons"].append({"message_id": message_id, "reason": record.failure_reason})
            logger.warning("Failed to process Gmail message %s: %s", message_id, record.failure_reason)
        db.commit()

    if stmt:
        stmt.rows_read = len(listed)
        stmt.rows_parsed = result["new_transactions"]
        stmt.duplicate_rows = result["duplicates_skipped"]
        stmt.invalid_rows = result["failed"]
        stmt.status = ImportStatus.IMPORTED if not result["failed"] else ImportStatus.NEEDS_REVIEW
        stmt.completed_at = datetime.now(timezone.utc)
        db.commit()
        if result["new_transactions"]:
            from app.services.classification import classify_import_transactions
            from app.services.internal_transfer import match_internal_transfers
            classify_import_transactions(db, stmt.id)
            match_internal_transfers(db)
    connection.last_successful_sync_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "Gmail sync complete: found=%d bodies=%d parsed=%d imported=%d duplicates=%d failed=%d",
        result["emails_found"], result["bodies_read"], result["parsed"], result["imported"],
        result["duplicates"], result["failed"],
    )
    return result