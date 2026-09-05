# Data Model

The canonical `transactions` table stores imported and manual records. Manual
records have `source=MANUAL`, `is_manual=true`, nullable
`statement_import_id`, `payment_method`, and user classification metadata.
Imported records retain their statement relationship and source fields.

`monthly_budgets` stores one plan per `year` and `month`, including expected
income and an optional planned saving target. `budget_allocations` stores the
planned amount per category and labels each allocation as `CONSUMPTION` or
`INVESTMENT`.

All monetary columns use `NUMERIC(18, 2)`. Canonical transaction amounts are
positive for money entering an account and negative for money leaving it.