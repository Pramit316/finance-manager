"""Manual Gmail ingestion for Nabil transaction alerts."""

import base64
import hashlib
import logging
import re
import time
from collections import Counter
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
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)
MAX_GMAIL_RETRIES = 3


class QuotaDeferred(Exception):
    """Gmail quota prevented this sync from safely continuing."""


def _is_quota_error(error: HttpError) -> bool:
    status = getattr(error.resp, "status", None)
    detail = str(error).lower()
    return status == 429 or (status == 403 and any(code in detail for code in ("quotaexceeded", "userratelimitexceeded", "ratelimitexceeded")))


def _execute_gmail_request(request_factory, operation: str):
    for attempt in range(MAX_GMAIL_RETRIES):
        try:
            return request_factory().execute()
        except HttpError as exc:
            if not _is_quota_error(exc):
                raise
            if attempt == MAX_GMAIL_RETRIES - 1:
                raise QuotaDeferred(operation) from exc
            delay = 2 ** attempt
            logger.warning("Gmail %s quota/rate limit; retrying in %ss", operation, delay)
            time.sleep(delay)


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
    logger.info(
        "Mapping NABIL account: alert=%s candidates=%s",
        _masked_account_for_log(account_number),
        [_masked_account_for_log(account.account_number) for account in accounts],
    )
    if account_number:
        normalized_alert = _normalize_account_number(account_number)
        if not normalized_alert:
            raise ValueError("NABIL alert account number is invalid")

        full_accounts = {
            account: _normalize_account_number(account.account_number)
            for account in accounts
            if account.account_number
        }
        logger.info("NABIL normalized candidates=%s", [_masked_account_for_log(value) for value in full_accounts.values()])
        normalized_counts = Counter(full_accounts.values())
        duplicate_records = [value for value, count in normalized_counts.items() if value and count > 1]
        if duplicate_records:
            logger.warning(
                "Duplicate active NABIL account records represent the same normalized account: %s",
                [_masked_account_for_log(value) for value in duplicate_records],
            )
        if not _contains_mask(normalized_alert):
            exact_matches = [account for account, normalized in full_accounts.items() if normalized == normalized_alert]
            logger.info("NABIL exact matching candidates=%d", len(exact_matches))
            if len(exact_matches) == 1:
                return exact_matches[0]
            if len(exact_matches) > 1:
                raise ValueError("NABIL account mapping is ambiguous")

        pattern = _masked_account_pattern(normalized_alert)
        masked_matches = [
            account for account, normalized in full_accounts.items()
            if pattern.fullmatch(normalized)
        ]
        logger.info("NABIL prefix/suffix mask matching candidates=%d", len(masked_matches))
        if len(masked_matches) == 1:
            return masked_matches[0]
        if len(masked_matches) > 1:
            raise ValueError("NABIL account mapping is ambiguous")
        raise ValueError("NABIL alert account does not match an existing account")
    if len(accounts) != 1:
        raise ValueError("NABIL account mapping is ambiguous")
    return accounts[0]


def _masked_account_for_log(value: str | None) -> str:
    normalized = _normalize_account_number(value)
    if not normalized:
        return "<none>"
    if len(normalized) <= 6:
        return "*" * len(normalized)
    return f"{normalized[:3]}{'*' * max(len(normalized) - 6, 1)}{normalized[-3:]}"


def _normalize_account_number(value: str | None) -> str:
    """Remove display formatting while retaining generic account mask characters."""
    return re.sub(r"[^0-9#*xX]", "", value or "").lower().replace("x", "#")


def _contains_mask(value: str) -> bool:
    return "#" in value or "*" in value


def _masked_account_pattern(value: str) -> re.Pattern[str]:
    parts: list[str] = []
    index = 0
    while index < len(value):
        if value[index] in "#*":
            end = index
            while end < len(value) and value[end] in "#*":
                end += 1
            parts.append(rf"\d{{{end - index}}}")
            index = end
        elif value[index].isdigit():
            parts.append(value[index])
            index += 1
        else:
            raise ValueError("NABIL alert account number is invalid")
    return re.compile("".join(parts))


def sync_nabil_alerts(
    db: Session,
    connection: GmailConnection,
    *,
    backfill: bool = False,
    page_token: str | None = None,
    batch_size: int | None = None,
) -> dict:
    service = gmail_service(connection)
    query = f"from:{settings.GMAIL_ALLOWED_SENDER}"
    batch_size = max(1, min(batch_size or settings.GMAIL_SYNC_BATCH_SIZE, 50))
    logger.info("Searching Gmail for Nabil alerts with sender filter %s", settings.GMAIL_ALLOWED_SENDER)
    listed = []
    next_page_token = None
    list_quota_deferred = False
    try:
        page = _execute_gmail_request(
            lambda: service.users().messages().list(
                userId="me", q=query, maxResults=batch_size, **({"pageToken": page_token} if page_token else {}),
            ),
            "message list",
        )
        listed.extend(page.get("messages", []))
        next_page_token = page.get("nextPageToken") if backfill else None
    except QuotaDeferred:
        list_quota_deferred = True
        logger.warning("Gmail quota exhausted while listing messages; deferring sync")
    logger.info("Gmail search found %d messages", len(listed))
    result = {
        "emails_found": len(listed), "emails_already_processed": 0, "emails_fetched": 0, "emails_parsed": 0,
        "transactions_imported": 0, "transaction_duplicates": 0, "failed": 0,
        "quota_deferred": 1 if list_quota_deferred else 0,
        "failure_reasons": [], "bodies_read": 0, "parsed": 0,
        "imported": 0, "duplicates": 0, "new_transactions": 0,
        "duplicates_skipped": 0, "failures": [],
    }
    stmt = None

    parser = NabilEmailParser()
    for message_index, listed_message in enumerate(listed):
        message_id = listed_message.get("id", "")
        existing_message = db.query(GmailMessage).filter(
            GmailMessage.connection_id == connection.id,
            GmailMessage.gmail_message_id == message_id,
        ).first()
        if existing_message and existing_message.status in {"IMPORTED", "DUPLICATE"}:
            result["emails_already_processed"] += 1
            logger.info("Gmail message %s already processed with status=%s", message_id, existing_message.status)
            continue
        try:
            message = _execute_gmail_request(
                lambda: service.users().messages().get(userId="me", id=message_id, format="full"),
                "message body",
            )
        except QuotaDeferred:
            result["quota_deferred"] += len(listed) - message_index
            logger.warning("Gmail quota exhausted while fetching message bodies; deferring remaining batch")
            break
        except Exception as exc:
            record = existing_message or GmailMessage(
                connection_id=connection.id, gmail_message_id=message_id,
                sender=settings.GMAIL_ALLOWED_SENDER, status="FAILED",
            )
            record.status = "FAILED"
            record.failure_reason = str(exc)[:500]
            db.add(record)
            result["failed"] += 1
            result["failure_reasons"].append({"message_id": message_id, "reason": record.failure_reason})
            db.commit()
            logger.warning("Failed to fetch Gmail message %s: %s", message_id, type(exc).__name__)
            continue

        result["emails_fetched"] += 1
        record = existing_message or GmailMessage(
            connection_id=connection.id, gmail_message_id=message_id,
            sender=settings.GMAIL_ALLOWED_SENDER, status="PROCESSING",
        )
        record.status = "PROCESSING"
        db.add(record)
        try:
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
            result["emails_parsed"] += 1
            logger.info(
                "Parsed Gmail message %s: date=%s type=%s amount=%s balance=%s remarks_found=%s",
                message_id, alert.transaction_timestamp.isoformat(),
                "Credit" if alert.is_credit else "Debit", alert.amount,
                alert.balance_after, bool(alert.remarks),
            )
            account = _account_for_alert(db, alert.account_number)
            logger.info("Mapped Gmail message %s to NABIL account %s", message_id, account.id)
            if stmt is None:
                stmt = StatementImport(
                    source=StatementSource.GMAIL_TRANSACTION_ALERT,
                    account_id=account.id,
                    filename=f"gmail-sync-{datetime.now(timezone.utc).isoformat()}",
                    file_hash=hashlib.sha256("|".join(m["id"] for m in listed).encode()).hexdigest(),
                    status=ImportStatus.PARSING,
                    reconciliation_status=ReconciliationStatus.NOT_AVAILABLE,
                )
                db.add(stmt)
                db.flush()
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
                result["transaction_duplicates"] += 1
                result["duplicates"] += 1
                result["duplicates_skipped"] += 1
                logger.info("Skipped duplicate Gmail transaction")
            else:
                txn = Transaction(source=StatementSource.GMAIL_TRANSACTION_ALERT, account_id=account.id, statement_import_id=stmt.id, transaction_date=parsed.transaction_date, transaction_timestamp=parsed.transaction_timestamp, description_raw=parsed.description_raw, amount=parsed.amount, debit_amount=parsed.debit_amount, credit_amount=parsed.credit_amount, currency=account.currency, balance_after=parsed.balance_after, source_reference=message_id, transaction_hash=txn_hash, raw_payload=parsed.raw_payload)
                db.add(txn)
                db.flush()
                record.transaction_id = txn.id
                record.status = "IMPORTED"
                result["new_transactions"] += 1
                result["imported"] += 1
                result["transactions_imported"] += 1
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
        stmt.rows_parsed = result["emails_parsed"]
        stmt.duplicate_rows = result["transaction_duplicates"]
        stmt.invalid_rows = result["failed"]
        stmt.status = ImportStatus.IMPORTED if not result["failed"] else ImportStatus.NEEDS_REVIEW
        stmt.completed_at = datetime.now(timezone.utc)
        db.commit()
        if result["transactions_imported"]:
            from app.services.classification import classify_import_transactions
            from app.services.internal_transfer import match_internal_transfers
            classify_import_transactions(db, stmt.id)
            match_internal_transfers(db)
    if not result["quota_deferred"]:
        connection.last_successful_sync_at = datetime.now(timezone.utc)
    db.commit()
    result["next_page_token"] = next_page_token
    logger.info(
        "Gmail sync complete: found=%d bodies=%d parsed=%d imported=%d duplicates=%d failed=%d",
        result["emails_found"], result["bodies_read"], result["emails_parsed"],
        result["transactions_imported"], result["transaction_duplicates"], result["failed"],
    )
    return result