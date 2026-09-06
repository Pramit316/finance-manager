"""Parser for Nabil transaction alert email bodies."""

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser


@dataclass
class NabilEmailAlert:
    transaction_timestamp: datetime
    is_credit: bool
    amount: Decimal
    balance_after: Decimal | None
    remarks: str
    account_number: str | None
    sender: str
    received_at: datetime | None


class _BodyTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"td", "th", "tr", "br", "p", "div"}:
            self.parts.append("\n")

    def text(self) -> str:
        return "\n".join(self.parts)


class NabilEmailParser:
    """Parse labelled Nabil alerts from HTML, with plain-text fallback."""

    _LABELS = {
        "transaction_date": r"Transaction\s+Date",
        "transaction_type": r"Transaction\s+Type",
        "transaction_amount": r"Transaction\s+Amount",
        "available_balance": r"Available\s+Balance",
        "remarks": r"Remarks?",
        "account_number": r"(?:Account\s+(?:Number|No\.?))",
    }

    def parse(
        self,
        body: str,
        *,
        sender: str,
        received_at: datetime | None = None,
        is_html: bool = False,
    ) -> NabilEmailAlert:
        text = self._to_text(body) if is_html else body
        text = html.unescape(text)
        values = {name: self._extract_value(text, label) for name, label in self._LABELS.items()}

        timestamp = self._parse_datetime(self._required(values, "transaction_date"))
        transaction_type = self._required(values, "transaction_type").strip().lower()
        if transaction_type not in {"credit", "debit"}:
            raise ValueError(f"Unsupported transaction type: {transaction_type}")

        amount = self._parse_decimal(self._required(values, "transaction_amount"))
        balance_text = values.get("available_balance")
        balance = self._parse_decimal(balance_text) if balance_text else None
        remarks = (values.get("remarks") or "").strip()
        account_number = (values.get("account_number") or "").strip() or None

        return NabilEmailAlert(
            transaction_timestamp=timestamp,
            is_credit=transaction_type == "credit",
            amount=amount,
            balance_after=balance,
            remarks=remarks,
            account_number=account_number,
            sender=sender,
            received_at=received_at,
        )

    @staticmethod
    def _to_text(body: str) -> str:
        parser = _BodyTextParser()
        parser.feed(body)
        return parser.text()

    @classmethod
    def _extract_value(cls, text: str, label: str) -> str | None:
        all_labels = "|".join(cls._LABELS.values())
        pattern = rf"(?:^|\n|\r|>)\s*{label}\s*:?\s*(.*?)\s*(?=(?:{all_labels})\s*:?\s*|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return " ".join(match.group(1).split())
        return None

    @staticmethod
    def _required(values: dict[str, str | None], key: str) -> str:
        value = values.get(key)
        if not value:
            raise ValueError(f"Missing required field: {key}")
        return value

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        normalized = value.strip().replace("Z", "+00:00")
        for candidate in (normalized, normalized.replace("/", "-")):
            try:
                result = datetime.fromisoformat(candidate)
                return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"):
            try:
                return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        raise ValueError(f"Invalid transaction date: {value}")

    @staticmethod
    def _parse_decimal(value: str) -> Decimal:
        try:
            return Decimal(value.replace(",", "").strip())
        except (InvalidOperation, AttributeError) as exc:
            raise ValueError(f"Invalid monetary value: {value}") from exc

    @staticmethod
    def parse_received_at(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            result = parsedate_to_datetime(value)
            return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
