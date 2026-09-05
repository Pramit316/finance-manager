"""Internal transfer matching service.

Identifies and links transactions that represent internal transfers
between user-owned accounts.

Classification order:
1. User overrides (classification_source='USER') — never touched.
2. Identify transfer candidates from descriptions and account ownership.
3. Perform cross-account matching (ATOMIC — both sides updated together).
4. Successfully matched pairs → INTERNAL_TRANSFER on BOTH sides.
5. Unmatched outgoing eSewa-load-to-owned-wallet candidates remain
   INTERNAL_TRANSFER (pending counterpart). Downstream analytics
   should not double-count; classification_source='CANDIDATE'.
"""

import logging
import re
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction, TransactionKind

logger = logging.getLogger(__name__)

# Pattern to extract the destination eSewa wallet number from Nabil descriptions.
_ESEWA_LOAD_RE = re.compile(r"eSewa\s+Load\s+(\d+)", re.IGNORECASE)

# Descriptions that indicate an incoming transfer from Nabil on the eSewa side.
_ESEWA_FROM_NABIL_RE = re.compile(r"Money\s+transferred\s+from\s+NABIL", re.IGNORECASE)
_TRANSFER_DESCRIPTION_RE = re.compile(
    r"\b(?:IBFT|ACCOUNTFT|ACCOUNT\s*FT|FUND\s+TRANSFER|TRANSFER)\b",
    re.IGNORECASE,
)


def _get_user_esewa_numbers(db: Session) -> dict[str, uuid.UUID]:
    """Return {account_number: account_id} for every user-owned eSewa account."""
    accounts = (
        db.query(Account)
        .filter(Account.institution == "ESEWA", Account.account_number.isnot(None))
        .all()
    )
    return {acc.account_number: acc.id for acc in accounts}


def match_internal_transfers(db: Session, date_tolerance_days: int = 2) -> dict:
    """Find and atomically link internal transfers across accounts.

    Matching strategy:
    - For each Nabil debit with an `eSewa Load <owned_wallet>` description:
        * extract the destination wallet number
        * confirm it belongs to a user-owned eSewa account
        * find a matching eSewa credit of equal absolute amount within the
          date tolerance that has a Nabil-origin description
    - For each eSewa debit with a bank-transfer description:
        * find a matching bank credit of equal absolute amount within the
          date tolerance (future extension — basic amount/date matching).
    - When a pair is confirmed, update BOTH sides atomically.

    USER-overridden transactions are never modified.
    """
    user_esewa_numbers = _get_user_esewa_numbers(db)

    # ── 1. Collect unmatched transactions ─────────────────────────────────────
    # Include transactions not yet confirmed as a transfer pair AND not user-overridden.
    unmatched = (
        db.query(Transaction)
        .filter(
            Transaction.transfer_group_id.is_(None),
            Transaction.classification_source != "USER",
        )
        .all()
    )

    matched_ids: set[uuid.UUID] = set()
    matched_count = 0
    new_groups = 0

    # ── 2. Nabil → eSewa matching ──────────────────────────────────────────────
    # A Nabil debit "eSewa Load <owned_wallet>" paired with an eSewa credit
    # "Money transferred from NABIL BANK LTD." of the same amount and date.

    # eSewa credit candidates: no group yet, OR has a group but the group's
    # Nabil debit partner is missing (orphaned eSewa side from a broken pair).
    # We include both cases so that re-matching can reassign the group atomically.
    esewa_credits: list[Transaction] = [
        t for t in (
            db.query(Transaction)
            .filter(
                Transaction.amount > 0,
                Transaction.classification_source != "USER",
            )
            .all()
        )
        if _ESEWA_FROM_NABIL_RE.search(t.description_raw or "")
    ]

    # Nabil debit candidates: eSewa Load to owned wallet, no confirmed group yet.
    nabil_debits: list[Transaction] = [
        t for t in unmatched
        if t.amount < 0 and _ESEWA_LOAD_RE.search(t.description_raw or "")
           and t.transaction_kind == TransactionKind.INTERNAL_TRANSFER
    ]

    # Track eSewa credit IDs that are already correctly paired (group set, and the
    # partner Nabil debit in the same group also exists and is INTERNAL_TRANSFER).
    correctly_paired_credit_ids: set[uuid.UUID] = set()
    for credit in esewa_credits:
        if credit.transfer_group_id is None:
            continue
        # Check if there's already a Nabil debit in the same group.
        partner = (
            db.query(Transaction)
            .filter(
                Transaction.transfer_group_id == credit.transfer_group_id,
                Transaction.id != credit.id,
                Transaction.transaction_kind == TransactionKind.INTERNAL_TRANSFER,
                Transaction.is_internal_transfer == True,  # noqa: E712
            )
            .first()
        )
        if partner is not None:
            correctly_paired_credit_ids.add(credit.id)

    for debit in nabil_debits:
        if debit.id in matched_ids:
            continue

        description = debit.description_raw or ""
        load_match = _ESEWA_LOAD_RE.search(description)
        if not load_match:
            continue

        dest_wallet = load_match.group(1)
        if dest_wallet not in user_esewa_numbers:
            # Destination is not user-owned — not an internal transfer candidate.
            continue

        # The destination eSewa account id, used to ensure the credit comes from the
        # correct account (owned eSewa with that wallet number).
        dest_account_id = user_esewa_numbers[dest_wallet]

        # Find the best matching eSewa credit.
        best_match: Transaction | None = None
        for credit in esewa_credits:
            if credit.id in matched_ids:
                continue
            if credit.id in correctly_paired_credit_ids:
                continue  # Already has a confirmed pair — leave it.
            if credit.account_id != dest_account_id:
                continue
            if credit.amount != abs(debit.amount):
                continue
            date_diff = abs((debit.transaction_date - credit.transaction_date).days)
            if date_diff > date_tolerance_days:
                continue
            # Accept the first qualifying candidate.
            best_match = credit
            break

        if best_match:
            group_id = uuid.uuid4()
            _confirm_pair(debit, best_match, group_id)
            matched_ids.add(debit.id)
            matched_ids.add(best_match.id)
            matched_count += 2
            new_groups += 1
            logger.info(
                "Matched internal transfer: Nabil %s <-> eSewa %s (group %s)",
                debit.id, best_match.id, group_id,
            )

    # ── 3. Evidence-gated cross-account matching ─────────────────────────────
    # Do not require automatic classification here: a positive account-transfer
    # row may already have fallen through to generic INCOME. At least one side
    # must contain transfer evidence, while amount/date/account constraints keep
    # coincidental equal-value payments from becoming transfers.
    candidates = [
        txn for txn in unmatched
        if txn.id not in matched_ids
        and txn.transfer_group_id is None
        and txn.classification_source != "USER"
        and _TRANSFER_DESCRIPTION_RE.search(txn.description_raw or "")
    ]
    for debit in (txn for txn in candidates if txn.amount < 0):
        if debit.id in matched_ids:
            continue
        for credit in (txn for txn in candidates if txn.amount > 0):
            if credit.id in matched_ids or debit.account_id == credit.account_id:
                continue
            if abs(debit.amount) != credit.amount:
                continue
            if abs((debit.transaction_date - credit.transaction_date).days) > date_tolerance_days:
                continue
            group_id = uuid.uuid4()
            _confirm_pair(debit, credit, group_id)
            matched_ids.add(debit.id)
            matched_ids.add(credit.id)
            matched_count += 2
            new_groups += 1
            break

    # ── 4. Generic fallback matching ───────────────────────────────────────────
    # For transactions already flagged as INTERNAL_TRANSFER by rules but not yet
    # paired — use basic amount/date/different-account matching.
    # This covers eSewa→Bank and other future transfer types.

    remaining = [t for t in unmatched if t.id not in matched_ids]
    remaining_debits = [t for t in remaining if t.amount < 0
                        and t.transaction_kind == TransactionKind.INTERNAL_TRANSFER]
    remaining_credits = [t for t in remaining if t.amount > 0
                         and t.transaction_kind == TransactionKind.INTERNAL_TRANSFER]

    for debit in remaining_debits:
        if debit.id in matched_ids:
            continue
        for credit in remaining_credits:
            if credit.id in matched_ids:
                continue
            if debit.account_id == credit.account_id:
                continue
            if abs(debit.amount) != credit.amount:
                continue
            date_diff = abs((debit.transaction_date - credit.transaction_date).days)
            if date_diff > date_tolerance_days:
                continue
            group_id = uuid.uuid4()
            _confirm_pair(debit, credit, group_id)
            matched_ids.add(debit.id)
            matched_ids.add(credit.id)
            matched_count += 2
            new_groups += 1
            break

    db.commit()

    return {
        "matched_transactions": matched_count,
        "transfer_groups_created": new_groups,
    }


def _confirm_pair(debit: Transaction, credit: Transaction, group_id: uuid.UUID) -> None:
    """Atomically mark both sides of a transfer pair as INTERNAL_TRANSFER.

    USER-overridden transactions are never modified.
    """
    for txn in (debit, credit):
        if txn.classification_source == "USER":
            continue
        txn.transaction_kind = TransactionKind.INTERNAL_TRANSFER
        txn.is_internal_transfer = True
        txn.transfer_group_id = group_id
        txn.classification_source = "MATCHING"
        other = credit if txn is debit else debit
        txn.classification_reason = f"Matched internal transfer with transaction {other.id}"


def repair_orphaned_pairs(db: Session) -> dict:
    """Find and fix transfer pairs where only one side is marked INTERNAL_TRANSFER.

    This can happen when:
    - A previous repair incorrectly reclassified one side as EXPENSE.
    - A transaction was manually changed without updating its pair.

    For each transaction with a transfer_group_id, ensure its pair also has
    INTERNAL_TRANSFER set. Preserve USER overrides on the pair.
    """
    # Transactions with a group_id but missing INTERNAL_TRANSFER status.
    orphan_candidates = (
        db.query(Transaction)
        .filter(
            Transaction.transfer_group_id.isnot(None),
            Transaction.is_internal_transfer.isnot(True),
            Transaction.classification_source != "USER",
        )
        .all()
    )

    repaired = 0
    for txn in orphan_candidates:
        txn.transaction_kind = TransactionKind.INTERNAL_TRANSFER
        txn.is_internal_transfer = True
        if txn.classification_source != "USER":
            txn.classification_source = "MATCHING"
            txn.classification_reason = "Repaired: pair had confirmed transfer_group_id"
        repaired += 1

    # Also find confirmed-matched transactions whose pair no longer exists or was
    # reclassified — clear the stale group_id from confirmed EXPENSE transactions
    # that somehow retained a group_id but is_internal_transfer is False.
    stale = (
        db.query(Transaction)
        .filter(
            Transaction.transfer_group_id.isnot(None),
            Transaction.is_internal_transfer == False,  # noqa: E712
            Transaction.classification_source != "USER",
        )
        .all()
    )
    cleared = 0
    for txn in stale:
        txn.transfer_group_id = None
        cleared += 1

    db.commit()
    return {"repaired_orphans": repaired, "cleared_stale_groups": cleared}


def repair_and_match_transfers(db: Session) -> dict:
    """Repair automatic classifications and rematch all existing transactions."""
    from app.services.classification import run_classification

    classification_result = run_classification(db)
    matching_result = match_internal_transfers(db)
    repair_result = repair_orphaned_pairs(db)
    return {
        "classification": classification_result,
        "matching": matching_result,
        "repair": repair_result,
    }
