---
name: data-validation
description: Validate transaction imports, deduplication, reconciliation and financial data correctness.
---

# Financial Data Validation

Use this skill whenever validating financial data or changing
transaction-processing logic.

## Core Principle

Row count alone is not sufficient validation.

Validate at multiple levels.

## Import Validation

For every import check:

- input row count
- successfully parsed row count
- invalid row count
- duplicate row count
- newly inserted row count

The numbers must reconcile.

input =
inserted + duplicates + invalid

unless an explicitly documented additional state exists.

## Duplicate Validation

Test:

1. Upload file once.
2. Record transaction count.
3. Upload the exact same file again.
4. Transaction count must not increase.

Also test overlapping exports.

Example:

File A:
August 1–10

File B:
August 5–15

Only August 11–15 transactions should normally be new.

## Financial Reconciliation

Where balances exist, validate that transaction movements agree with
the reported account balance.

Compare:

- total debit
- total credit
- opening balance
- closing balance

## Edge Cases

Always consider:

- identical legitimate transactions
- missing transaction IDs
- transaction reversals
- refunds
- transfers between own accounts
- duplicate exports
- different date formats
- missing values
- negative numbers
- debit/credit represented in separate columns