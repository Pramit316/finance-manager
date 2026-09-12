"""Transaction deduplication service.

Uses SHA-256 fingerprints for deterministic dedup.
Fingerprint components differ by source to ensure:
- same row → same hash
- different legitimate rows with same reference → different hashes
"""

import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from app.parsers.base import ParsedTransaction
from app.models.transaction import Transaction


def compute_transaction_hash(
    txn: ParsedTransaction,
    account_id: str,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for a parsed transaction.

    The hash components are source-specific to preserve uniqueness where
    source identifiers like eSewa reference codes are non-unique.
    """
    if txn.source == "ESEWA":
        return _compute_esewa_hash(txn, account_id)
    elif txn.source == "NABIL":
        return _compute_nabil_hash(txn, account_id)
    elif txn.source == "STANDARD_CHARTERED":
        return _compute_standard_chartered_hash(txn, account_id)
    elif txn.source == "GMAIL_TRANSACTION_ALERT":
        return _compute_gmail_hash(txn, account_id)
    else:
        return _compute_generic_hash(txn, account_id)


def _compute_esewa_hash(txn: ParsedTransaction, account_id: str) -> str:
    """eSewa fingerprint uses reference, timestamp, amounts, description, balance, channel."""
    components = [
        "ESEWA",
        account_id,
        txn.source_reference or "",
        txn.transaction_timestamp.isoformat() if txn.transaction_timestamp else "",
        str(txn.debit_amount or "0"),
        str(txn.credit_amount or "0"),
        txn.description_raw.strip(),
        str(txn.balance_after or ""),
        txn.channel or "",
    ]
    fingerprint = "|".join(components)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _compute_nabil_hash(txn: ParsedTransaction, account_id: str) -> str:
    """Nabil fingerprint uses date, amounts, balance, normalised description."""
    # Normalise description: collapse whitespace, strip
    desc_normalised = " ".join(txn.description_raw.split())

    components = [
        "NABIL",
        account_id,
        txn.transaction_date.isoformat() if txn.transaction_date else "",
        str(txn.debit_amount or "0"),
        str(txn.credit_amount or "0"),
        str(txn.balance_after or ""),
        desc_normalised,
    ]
    fingerprint = "|".join(components)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _compute_generic_hash(txn: ParsedTransaction, account_id: str) -> str:
    """Fallback generic fingerprint."""
    desc_normalised = " ".join(txn.description_raw.split())
    components = [
        txn.source,
        account_id,
        txn.transaction_date.isoformat() if txn.transaction_date else "",
        str(txn.amount),
        desc_normalised,
        str(txn.balance_after or ""),
        txn.source_reference or "",
    ]
    fingerprint = "|".join(components)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _compute_standard_chartered_hash(txn: ParsedTransaction, account_id: str) -> str:
    """Standard Chartered fingerprint uses date, both columns, balance, and description."""
    components = [
        "STANDARD_CHARTERED", account_id, txn.transaction_date.isoformat(),
        str(txn.debit_amount or "0"), str(txn.credit_amount or "0"),
        str(txn.balance_after or ""), " ".join(txn.description_raw.split()),
    ]
    return hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()


def _compute_gmail_hash(txn: ParsedTransaction, account_id: str) -> str:
    """Fingerprint alert contents, excluding Gmail message ID for safety."""
    components = [
        "GMAIL_TRANSACTION_ALERT", account_id,
        txn.transaction_timestamp.isoformat() if txn.transaction_timestamp else txn.transaction_date.isoformat(),
        str(txn.debit_amount or "0"), str(txn.credit_amount or "0"),
        str(txn.balance_after or ""), " ".join(txn.description_raw.split()),
    ]
    return hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()


def find_cross_source_match(db, txn: ParsedTransaction, account_id: str):
    """Find an existing non-Gmail transaction representing the same bank event.

    Descriptions are deliberately not required: Nabil PDF and alert remarks
    commonly describe the same event differently. Exact date matches win;
    the one-day fallback is used only when amount and post-transaction balance
    are also identical.
    """
    signed_amount = txn.amount
    normalized_account_id = uuid.UUID(account_id) if isinstance(account_id, str) else account_id
    base_query = db.query(Transaction).filter(
        Transaction.account_id == normalized_account_id,
        Transaction.source != "GMAIL_TRANSACTION_ALERT",
        Transaction.amount == signed_amount,
        Transaction.balance_after == txn.balance_after,
    )
    exact = base_query.filter(Transaction.transaction_date == txn.transaction_date).all()
    if len(exact) == 1:
        return exact[0], "same_account_date_amount_balance", "strong"
    if len(exact) > 1:
        return None, "ambiguous_same_date_amount_balance", "ambiguous"

    nearby = base_query.filter(
        Transaction.transaction_date >= txn.transaction_date - timedelta(days=1),
        Transaction.transaction_date <= txn.transaction_date + timedelta(days=1),
    ).all()
    if len(nearby) == 1:
        return nearby[0], "same_account_amount_balance_within_one_day", "cautious"
    if len(nearby) > 1:
        return None, "ambiguous_nearby_amount_balance", "ambiguous"
    return None, None, None
