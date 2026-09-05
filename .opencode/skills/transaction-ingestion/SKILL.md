---
name: transaction-ingestion
description: Design or modify ingestion of personal financial transaction files including eSewa XLS exports and bank PDF statements.
---

# Transaction Ingestion

Use this skill when working with:

- transaction imports
- CSV, XLS or PDF statement parsing
- source adapters
- transaction normalisation
- duplicate detection
- statement reconciliation
- transfer detection
- transaction classification

The main goal is to ingest financial data safely, consistently and without losing information.

Financial correctness is more important than convenience.

---

## Core Principle

Always preserve the original financial data.

Do not delete, merge, modify or ignore a transaction simply because it appears to be:

- an internal transfer
- an expense
- income
- a refund
- a bank fee
- interest
- tax
- a duplicate candidate
- difficult to classify

Parsing, deduplication, classification and analytics are separate responsibilities.

---

## Required Processing Flow

Every import should conceptually follow:

FILE
→ SOURCE DETECTION
→ IMPORT RECORD
→ RAW INGESTION
→ PARSING
→ NORMALISATION
→ VALIDATION
→ STATEMENT RECONCILIATION
→ DEDUPLICATION
→ CLEAN TRANSACTION INSERT
→ TRANSACTION CLASSIFICATION
→ TRANSFER MATCHING
→ ANALYTICS

Do not perform semantic classification inside the source parser unless it is required to interpret the source format.

The parser should primarily answer factual questions such as:

- what date did the transaction occur?
- what amount was withdrawn or deposited?
- what description did the source provide?
- what was the resulting balance?

Classification should happen later.

---

# Source Adapters

Each financial institution or statement format should have its own parser.

Example:

parsers/
    base.py
    esewa.py
    nabil.py
    global_ime.py

Each parser must output the same canonical transaction structure.

Do not build source-specific logic directly into shared transaction-processing code.

---

# Currently Supported Sources

## eSewa

The current known eSewa source is an XLS statement export.

The eSewa parser should:

- inspect the actual XLS column structure
- preserve the source transaction/reference identifier when available
- preserve the raw transaction description
- preserve debit/credit direction
- preserve balance when provided
- convert dates into the canonical timestamp format
- avoid assuming that wallet loads are income

Do not rely on manually modified spreadsheets.

The parser must support the original exported structure.

---

## Nabil Bank

The current known Nabil source is an electronic account statement in PDF format.

Known statement-level fields include:

- From Date
- To Date
- Opening Balance
- Closing Balance
- Currency Code

Known transaction columns include:

- S.N
- Transaction Date
- Description
- Withdraw
- Deposit
- Balance

The Nabil parser must:

1. extract transaction rows from the PDF
2. preserve the raw description exactly
3. recognise Withdraw as money leaving the account
4. recognise Deposit as money entering the account
5. preserve the Balance column
6. exclude the "Opening Balance" row from transaction records
7. preserve opening and closing balance as statement metadata
8. handle multi-line descriptions
9. handle statements containing multiple pages
10. ignore repeated page headers and footers
11. detect extraction failures rather than silently continuing

Prefer deterministic PDF text/table extraction.

Do not use OCR unless the PDF does not contain usable embedded text.

If OCR is required, treat the extracted financial values as lower confidence and validate them carefully.

---

# Canonical Transaction Structure

Each parser should return a canonical structure with fields such as:

transaction_id
source
account_id

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

statement_import_id

transaction_kind
category
subcategory
merchant

is_internal_transfer
transfer_group_id

classification_source
classification_confidence
classification_reason

created_at
updated_at

Not every source will provide every field.

Missing source fields should normally be stored as null rather than guessed.

---

# Amount Convention

Canonical amounts should use a consistent sign convention:

Money entering the account:
positive amount

Money leaving the account:
negative amount

Example:

Nabil Withdraw = 5,010

Canonical:

amount = -5010.00
debit_amount = 5010.00
credit_amount = null

Example:

Nabil Deposit = 500

Canonical:

amount = 500.00
debit_amount = null
credit_amount = 500.00

Keep original debit and credit values where useful for auditing.

---

# Raw Data Preservation

The system should preserve enough raw information to reproduce or audit the transformation.

Where practical, store:

- original filename
- source
- source row number
- original description
- original date representation
- original debit value
- original credit value
- original balance
- source reference
- original parsed row payload

Never overwrite raw financial values with AI-generated values.

---

# Import Tracking

Every uploaded file should create an import record.

Recommended fields:

import_id
filename
file_hash
source
account_id

period_from
period_to

opening_balance
closing_balance
currency

uploaded_at

rows_read
rows_parsed
rows_inserted
duplicate_rows
invalid_rows

reconciliation_difference

status
error_message

Possible statuses:

PENDING
PARSING
VALIDATING
READY
IMPORTED
FAILED
NEEDS_REVIEW

---

# Import Idempotency

Imports must be idempotent.

Uploading the same file multiple times must not create duplicate transactions.

Uploading overlapping statements must also not create duplicates.

Example:

Statement A:
1 August → 10 August

Statement B:
5 August → 15 August

Transactions already imported from 5–10 August must not be inserted again.

Only genuinely new transactions should be added.

---

# File-Level Duplicate Detection

Calculate a hash of the uploaded file.

If exactly the same file has already been successfully imported, the application may warn the user.

However, file-level duplicate detection is not sufficient.

Two different files can contain overlapping transactions.

Transaction-level deduplication is always required.

---

# Transaction Deduplication

Prefer source-provided unique transaction identifiers where reliable.

Possible priority:

1. source transaction/reference ID
2. source-specific stable identifier
3. deterministic transaction fingerprint

Never rely solely on:

date + amount + description

because legitimate identical transactions may exist.

A fallback fingerprint may use fields such as:

source
account_id
transaction timestamp
amount
description
reference number
balance_after

The exact fingerprint should be source-specific where necessary.

Do not mark transactions as duplicates only because they look similar.

---

# Duplicate Review

If duplicate detection is uncertain:

do not silently discard the row.

Record it as a possible duplicate or flag it for review.

Prefer preserving uncertain financial data over incorrectly deleting a valid transaction.

---

# Statement Reconciliation

Where opening and closing balances are available, reconcile the statement.

For a standard bank statement:

calculated_closing_balance =
opening_balance
+ total_deposits
- total_withdrawals

Compare this with the reported closing balance.

For example:

opening balance = 266,744.21
+ deposits
- withdrawals
= expected closing balance

The expected result should match the statement's closing balance within the defined monetary tolerance.

If reconciliation fails:

- do not silently ignore the difference
- record the difference
- flag the statement
- prevent automatic finalisation if the discrepancy is material

Possible causes include:

- missing transactions
- parsing errors
- duplicate extracted rows
- incorrect numeric parsing
- multi-line PDF extraction issues
- OCR errors

---

# Opening Balance Rows

Rows labelled as opening balance are statement metadata.

They must not be inserted as normal financial transactions.

Example:

2026-07-10
Opening Balance
266,744.21

This represents the starting account state, not income.

---

# Transaction Classification

All valid transactions should be stored before semantic classification.

Initial transaction kinds may include:

EXPENSE
INCOME
INTERNAL_TRANSFER
REFUND
BANK_FEE
INTEREST
TAX
UNKNOWN

Classification should happen after ingestion and deduplication.

Do not remove a transaction because it is classified as an internal transfer.

---

# Internal Transfers

Movement between accounts owned by the same user is not income or expense.

Examples:

- Nabil → eSewa
- eSewa → Nabil
- Nabil → another user-owned bank account
- one wallet → another user-owned account

Both sides should remain stored.

Example:

Nabil:

amount = -200

eSewa:

amount = +200

These may be linked using:

transfer_group_id

Internal transfers should be excluded from:

- expense totals
- income totals
- spending-category totals

But retained for:

- account balances
- cash-flow history
- reconciliation
- net-worth calculations
- auditing

---

# Transfer Matching

Transfer detection may use:

- equal and opposite amounts
- transaction dates/timestamps
- source account
- destination account
- description
- wallet/bank identifiers
- nearby transactions
- historical transfer patterns
- AI classification

Prefer matching both sides of the transfer when possible.

A description such as:

"eSewa Load"

is useful evidence but should not automatically prove that a transaction is an internal transfer.

---

# AI Classification

AI may help classify transactions using:

- description
- amount
- transaction date
- source
- account
- matching transactions
- historical classifications
- merchant mappings
- user corrections

AI must not modify raw transaction data.

AI classification should record:

classification_source
classification_confidence
classification_reason

Example:

transaction_kind = INTERNAL_TRANSFER
classification_source = AI
classification_confidence = 0.97
classification_reason = "Matching eSewa credit with equal amount detected on the same date."

---

# Classification Priority

Prefer deterministic and user-controlled classification before AI.

Suggested order:

1. explicit user-defined rule
2. previous user correction
3. known merchant mapping
4. deterministic transfer matching
5. deterministic source rule
6. AI classification
7. manual review

User corrections must override AI classifications.

---

# Low-Confidence Classification

Do not force uncertain classifications.

If confidence is low:

transaction_kind = UNKNOWN

or mark the transaction as requiring review.

The application should allow the user to correct classifications.

---

# Merchant Normalisation

Preserve:

description_raw

and derive:

description_clean
merchant

Example:

description_raw:

MPAY FPQR,49554221hCSy,BMGG,Remarks 1

Possible derived value:

merchant = BMGG

Do not destroy the original description.

---

# Validation Rules

At minimum validate:

- required columns are present
- date values can be parsed
- monetary values can be parsed
- debit and credit values are logically valid
- transaction amount can be derived
- source rows are not accidentally repeated
- statement totals reconcile where possible
- opening balance rows are excluded
- invalid rows are recorded
- duplicate handling is deterministic

---

# Import Count Validation

The import should reconcile operationally.

For example:

rows_read =
rows_inserted
+ duplicate_rows
+ invalid_rows

If additional statuses exist, include them explicitly.

Never make rows disappear without explanation.

---

# Error Handling

Never silently ignore parsing errors.

Invalid or ambiguous rows should be:

- stored for review where appropriate
- associated with the import
- accompanied by an error reason

Examples:

INVALID_DATE
INVALID_AMOUNT
MISSING_DESCRIPTION
PDF_EXTRACTION_ERROR
DUPLICATE_CANDIDATE
UNSUPPORTED_STRUCTURE

---

# Logging

Logs should help diagnose failures without exposing unnecessary sensitive data.

Do not log:

- passwords
- authentication tokens
- account credentials
- API secrets

Avoid logging complete financial statements.

Prefer identifiers such as:

import_id
transaction_id
source
error type

---

# Extensibility

Adding another institution should primarily require creating another parser.

Example:

parsers/
    base.py
    esewa.py
    nabil.py
    global_ime.py
    nic_asia.py

Shared ingestion logic should not need major modification when adding a new source.

---

# Testing Requirements

Every parser should have tests using anonymised sample statements.

Test at minimum:

- successful parsing
- date conversion
- amount conversion
- debit/credit handling
- duplicate detection
- repeated import
- overlapping statement import
- malformed rows
- missing fields
- multi-line descriptions
- opening balance exclusion
- reconciliation
- internal-transfer candidates

---

# Important Development Rule

Do not make assumptions about a financial statement format when a real sample is available.

Inspect the actual source file first.

If the source format changes, update the source-specific parser rather than weakening the canonical model.

Financial correctness, traceability and reproducibility take priority over convenience.