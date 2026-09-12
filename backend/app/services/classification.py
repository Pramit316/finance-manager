"""Transaction classification service.

Applies deterministic rules to classify transactions by kind, category, and merchant.
Respects classification priority:
1. User overrides (classification_source = USER) — never overwritten
2. eSewa Load ownership check (owned wallet → INTERNAL_TRANSFER candidate;
   external wallet → EXPENSE immediately)
3. Other deterministic description rules
4. Sign-based fallback (positive → INCOME, negative → EXPENSE)
5. UNKNOWN if no rule matched

Critical: eSewa Load to an OWNED wallet must be classified INTERNAL_TRANSFER at
this stage. The internal_transfer matching service will later pair it with the
corresponding eSewa credit and set transfer_group_id on BOTH sides atomically.
Do NOT classify owned-wallet loads as EXPENSE before matching runs.

Does NOT modify raw financial fields.
"""

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.account import Account
from app.models.transaction import Transaction, TransactionKind

logger = logging.getLogger(__name__)

# Default categories
CATEGORIES = [
    "Food & Dining",
    "Lunch",
    "Home Expense",
    "Groceries",
    "Shopping",
    "Transport",
    "Petrol / Gas",
    "Bills & Utilities",
    "Entertainment",
    "Health",
    "Education",
    "Travel",
    "Personal",
    "Transfers",
    "Fees & Charges",
    "Tax",
    "Income",
    "Other",
]


class ClassificationRule:
    """A single deterministic classification rule."""

    def __init__(
        self,
        pattern: str,
        kind: TransactionKind,
        category: str | None = None,
        merchant: str | None = None,
        confidence: float = 0.8,
        reason: str = "deterministic_rule",
        require_positive: bool = False,
        require_negative: bool = False,
    ):
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.kind = kind
        self.category = category
        self.merchant = merchant
        self.confidence = confidence
        self.reason = reason
        self.require_positive = require_positive
        self.require_negative = require_negative

    def matches(self, description: str, amount) -> bool:
        if not bool(self.pattern.search(description)):
            return False
        if self.require_positive and amount <= 0:
            return False
        if self.require_negative and amount >= 0:
            return False
        return True


# Built-in deterministic rules — ordered by specificity (most specific first)
DETERMINISTIC_RULES: list[ClassificationRule] = [
    # ── Tax ────────────────────────────────────────────────────────────
    ClassificationRule(
        r"WTax\.Pd",
        TransactionKind.TAX,
        category="Tax",
        reason="Withholding tax payment",
    ),

    # ── Interest ──────────────────────────────────────────────────────
    ClassificationRule(
        r"Int\.Pd",
        TransactionKind.INTEREST,
        category="Income",
        reason="Interest payment received",
    ),

    # ── Bank fees / charges ───────────────────────────────────────────
    ClassificationRule(
        r"Bank\s*transfer\s*charges",
        TransactionKind.BANK_FEE,
        category="Fees & Charges",
        reason="Bank transfer fee",
    ),
    ClassificationRule(
        r"Charge\s+on\s+payment",
        TransactionKind.BANK_FEE,
        category="Fees & Charges",
        reason="Service charge",
    ),
    ClassificationRule(
        r"SMS\s+ALERT\s+FEE|IBFT\s+CHARGES",
        TransactionKind.BANK_FEE,
        category="Fees & Charges",
        reason="Standard Chartered account fee",
        require_negative=True,
    ),
    # Standard Chartered IBFT movements are not consumption until a counterpart
    # or user classification establishes what the transfer represents.
    ClassificationRule(
        r"\bIBFT\b",
        TransactionKind.INTERNAL_TRANSFER,
        category="Transfers",
        confidence=0.6,
        reason="IBFT transfer candidate",
    ),

    # ── Internal transfer candidates ──────────────────────────────────
    # eSewa loads from Nabil (Nabil side)
    ClassificationRule(
        r"eSewa\s+Load\s+\d+",
        TransactionKind.INTERNAL_TRANSFER,
        category="Transfers",
        reason="eSewa wallet load from bank",
    ),
    # eSewa incoming from Nabil (eSewa side)
    ClassificationRule(
        r"Money\s+transferred\s+from\s+NABIL\s+BANK",
        TransactionKind.INTERNAL_TRANSFER,
        category="Transfers",
        reason="Incoming transfer from Nabil Bank (internal transfer candidate)",
    ),
    # eSewa outgoing to bank accounts (eSewa side)
    ClassificationRule(
        r"Money\s+transferred\s+to\s+.*BANK",
        TransactionKind.INTERNAL_TRANSFER,
        category="Transfers",
        confidence=0.7,
        reason="Outgoing transfer to bank (internal transfer candidate)",
    ),

    # ── eSewa fund transfers ──────────────────────────────────────────
    # Outgoing fund transfer to another person/entity
    ClassificationRule(
        r"Fund\s+Transferred\s+to\s+",
        TransactionKind.EXPENSE,
        category="Personal",
        confidence=0.6,
        reason="Fund transferred out via eSewa",
    ),
    # Incoming fund transfer from another person
    ClassificationRule(
        r"Fund\s+Transferred\s+by\s+",
        TransactionKind.INCOME,
        category="Income",
        confidence=0.5,
        reason="Fund received via eSewa (could be internal transfer)",
    ),

    # ── Bill payments ─────────────────────────────────────────────────
    ClassificationRule(
        r"Nepal\s+Electricity",
        TransactionKind.EXPENSE,
        category="Bills & Utilities",
        merchant="Nepal Electricity Authority",
        reason="Electricity bill payment",
    ),
    ClassificationRule(
        r"Nepal\s+Telecom|NTC",
        TransactionKind.EXPENSE,
        category="Bills & Utilities",
        merchant="Nepal Telecom",
        reason="Telecom bill/topup",
    ),
    ClassificationRule(
        r"Topup\s+for",
        TransactionKind.EXPENSE,
        category="Bills & Utilities",
        reason="Mobile phone topup",
    ),
    ClassificationRule(
        r"Ncell",
        TransactionKind.EXPENSE,
        category="Bills & Utilities",
        merchant="Ncell",
        reason="Ncell mobile payment",
    ),

    # ── Received payment ──────────────────────────────────────────────
    ClassificationRule(
        r"Received\s+payment\s+for\s+Bill\s+Split",
        TransactionKind.INCOME,
        category="Income",
        reason="Bill split received",
    ),
    ClassificationRule(
        r"Received\s+payment",
        TransactionKind.INCOME,
        category="Income",
        confidence=0.7,
        reason="Payment received",
    ),

    # NOTE: ACCOUNTFT: prefix is NOT a reliable internal-transfer signal on its own.
    # It appears on both incoming payments from external people AND genuine account
    # transfers. Real internal transfers are caught by the transfer matching service.

    # ── POS purchases ─────────────────────────────────────────────────
    ClassificationRule(
        r"^POS\b",
        TransactionKind.EXPENSE,
        category="Shopping",
        reason="POS terminal purchase",
    ),
    ClassificationRule(
        r"PUR/\d+/",
        TransactionKind.EXPENSE,
        category="Shopping",
        reason="POS purchase",
    ),

    # ── eSewa bill split ──────────────────────────────────────────────
    ClassificationRule(
        r"Paid\s+For\s+Bill\s+Split",
        TransactionKind.EXPENSE,
        category="Personal",
        reason="Bill split payment",
    ),

    # ── General eSewa payments ("Paid for ...") ───────────────────────
    ClassificationRule(
        r"Paid\s+for\s+.*Daraz",
        TransactionKind.EXPENSE,
        category="Shopping",
        merchant="Daraz",
        reason="Daraz purchase via eSewa",
    ),
    ClassificationRule(
        r"Paid\s+for\s+.*Meroshare|Siddhartha\s+Capital",
        TransactionKind.EXPENSE,
        category="Personal",
        reason="Stock market / Meroshare payment",
    ),
    ClassificationRule(
        r"Paid\s+for\s+",
        TransactionKind.EXPENSE,
        category="Shopping",
        reason="Payment via eSewa",
    ),

    # ── MPAY / QR — Nabil mobile payments ─────────────────────────────
    ClassificationRule(
        r"^MPAY\b",
        TransactionKind.EXPENSE,
        category="Shopping",
        reason="Mobile payment sent (MPAY)",
        require_negative=True,
    ),
    ClassificationRule(
        r"^MPAY\b",
        TransactionKind.INCOME,
        category="Income",
        reason="Mobile payment received (MPAY)",
        require_positive=True,
    ),
    ClassificationRule(
        r"FPQR,",
        TransactionKind.EXPENSE,
        category="Shopping",
        reason="QR code payment",
        require_negative=True,
    ),
]


def classify_transaction(txn: Transaction, user_esewa_numbers: set[str] | None = None) -> dict:
    """Classify a single transaction using deterministic rules.

    Returns a dict of fields to update. Does not modify the transaction directly.
    """
    description = txn.description_raw or ""

    # ── eSewa Load ownership check ────────────────────────────────────────────
    # Example: eSewa Load 9841978487, 289084067
    # Must be intercepted BEFORE the generic DETERMINISTIC_RULES loop so that
    # external-wallet loads are hard-classified as EXPENSE and not caught by
    # the generic `eSewa Load \d+` → INTERNAL_TRANSFER rule.
    esewa_load_match = re.search(r"eSewa\s+Load\s+(\d+)", description, re.IGNORECASE)
    if esewa_load_match:
        dest_wallet = esewa_load_match.group(1)
        if user_esewa_numbers is not None:
            if dest_wallet not in user_esewa_numbers:
                # External wallet — hard classify as EXPENSE immediately.
                return {
                    "transaction_kind": TransactionKind.EXPENSE,
                    "category": "Transfers",
                    "classification_source": "RULE",
                    "classification_confidence": 0.9,
                    "classification_reason": (
                        f"eSewa load to external wallet ({dest_wallet})"
                    ),
                }
            else:
                # Owned wallet — mark as INTERNAL_TRANSFER candidate.
                # The matching service will pair it and set transfer_group_id.
                return {
                    "transaction_kind": TransactionKind.INTERNAL_TRANSFER,
                    "category": "Transfers",
                    "classification_source": "RULE",
                    "classification_confidence": 0.9,
                    "classification_reason": (
                        f"eSewa load to user-owned wallet ({dest_wallet}) — transfer candidate"
                    ),
                }

    for rule in DETERMINISTIC_RULES:
        if rule.matches(description, txn.amount):
            result = {
                "transaction_kind": rule.kind,
                "classification_source": "RULE",
                "classification_confidence": rule.confidence,
                "classification_reason": rule.reason,
            }
            if rule.category:
                result["category"] = rule.category
            if rule.merchant:
                result["merchant"] = rule.merchant
            return result

    # Fallback: classify by sign of amount if no rule matched
    if txn.amount > 0:
        return {
            "transaction_kind": TransactionKind.INCOME,
            "category": "Income",
            "classification_source": "RULE",
            "classification_confidence": 0.5,
            "classification_reason": "Positive amount — assumed income",
        }
    elif txn.amount < 0:
        return {
            "transaction_kind": TransactionKind.EXPENSE,
            "category": "Other",
            "classification_source": "RULE",
            "classification_confidence": 0.5,
            "classification_reason": "Negative amount — assumed expense",
        }

    return {
        "transaction_kind": TransactionKind.UNKNOWN,
        "classification_source": "RULE",
        "classification_confidence": 0.0,
        "classification_reason": "No matching rule",
    }


def _apply_classification(txn: Transaction, result: dict) -> None:
    """Apply a classification result dict to a transaction."""
    txn.transaction_kind = result["transaction_kind"]
    txn.classification_source = result["classification_source"]
    txn.classification_confidence = result["classification_confidence"]
    txn.classification_reason = result["classification_reason"]
    if "category" in result:
        txn.category = result["category"]
    if "merchant" in result:
        txn.merchant = result["merchant"]

    # If reclassified away from INTERNAL_TRANSFER, clear stale transfer flags
    # UNLESS the transaction was confirmed by the matching service (classification_source=MATCHING)
    # — in that case the transfer_group_id represents a real verified pair and must not be cleared.
    if (
        result["transaction_kind"] != TransactionKind.INTERNAL_TRANSFER
        and txn.is_internal_transfer
        and txn.transfer_group_id is None  # no confirmed pair match
    ):
        txn.is_internal_transfer = None

    txn.updated_at = datetime.now(timezone.utc)


def classify_import_transactions(db: Session, statement_import_id: uuid.UUID) -> dict:
    """Classify only the transactions from a specific import.

    Called automatically after a successful statement import.
    Respects user overrides.
    """
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.statement_import_id == statement_import_id,
            (
                (Transaction.classification_source != "USER")
                | (Transaction.classification_source.is_(None))
            ),
            or_(
                Transaction.classification_source != "MATCHING",
                Transaction.classification_source.is_(None),
            ),
        )
        .all()
    )

    user_esewa_numbers = {
        acc.account_number for acc in db.query(Account).filter(Account.institution == "ESEWA", Account.account_number.isnot(None)).all()
    }

    classified = 0
    for txn in transactions:
        if txn.classification_source == "USER":
            continue
        result = classify_transaction(txn, user_esewa_numbers=user_esewa_numbers)
        _apply_classification(txn, result)
        classified += 1

    db.commit()
    return {"classified": classified, "import_id": str(statement_import_id)}


def run_classification(db: Session) -> dict:
    """Run classification on all non-user-classified transactions.

    Respects user overrides — transactions with classification_source='USER'
    are never overwritten.

    Returns summary stats.
    """
    # Fetch transactions that are not user-classified
    transactions = (
        db.query(Transaction)
        .filter(
            (
                (Transaction.classification_source != "USER")
                | (Transaction.classification_source.is_(None))
            ),
            or_(
                Transaction.classification_source != "MATCHING",
                Transaction.classification_source.is_(None),
            ),
        )
        .all()
    )

    user_esewa_numbers = {
        acc.account_number for acc in db.query(Account).filter(Account.institution == "ESEWA", Account.account_number.isnot(None)).all()
    }

    classified = 0
    skipped = 0

    for txn in transactions:
        # Double-check: never overwrite user classifications
        if txn.classification_source == "USER":
            skipped += 1
            continue

        result = classify_transaction(txn, user_esewa_numbers=user_esewa_numbers)
        _apply_classification(txn, result)
        classified += 1

    db.commit()

    return {
        "classified": classified,
        "skipped_user_overrides": skipped,
        "total_processed": classified + skipped,
    }


def repair_existing_classifications(db: Session) -> dict:
    """Re-evaluate non-user transactions and fix incorrect classification.

    This handles two cases:
    1. Transactions previously misclassified as INTERNAL_TRANSFER that should
       be EXPENSE (e.g. eSewa Load to an external wallet).
    2. Transactions previously misclassified as EXPENSE that should be
       INTERNAL_TRANSFER candidates (e.g. eSewa Load to an owned wallet that
       was repaired incorrectly by an earlier version of this function).

    Confirmed transfer pairs (classification_source='MATCHING', transfer_group_id set)
    are left to repair_orphaned_pairs() in internal_transfer.py — do not break them here.
    """
    # Only touch transactions not confirmed by the matching service.
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.classification_source != "USER",
            Transaction.classification_source != "MATCHING",
        )
        .all()
    )

    user_esewa_numbers = {
        acc.account_number
        for acc in db.query(Account)
        .filter(Account.institution == "ESEWA", Account.account_number.isnot(None))
        .all()
    }

    repaired = 0

    for txn in transactions:
        result = classify_transaction(txn, user_esewa_numbers=user_esewa_numbers)

        current_kind = txn.transaction_kind
        new_kind = result["transaction_kind"]

        if current_kind == new_kind:
            continue  # already correct

        # Apply the corrected classification.
        # For transactions reclassified AWAY from INTERNAL_TRANSFER, also clear
        # stale transfer flags (but only when there's no confirmed group).
        if new_kind != TransactionKind.INTERNAL_TRANSFER and txn.transfer_group_id is None:
            txn.is_internal_transfer = None

        txn.transaction_kind = new_kind
        txn.classification_source = result["classification_source"]
        txn.classification_confidence = result["classification_confidence"]
        txn.classification_reason = result["classification_reason"]
        if "category" in result:
            txn.category = result["category"]
        if "merchant" in result:
            txn.merchant = result["merchant"]
        txn.updated_at = datetime.now(timezone.utc)
        repaired += 1

    db.commit()

    return {"repaired_transactions": repaired}
