from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.parsers.nabil_email import NabilEmailParser


HTML_ALERT = """
<html><body><table>
<tr><td>Transaction Date</td><td>2026-09-06 12:37</td></tr>
<tr><td>Transaction Type</td><td>Credit</td></tr>
<tr><td>Transaction Amount</td><td>10,924.00</td></tr>
<tr><td>Available Balance</td><td>204,264.96</td></tr>
<tr><td>Remarks</td><td>FON:IBFT:1846053471:5824:NARBNPKA:RBBANKA:SHIVA H</td></tr>
<tr><td>Account Number</td><td>341####08963</td></tr>
</table></body></html>
"""

REALISTIC_TABLE_ALERT = """
<html><body>
<p>Dear PRAMIT,<br>Greetings!</p>
<p>Please find transaction details for your account number 341#####08963 as below:</p>
<table>
    <tr><th>Transaction Date</th><th>Transaction Type</th><th>Transaction Amount</th><th>Available Balance</th><th>Remarks</th></tr>
    <tr><td>2026-09-11 12:40</td><td>Debit</td><td>25.00</td><td>369,659.96</td><td>NQR-7969339,<br>sandwich-Sandwich Hub NQR-7969339,san</td></tr>
</table>
<p>Contact Nabil support for assistance.</p>
</body></html>
"""


PLAIN_ALERT = """Transaction Date: 2026-09-06 12:38
Transaction Type: Debit
Transaction Amount: 1,269.00
Available Balance: 202,995.96
Remarks: POS PUR/50009142/BHATBH ATEN
"""


def test_parses_html_credit_and_metadata():
    alert = NabilEmailParser().parse(
        HTML_ALERT,
        sender="txn-alert@nabilbank.com",
        received_at=datetime(2026, 9, 6, 12, 38, tzinfo=timezone.utc),
        is_html=True,
    )

    assert alert.transaction_timestamp == datetime(2026, 9, 6, 12, 37, tzinfo=timezone.utc)
    assert alert.is_credit is True
    assert alert.amount == Decimal("10924.00")
    assert alert.balance_after == Decimal("204264.96")
    assert alert.remarks.startswith("FON:IBFT:")
    assert alert.account_number == "341####08963"


def test_plain_text_debit_is_negative_direction():
    alert = NabilEmailParser().parse(PLAIN_ALERT, sender="txn-alert@nabilbank.com")

    assert alert.is_credit is False
    assert alert.amount == Decimal("1269.00")
    assert alert.remarks == "POS PUR/50009142/BHATBH ATEN"


def test_parses_realistic_html_header_and_value_rows():
    alert = NabilEmailParser().parse(
        REALISTIC_TABLE_ALERT,
        sender="txn-alert@nabilbank.com",
        is_html=True,
    )

    assert alert.transaction_timestamp == datetime(2026, 9, 11, 12, 40, tzinfo=timezone.utc)
    assert alert.is_credit is False
    assert alert.amount == Decimal("25.00")
    assert alert.balance_after == Decimal("369659.96")
    assert alert.remarks == "NQR-7969339,sandwich-Sandwich Hub NQR-7969339,san"
    assert alert.account_number == "341#####08963"


def test_missing_required_value_is_rejected():
    with pytest.raises(ValueError, match="transaction_amount"):
        NabilEmailParser().parse(
            "Transaction Date: 2026-09-06 12:37\nTransaction Type: Debit",
            sender="txn-alert@nabilbank.com",
        )
