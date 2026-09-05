# Statement Ingestion

Supported sources are isolated behind the parser registry in
`backend/app/services/import_service.py`:

- `ESEWA`: legacy XLS parser
- `NABIL`: embedded-text PDF parser with Nabil-specific geometry
- `STANDARD_CHARTERED`: embedded-text PDF table parser

## Standard Chartered (Verified)

The verified sample is a one-page transaction-history PDF for 25/07/2026 to
23/08/2026. It contains usable embedded text and a five-column table:
`Date`, `Description`, `Withdrawal`, `Deposit`, and `Balance`.
The sample account is `32382575201`, currency is `NPR`, and the available and
ledger ending balance is `63177.00`.

The parser uses Standard Chartered's extracted table rows, not Nabil geometry.
Descriptions can contain multiple visual lines and are whitespace-normalized
for the canonical description while the original cell remains in `raw_payload`.
Withdrawals become negative `Decimal` amounts and deposits become positive.
The fingerprint includes source, account, date, debit, credit, balance, and
description, so repeated and overlapping imports are idempotent without
assuming descriptions are unique.

`SMS ALERT FEE` and `IBFT CHARGES` are deterministic bank-fee candidates.
Other `IBFT` transactions are internal-transfer candidates and are not
automatically counted as consumption. Salary-looking credits retain their raw
description and use the existing positive-income fallback until a stronger
salary rule is established.