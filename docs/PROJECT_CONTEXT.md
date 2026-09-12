# Personal Finance AI — Project Context

## Purpose of This File

This file contains durable project memory.

Important verified project knowledge must be stored here rather than relying on chat history.

Agents working on this project should read this document before substantial implementation work.

Update this file automatically when new stable project knowledge is verified through:

* actual source files
* tests
* implemented behaviour

Do not record temporary debugging information or abandoned experiments.

---

# Project Goal

Build a personal finance tracking application that consolidates financial transactions from multiple accounts.

The initial sources are:

* eSewa wallet
* Nabil Bank

The user currently obtains statements manually and uploads them to the application.

Direct bank/eSewa API integration is NOT required for the initial version.

The initial ingestion formats are:

* eSewa → XLS
* Nabil Bank → PDF

Future sources should be supported through additional source-specific parsers.

Standard Chartered is now supported through a separate embedded-text PDF
adapter. Its verified sample is a one-page five-column transaction table for
25/07/2026 through 23/08/2026; see `docs/INGESTION.md` for the stable details.

Gmail Nabil transaction-alert ingestion supports local development with
`GOOGLE_REDIRECT_URI=http://localhost:8000/api/gmail/oauth/callback` while
production keeps its Render callback in the Render environment. Gmail OAuth
tokens are encrypted with the environment-specific `GMAIL_TOKEN_ENCRYPTION_KEY`
and local sync uses the local PostgreSQL database. Gmail search is restricted to
`from:txn-alert@nabilbank.com` by default; processed Gmail message IDs and
transaction fingerprints make manual sync idempotent.

Nabil Gmail alerts may be `multipart/alternative` or nested MIME messages
with an HTML table whose header row is separate from its value row. The Gmail
ingestion path requests `format=full`, prefers decoded `text/html`, falls back
to `text/plain`, and maps the labeled table columns to the existing canonical
transaction model. Surrounding masked account text is used for NABIL account
mapping when it is outside the table.

NABIL Gmail account mapping normalizes display formatting and supports masked
account numbers generically. Literal digits must match the stored full account,
mask runs (`#`, `*`, or `x`) match the same number of digits, and the complete
normalized account length must match. Multiple masked matches are rejected as
ambiguous rather than guessed.

Gmail sync keeps message-level and transaction-level deduplication separate:
`IMPORTED` and `DUPLICATE` Gmail message records count as
`emails_already_processed`, while only a matching canonical transaction hash
counts as `transaction_duplicates`. Failed message records are retried rather
than treated as already processed. Gmail fingerprints include account, full
transaction timestamp, debit/credit direction, amount, balance, and remarks.

Gmail sync is quota-efficient: normal runs request one page of at most 50
message IDs using only `from:txn-alert@nabilbank.com`, check local
`gmail_messages` before fetching any body, and fetch only new or retryable
messages. Controlled historical backfill uses the same bounded page size and
returns a `next_page_token`. Gmail 403 quota errors and 429 rate limits use
exponential backoff; exhausted quota stops the current batch and reports
`quota_deferred` without marking the sync successful.

The dashboard uses one shared filter context for summary, category and account
spending, monthly trend, account balances, budget actuals, comparisons, and the
filtered transaction list. Period comparisons are calculated server-side for
the selected date window versus the immediately preceding equivalent window.
Dashboard category edits use the existing transaction classification update API
and refresh analytics without a full page reload.

NABIL PDF and Gmail alert imports use a cross-source duplicate matcher before
Gmail insertion. It requires the same account, signed Decimal amount, and
post-transaction balance, preferring the same calendar date and allowing a
single-day fallback. Descriptions are supporting context only. A matched Gmail
message is linked to the existing transaction with status
`MATCHED_EXISTING_TRANSACTION`; it is not inserted as a second canonical row.

The authenticated Gmail reset-and-resync operation deletes only transactions
whose source is `GMAIL_TRANSACTION_ALERT` and clears that connection's
`gmail_messages` records. It preserves accounts, budgets, statement/manual
transactions, matched statement transactions, and the encrypted Gmail OAuth
connection, then starts a fresh sync using the cross-source matcher.

The standard editable category options include `Lunch`, `Home Expense`, and `Petrol / Gas`.

Dashboard drill-downs use the server-side `/api/analytics/drilldown` endpoint.
Summary cards, spending categories, and account rows pass the same active
dashboard filters and return explainable aggregate statistics plus the
contributing transactions. Balance drill-downs reuse latest `balance_after`
per-account logic rather than summing transactions. Monthly trend is collapsed
by default and can be expanded on demand.
The drill-down view is rendered through a `document.body` portal with a
viewport-level backdrop, Escape/backdrop close behavior, and body scroll lock;
only the modal body scrolls when its content exceeds the viewport.

Dashboard custom date filters support AD and Bikram Sambat display/input modes
through the frontend `dateUtils.ts` wrapper around `nepali-date-converter`.
Selected BS dates are converted immediately to local Gregorian `YYYY-MM-DD`
values before being sent to the existing analytics and transaction APIs; no
database or backend date representation changes are required.
The dashboard also provides a `This Nepali Month` preset, whose BS month
boundaries are converted to the corresponding Gregorian range before filtering.
They are exposed alongside categories already used by stored transactions.

Gmail conversation threads are not ingestion units. The sync uses
`users.messages.list` and fetches each returned `message.id` independently with
`messages.get(format="full")`. Multiple messages sharing one Gmail `threadId`
therefore receive separate parsing, message-status, duplicate checks, and
transactions; `threadId` is never the primary deduplication key.

---

# Core Product Flow

```text
Financial Statement
        ↓
Source Detection / Selection
        ↓
Statement Import Record
        ↓
Raw Extraction
        ↓
Source-Specific Parser
        ↓
Canonical Normalisation
        ↓
Validation
        ↓
Reconciliation
        ↓
Transaction Deduplication
        ↓
Database Storage
        ↓
Classification
        ↓
Internal Transfer Matching
        ↓
Analytics
        ↓
AI Insights
```

Phase 1 focuses primarily on everything through database storage and basic transaction viewing.

---

# Core Financial Rules

## Preserve Transactions

All valid financial transactions should be stored.

Do not remove transactions during ingestion because they appear to be:

* internal transfers
* expenses
* income
* refunds
* bank fees
* tax
* interest
* unusual transactions

Classification occurs after ingestion.

---

## Internal Transfers

Moving money between accounts owned by the same user does not represent income or spending.

Example:

```text
Nabil Bank
-5000

eSewa
+5000
```

Both transactions remain stored.

Future classification may identify them as:

`INTERNAL_TRANSFER`

They should then be excluded from income and expense analytics while remaining part of:

* account history
* account balances
* reconciliation
* net-worth tracking
* auditing

Internal-transfer detection is NOT part of the initial parser responsibility.

## eSewa Load Rule (Verified)

`eSewa Load` in a Nabil bank statement description does NOT imply an internal transfer on its own.

Classification order for `eSewa Load <wallet_number>` transactions:

1. Extract the destination wallet number using `eSewa\s+Load\s+(\d+)`.
2. If the wallet number is NOT in the user's registered eSewa accounts: classify as `EXPENSE` immediately.
3. If the wallet number IS a user-owned eSewa wallet: classify as `INTERNAL_TRANSFER` candidate.
4. The `internal_transfer` matching service then pairs the candidate with the corresponding eSewa credit (`Money transferred from NABIL BANK LTD.`) using amount and date matching.
5. When a pair is confirmed, BOTH sides are updated atomically to `INTERNAL_TRANSFER` with the same `transfer_group_id`.
6. Only transactions confirmed by the matching service (classification_source=MATCHING) receive `is_internal_transfer=True` and `transfer_group_id`.

The eSewa wallet number is obtained from the eSewa statement metadata field `Generated by`. The import service persists this to `Account.account_number` on import, replacing placeholder values such as `ESEWA_DEFAULT`.

Do NOT classify a transaction as internal transfer solely because the description contains `eSewa Load`. Account ownership must be confirmed first.

Confirmed cross-account transfer matching runs after automatic classification and
can override generic positive-income or negative-expense fallbacks when opposite
signed transactions have equal amounts, close dates, different owned accounts,
and transfer evidence such as `IBFT` or `ACCOUNTFT`. Confirmed pairs are marked
atomically with `transaction_kind=INTERNAL_TRANSFER`, `is_internal_transfer=true`,
the same `transfer_group_id`, and `classification_source=MATCHING`. Automatic
reclassification skips `USER` and `MATCHING` records, and the repair operation
can safely rerun classification and matching for existing data.



---

# Technology Decisions

## Backend

* Python
* FastAPI
* SQLAlchemy
* Alembic

## Database

* PostgreSQL

## Frontend

* React
* TypeScript

Next.js or Vite React may be used depending on which provides the simplest maintainable implementation.

## Authentication

* Supabase Auth
* Frontend sends user session access token via `Authorization: Bearer <token>`
* Backend verifies asymmetric signing keys (`ES256`, `RS256`) dynamically from Supabase project JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) with cached keys (`PyJWKClient`)
* Legacy symmetric HS256 fallback supported when `SUPABASE_JWT_SECRET` is configured
* Claims verification: audience `authenticated`, `role != 'anon'`, and user `sub` presence
* `SUPABASE_JWT_SECRET` is not required on Render when `SUPABASE_URL` is configured

## Data Processing

* normal Python
* source-specific libraries
* `Decimal` for financial values

## AI

OpenAI API may be introduced in later phases.

AI is not required for Phase 1 ingestion.

---

# Architecture Principles

Use conceptual layers:

```text
RAW
↓
CLEAN
↓
ENRICHED
```

## RAW

Preserve original source information.

Examples:

* filename
* raw description
* source timestamp
* debit
* credit
* balance
* source reference
* parsed raw payload

## CLEAN

Canonical transaction representation.

## ENRICHED

Future semantic information such as:

* category
* merchant
* transaction kind
* transfer matching
* AI classification

---

# Canonical Transaction Direction

Use the following sign convention:

## Money entering account

Positive amount.

Example:

```text
Deposit = 500
amount = 500.00
```

## Money leaving account

Negative amount.

Example:

```text
Withdrawal = 500
amount = -500.00
```

Source debit and credit values should still be preserved where available.

All authoritative money calculations must use exact decimal arithmetic.

---

# VERIFIED SOURCE SPECIFICATION — eSEWA

## File Format

Current sample:

`sample_esewa.xls`

The file is a genuine legacy Excel XLS / BIFF file.

Observed OLE2 signature:

```text
D0 CF 11 E0 A1 B1 1A E1
```

It is NOT XLSX.

Use a legacy XLS-compatible parser such as `xlrd`.

---

# eSewa Workbook Structure

Workbook sheet:

`eSewa Report`

Current sample dimensions:

```text
58 rows
8 columns
```

The workbook contains:

1. statement metadata
2. transaction-table header
3. transaction rows
4. totals
5. transaction-status summary

It is not a simple table starting at the first row.

---

# eSewa Metadata

Verified metadata includes fields such as:

* Statement Report
* From Date
* To Date
* Generated On
* Status
* Channel
* Dr/Cr
* Generated by

Current sample period:

approximately:

```text
2026-07-09
to
2026-08-08
```

These rows are metadata and must not become transactions.

---

# eSewa Transaction Columns

Transaction header appears around worksheet row index 8 in the current sample.

Verified columns:

1. Reference Code
2. Date Time
3. Description
4. Dr.
5. Cr.
6. Status
7. Balance (NPR)
8. Channel

Parser implementation should identify the header semantically where practical rather than assuming the physical row can never change.

---

# eSewa Sample Transaction Count

Current verified sample contains:

```text
41 transactions
```

The transaction data occupies approximately worksheet rows 9–49.

Current sample is ordered:

```text
NEWEST → OLDEST
```

Do not assume chronological ascending order.

---

# eSewa Example

Verified sample row:

```text
Reference Code:
1O2GEF1

Date Time:
2026-08-07 20:21:25.0

Description:
Paid for Daraz Kaymu Private Limited

Dr:
1029.0

Cr:
0.0

Status:
COMPLETE

Balance:
407.64

Channel:
Linked Esewa Payment
```

Canonical amount:

```text
-1029.00
```

---

# eSewa Debit / Credit Rules

## Debit

Dr > 0 means money left the wallet.

Canonical:

```text
amount = -Dr
```

## Credit

Cr > 0 means money entered the wallet.

Canonical:

```text
amount = +Cr
```

Preserve source debit and credit separately.

---

# CRITICAL eSewa Deduplication Rule

The eSewa `Reference Code` is NOT unique per financial transaction row.

It must NOT be used alone as the transaction uniqueness key.

Do NOT create:

```text
UNIQUE(source, source_reference)
```

Verified duplicate-reference examples exist.

---

# eSewa Duplicate Reference Example 1

Reference:

```text
1ME7CUJ
```

appears for two legitimate rows:

```text
Charge on payment for Siddhartha Capital -Meroshare
Debit: 5.65
```

and:

```text
Paid for 1301090000446131-MEWZC-Both
Debit: 150.00
```

Both are legitimate separate financial records.

Both must remain stored.

---

# eSewa Duplicate Reference Example 2

Reference:

```text
1LY10GX
```

appears for:

```text
Bank transfer charges
Debit: 10.00
```

and:

```text
Money transferred to LAXMI SUNRISE BANK LTD.
Debit: 150.00
```

Both must remain stored.

---

# eSewa Fingerprint Strategy

Use a deterministic row-level fingerprint.

Suggested components:

```text
source
account_id
reference_code
transaction_timestamp
debit
credit
description_raw
balance_after
channel
```

Normalise fields deterministically.

Hash using SHA-256.

The goal:

```text
same statement row
→ same hash
```

while:

```text
same reference + different legitimate financial row
→ different hash
```

Database-level duplicate protection should use the transaction fingerprint rather than source reference alone.

---

# eSewa Footer / Summary Rows

After the transaction table, the current sample includes a Total row.

Verified totals:

```text
Total Debit:
8548.15

Total Credit:
8446.75
```

Status-summary rows follow, including:

* Total
* Pending
* Complete
* canceled
* Time out

Current sample summary includes:

```text
Total: 41
Pending: 0
Complete: 41
```

None of these rows are financial transactions.

They must be excluded from transaction ingestion.

---

# eSewa Balance Validation

Current sample contains running balances.

Verified implied opening wallet balance:

```text
509.04
```

Current statement totals:

```text
Credits:
8446.75

Debits:
8548.15
```

Calculation:

```text
509.04
+ 8446.75
- 8548.15
= 407.64
```

Newest transaction balance:

```text
407.64
```

The supplied sample therefore reconciles internally.

Because the source is newest-first, balance-chain validation must account for ordering.

---

# eSewa Potential Internal Transfers

Current sample contains descriptions such as:

```text
Money transferred from NABIL BANK LTD.
```

Verified examples include incoming amounts such as:

```text
1000
5000
```

These are likely future internal-transfer candidates.

They must NOT automatically become income.

They must NOT be removed during ingestion.

---

# VERIFIED SOURCE SPECIFICATION — NABIL BANK

## File Format

Current sample:

`sample_nabil.pdf`

Verified file type:

```text
PDF 1.5
```

The PDF contains usable embedded text.

OCR is NOT required for the current source format.

Do not use OCR unless a future statement genuinely lacks extractable text.

---

# Nabil Document Structure

Current verified sample:

```text
3 pages
```

The document repeats:

* account metadata
* table headers

across pages.

Page headers and footers must not become transactions.

Current sample contains:

```text
24 transactions
```

Verified serial-number sequence:

```text
1 through 24
```

---

# Nabil Statement Metadata

Verified current sample:

```text
From Date:
2026-07-10

To Date:
2026-08-09

Opening Balance:
266744.21

Closing Balance:
215366.99

Currency:
NPR
```

Other information exists in the statement, including:

* account-holder information
* account number
* accrued interest
* interest rate

The application should avoid storing unnecessary sensitive identity information.

Full account numbers should not be required for the financial model.

---

# Nabil Transaction Columns

Verified columns:

1. S.N
2. Transaction Date
3. Description
4. Withdraw
5. Deposit
6. Balance

---

# Nabil PDF Geometry

Stable vertical column boundaries were observed approximately at:

```text
40
130
260
410
520
650
770
```

Approximate regions:

```text
40–130
S.N

130–260
Transaction Date

260–410
Description

410–520
Withdraw

520–650
Deposit

650–770
Balance
```

These boundaries were stable across the supplied three-page sample.

---

# IMPORTANT Nabil Parsing Finding

Generic `pdfplumber.extract_tables()` is NOT sufficiently reliable as the final parser.

Observed issues included:

* unrelated metadata tables being detected
* multiple tables found on each page
* default table selection not always choosing the transaction table
* missing transaction rows under default detection
* inconsistent behaviour across pages

Therefore:

DO NOT implement the Nabil parser as:

```text
find tables
→ choose largest table
→ assume rows are transactions
```

That approach has already been investigated and rejected.

---

# Nabil Horizontal Text Strategy Finding

An experiment using explicit vertical boundaries with:

```text
horizontal_strategy = "text"
```

generated many physical text rows rather than one row per logical transaction.

Therefore:

```text
one extracted text row
!=
one financial transaction
```

The final parser must reconstruct logical transactions.

---

# Nabil Required Parsing Strategy

Use deterministic geometry-based extraction.

Recommended algorithm:

1. open PDF with `pdfplumber`
2. process every page
3. extract words with coordinates
4. identify the transaction region
5. use verified x-boundaries to assign words to columns
6. detect transaction anchors using:

   * serial number
   * transaction date
   * withdrawal/deposit
   * balance
7. group vertically related words into one logical transaction
8. reconstruct description fragments in reading order
9. ignore repeated headers
10. ignore page footers
11. validate transaction sequence
12. validate running balances
13. perform final reconciliation

If future Nabil layouts change, adapt the source-specific parser rather than weakening the canonical model.

---

# Nabil Multi-Line Descriptions

Descriptions may occupy multiple visual lines.

Verified examples resemble:

```text
MPAY
LXBLNPKA;16615826630
40001,3410017508963,re
```

and:

```text
MPAY
FPQR,49679285JC1p,AL
L STAR JEWELLERY
PVT LTD
```

These fragments belong to a single logical transaction.

Another verified example:

```text
eSewa Load 9841866292,
286346150
```

The parser must preserve all relevant fragments in `description_raw`.

Do not rely purely on PDF raw text order.

Use geometry and transaction boundaries.

---

# CURRENT DESIGN — Manual Transactions and Monthly Plans

Manual transactions reuse the canonical `transactions` table. They use
`source=MANUAL`, `is_manual=true`, `classification_source=USER`, a nullable
`statement_import_id`, and a `payment_method` of `CASH` or `MANUAL_OTHER`.
The API accepts a positive human-entered amount and applies the canonical
sign from `direction`; imported transaction financial fields remain immutable.

Monthly plans are stored in `monthly_budgets` with unique year/month rows and
`budget_allocations` keyed by category. Allocation types distinguish
`CONSUMPTION` from `INVESTMENT`. Budget analytics expose planned and actual
income, consumption, investment, saving, internal transfers, category
variance, percentage used, and unplanned categories.

Genuine income and consumption exclude confirmed internal transfers. Saving is
reported as genuine income minus consumption; investment is shown separately
and is not silently merged into lifestyle spending. Investment actuals are
currently identifiable by the `Investment` category, which is a documented
limitation until investment accounts/assets are modelled.

---

# Nabil Opening Balance

The Opening Balance row is statement metadata.

It is NOT a financial transaction.

Do not insert it into the canonical transaction table.

Store:

```text
opening_balance = 266744.21
```

on the statement import.

Closing Balance is also statement-level metadata.

---

# Nabil Debit / Credit Rules

## Withdraw

Withdraw means money left the bank account.

Example:

```text
Withdraw:
5010.00
```

Canonical:

```text
amount = -5010.00
```

## Deposit

Deposit means money entered the bank account.

Example:

```text
Deposit:
500.00
```

Canonical:

```text
amount = 500.00
```

Blank cells or `-` represent absence of a debit/deposit amount rather than a monetary value.

---

# VERIFIED Nabil Reconciliation

Current sample:

```text
Opening Balance:
266744.21

Total Deposits:
12475.30

Total Withdrawals:
63852.52

Closing Balance:
215366.99
```

Verified calculation:

```text
266744.21
+ 12475.30
- 63852.52
= 215366.99
```

Difference:

```text
0.00
```

The supplied Nabil fixture therefore reconciles exactly.

This must be enforced by automated tests.

---

# Nabil Running-Balance Validation

Where running balance exists, validate each chronological transaction:

```text
previous balance
+ deposit
- withdrawal
=
current balance
```

Verified example:

```text
Opening:
266744.21

Withdrawal:
5010.00

Expected:
261734.21

Reported:
261734.21
```

Next:

```text
Previous:
261734.21

Deposit:
500.00

Expected:
262234.21

Reported:
262234.21
```

This validation helps locate missing or incorrectly parsed rows.

---

# Nabil Internal Transfer Candidates

The sample contains descriptions such as:

```text
eSewa Load ...
```

These likely represent movement from Nabil to eSewa.

Do not classify them during ingestion.

Do not treat them automatically as expenses.

Store them.

Later transfer matching can compare:

```text
Nabil negative transaction
```

with:

```text
eSewa positive wallet load
```

and potentially classify both as:

```text
INTERNAL_TRANSFER
```

---

# Canonical Transaction Model

The architecture should support fields approximately including:

```text
id

source
account_id
statement_import_id

transaction_date
transaction_timestamp

description_raw
description_clean

amount
debit_amount
credit_amount

currency
balance_after

source_reference
source_row_number

transaction_hash

transaction_kind
merchant
category
subcategory

is_internal_transfer
transfer_group_id

classification_source
classification_confidence
classification_reason

raw_payload

created_at
updated_at
```

Future enrichment fields may remain null during Phase 1.

---

# Account Model

Support multiple financial accounts.

Suggested fields:

```text
id
name
institution
account_type
currency
is_active
created_at
updated_at
```

Possible types:

```text
BANK
WALLET
```

Do not store banking credentials.

---

# Statement Import Model

Statement imports should support information including:

```text
id
source
account_id

filename
file_hash

period_from
period_to

opening_balance
closing_balance
currency

rows_read
rows_parsed
rows_inserted
duplicate_rows
invalid_rows

total_debit
total_credit

reconciliation_difference
reconciliation_status

status
error_message
row_errors

created_at
completed_at
```

Possible import statuses:

```text
PENDING
PARSING
VALIDATING
READY
IMPORTED
FAILED
NEEDS_REVIEW
```

Possible reconciliation statuses:

```text
PENDING
PASSED
FAILED
NOT_AVAILABLE
```

---

# Import Idempotency

This is a critical business rule.

Exact re-upload:

```text
first import
→ transactions inserted

same file again
→ zero new transactions
```

Overlapping statements must also be safe.

Example:

```text
Statement A:
1 Aug – 10 Aug

Statement B:
5 Aug – 15 Aug
```

Rows already stored from 5–10 Aug must not be duplicated.

Only genuinely new rows should be inserted.

---

# File Hashing

Calculate SHA-256 for uploaded statement files.

This detects exact file re-upload.

However:

```text
file hash != transaction deduplication
```

Two different statement files may contain overlapping transactions.

Transaction-level deduplication is always required.

---

# Nabil Transaction Fingerprint

Suggested stable inputs:

```text
source
account_id
transaction date
debit
credit
balance_after
normalised description
```

Normalise description whitespace/line breaks before fingerprinting.

This helps the same logical PDF transaction retain its identity even if line-wrap extraction varies slightly.

Use SHA-256.

---

# Database Duplicate Protection

Transaction fingerprints should be protected by a database-level uniqueness mechanism where appropriate.

Example conceptual rule:

```text
UNIQUE(account_id, transaction_hash)
```

Do not use source reference alone.

---

# Parser Interface

Use a common parser abstraction.

Conceptually:

```text
StatementParser
    parse(file_bytes, filename)
        → ParsedStatement
```

Implement:

```text
EsewaStatementParser
NabilStatementParser
```

A ParsedStatement should support:

```text
source
period_from
period_to
opening_balance
closing_balance
currency

total_debit
total_credit

transactions

warnings
errors
```

Parsed transactions should carry both source information and canonical-ready information.

---

# Import Pipeline

Expected Phase 1 flow:

```text
UPLOAD FILE
↓
COMPUTE FILE HASH
↓
CREATE IMPORT RECORD
↓
SELECT SOURCE PARSER
↓
PARSE
↓
NORMALISE
↓
VALIDATE
↓
RECONCILE
↓
GENERATE TRANSACTION HASHES
↓
CHECK EXISTING TRANSACTIONS
↓
INSERT NEW TRANSACTIONS
↓
UPDATE IMPORT METRICS
↓
RETURN RESULT
```

---

# Testing Requirements

## eSewa Fixture

Tests should verify:

* XLS opens
* correct sheet detected
* 41 transactions parsed
* metadata excluded
* Total row excluded
* status summaries excluded
* debit becomes negative
* credit becomes positive
* source reference preserved
* duplicate references do not collapse legitimate rows
* both `1ME7CUJ` rows survive
* both `1LY10GX` rows survive
* fingerprints differ for legitimate rows sharing reference
* running-balance validation succeeds
* repeated import inserts zero new transactions

## Nabil Fixture

Tests should verify:

* 3 pages
* 24 transactions
* S.N 1–24
* Opening Balance excluded
* Closing Balance excluded from transactions
* From Date = 2026-07-10
* To Date = 2026-08-09
* Opening Balance = 266744.21
* Closing Balance = 215366.99
* Currency = NPR
* multi-line descriptions reconstructed
* withdrawals negative
* deposits positive
* total deposits = 12475.30
* total withdrawals = 63852.52
* running balances pass
* reconciliation difference = 0.00
* repeated import inserts zero new transactions

---

# Current Development Priority

## Phase 1 (IMPLEMENTED)

Financial statement ingestion foundation:

* backend
* PostgreSQL
* accounts
* statement imports
* canonical transactions
* eSewa XLS parser
* Nabil PDF parser
* normalisation
* validation
* reconciliation
* deduplication
* transaction storage
* API
* basic import interface
* tests

## Phase 2 (IMPLEMENTED)

* transaction browsing with advanced filtering (date, account, source, type, category, amount, search)
* dashboard views
* server-side SQL-aggregated filtering
* shared filter builder architecture

## Phase 3 (IMPLEMENTED / IN PROGRESS)

* transaction classification via deterministic rules
* auto-classification on import
* internal-transfer matching
* user classification overrides
* merchant mapping (via deterministic rules)

## Phase 4 (IMPLEMENTED / IN PROGRESS)

* financial dashboard with dynamic KPI cards
* spending by category pie chart and table
* income by category breakdown
* spending by account breakdown
* monthly income/spending trend analysis
* unknown transactions alert banner

## Phase 5 (NOT STARTED)

* AI-assisted categorisation
* financial insights
* anomaly explanation

## Phase 6 (NOT STARTED)

* conversational financial assistant

Do not implement future phases unless explicitly requested or required by the current task.

---

# Architecture Notes

* **Filtering:** The application uses a shared `filter_service.py` to ensure consistent filter application across both transaction list endpoints and analytics aggregation endpoints.
* **Analytics:** Financial totals (income, spending, cash flow) and trend metrics are calculated using server-side SQL aggregation. Internal transfers are correctly excluded from income/spending totals and tracked independently.
* **Account balances:** `/api/analytics/accounts` derives each active account's balance from its latest stored transaction with a non-null `balance_after`. Ordering is by transaction date, transaction timestamp when available, then descending source statement row number, with transaction ID as a deterministic final tie-breaker. Optional `account_id` selects one account, and `date_to` returns the latest known balance on or before that date for as-of dashboard totals.
* **Dashboard date filtering:** The dashboard sends optional `date_from` and `date_to` ISO dates to the existing analytics endpoints. Presets are resolved in the browser using local calendar dates; custom ranges use the same server-side filters. An empty range preserves the existing all-time behavior.
* **Classification:** Classification is deterministic and executes automatically after successful statement import. A safe `/api/transactions/reclassify-all` endpoint exists to apply rules to existing records while preserving manual user overrides.
* **Gmail ingestion:** Manual Nabil alert sync is exposed under `/api/gmail`. OAuth uses the read-only Gmail scope, stores encrypted tokens in `gmail_connections`, records message processing in `gmail_messages`, searches only `from:txn-alert@nabilbank.com` by default, and routes valid alerts through the canonical transaction, classification, and transfer-matching services. No scheduled sync or Gmail push notifications are implemented.
* **Gmail duplicates:** Gmail message IDs are the message-ledger key. Gmail transaction fingerprints use timestamp, direction/amount, balance, and remarks, excluding the message ID so repeated delivery of the same alert cannot create a second transaction.

---

# Context Maintenance Rule

This document must evolve with the project.

After a verified change, update this file if it changes stable knowledge.

Examples:

* new bank source
* source layout change
* new parser rule
* deduplication change
* canonical schema change
* reconciliation rule change
* new verified edge case
* technology architecture change

Do not update this file with speculative or temporary information.

The repository, tests and actual source files remain the highest authority.
