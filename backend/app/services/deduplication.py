"""Transaction deduplication service.

Uses SHA-256 fingerprints for deterministic dedup.
Fingerprint components differ by source to ensure:
- same row → same hash
- different legitimate rows with same reference → different hashes
"""

import hashlib
from decimal import Decimal
from typing import Optional

from app.parsers.base import ParsedTransaction


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
