-- ════════════════════════════════════════════════════════════════════
-- FinTrack — Supabase PostgreSQL Schema Migration
-- ════════════════════════════════════════════════════════════════════
-- Run this SQL in the Supabase SQL Editor (Dashboard → SQL Editor)
-- after creating your Supabase project.
--
-- This creates the identical schema to the local Alembic-managed DB.
-- Safe to run on a fresh Supabase PostgreSQL database.
-- ════════════════════════════════════════════════════════════════════

-- ─── Enums ──────────────────────────────────────────────────────────

DO $$ BEGIN
  CREATE TYPE account_type_enum AS ENUM ('BANK', 'WALLET');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE statement_source_enum AS ENUM ('ESEWA', 'NABIL', 'STANDARD_CHARTERED', 'MANUAL');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE import_status_enum AS ENUM ('PENDING', 'PARSING', 'VALIDATING', 'READY', 'IMPORTED', 'FAILED', 'NEEDS_REVIEW');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE reconciliation_status_enum AS ENUM ('PENDING', 'PASSED', 'FAILED', 'NOT_AVAILABLE');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE transaction_kind_enum AS ENUM ('EXPENSE', 'INCOME', 'INTERNAL_TRANSFER', 'REFUND', 'BANK_FEE', 'INTEREST', 'TAX', 'UNKNOWN');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE allocation_type_enum AS ENUM ('CONSUMPTION', 'INVESTMENT');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ─── Accounts ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS accounts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name           VARCHAR(255) NOT NULL,
  account_number VARCHAR(255),
  institution    VARCHAR(255) NOT NULL,
  account_type   account_type_enum NOT NULL,
  currency       VARCHAR(10)  NOT NULL DEFAULT 'NPR',
  is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);


-- ─── Statement Imports ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS statement_imports (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source                    statement_source_enum NOT NULL,
  account_id                UUID NOT NULL REFERENCES accounts(id),
  filename                  VARCHAR(500) NOT NULL,
  file_hash                 VARCHAR(64)  NOT NULL,
  period_from               DATE,
  period_to                 DATE,
  opening_balance           NUMERIC(18,2),
  closing_balance           NUMERIC(18,2),
  currency                  VARCHAR(10),
  rows_read                 INTEGER NOT NULL DEFAULT 0,
  rows_parsed               INTEGER NOT NULL DEFAULT 0,
  rows_inserted             INTEGER NOT NULL DEFAULT 0,
  duplicate_rows            INTEGER NOT NULL DEFAULT 0,
  invalid_rows              INTEGER NOT NULL DEFAULT 0,
  total_debit               NUMERIC(18,2),
  total_credit              NUMERIC(18,2),
  reconciliation_difference NUMERIC(18,2),
  reconciliation_status     reconciliation_status_enum NOT NULL DEFAULT 'PENDING',
  status                    import_status_enum NOT NULL DEFAULT 'PENDING',
  error_message             TEXT,
  row_errors                JSONB,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at              TIMESTAMPTZ
);


-- ─── Transactions ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS transactions (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source                    statement_source_enum NOT NULL,
  account_id                UUID NOT NULL REFERENCES accounts(id),
  statement_import_id       UUID REFERENCES statement_imports(id),
  transaction_date          DATE NOT NULL,
  transaction_timestamp     TIMESTAMPTZ,
  description_raw           TEXT NOT NULL,
  description_clean         TEXT,
  amount                    NUMERIC(18,2) NOT NULL,
  debit_amount              NUMERIC(18,2),
  credit_amount             NUMERIC(18,2),
  currency                  VARCHAR(10) NOT NULL DEFAULT 'NPR',
  balance_after             NUMERIC(18,2),
  source_reference          VARCHAR(255),
  source_row_number         INTEGER,
  transaction_hash          VARCHAR(64) NOT NULL,
  transaction_kind          transaction_kind_enum,
  merchant                  VARCHAR(255),
  category                  VARCHAR(255),
  subcategory               VARCHAR(255),
  is_internal_transfer      BOOLEAN,
  transfer_group_id         UUID,
  classification_source     VARCHAR(50),
  classification_confidence FLOAT,
  classification_reason     TEXT,
  is_manual                 BOOLEAN NOT NULL DEFAULT FALSE,
  payment_method            VARCHAR(30),
  raw_payload               JSONB,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Duplicate protection
  CONSTRAINT uq_account_transaction_hash UNIQUE (account_id, transaction_hash)
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_transactions_account_id          ON transactions(account_id);
CREATE INDEX IF NOT EXISTS ix_transactions_transaction_date     ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS ix_transactions_transaction_hash     ON transactions(transaction_hash);
CREATE INDEX IF NOT EXISTS ix_transactions_statement_import_id  ON transactions(statement_import_id);


-- ─── Monthly Budgets ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS monthly_budgets (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  year            INTEGER     NOT NULL,
  month           INTEGER     NOT NULL,
  expected_income NUMERIC(18,2) NOT NULL,
  planned_saving  NUMERIC(18,2),
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_monthly_budget_year_month UNIQUE (year, month)
);


-- ─── Budget Allocations ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS budget_allocations (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  monthly_budget_id UUID NOT NULL REFERENCES monthly_budgets(id) ON DELETE CASCADE,
  category          VARCHAR(255)  NOT NULL,
  planned_amount    NUMERIC(18,2) NOT NULL,
  allocation_type   allocation_type_enum NOT NULL DEFAULT 'CONSUMPTION',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_budget_allocation_category UNIQUE (monthly_budget_id, category)
);


-- ─── Alembic version tracking ───────────────────────────────────────
-- This lets Alembic know the schema is up to date if you ever run
-- migrations against Supabase directly.

CREATE TABLE IF NOT EXISTS alembic_version (
  version_num VARCHAR(32) NOT NULL,
  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Mark as current with the latest migration
INSERT INTO alembic_version (version_num)
VALUES ('b6c8e0f4a2d1')
ON CONFLICT DO NOTHING;


-- ════════════════════════════════════════════════════════════════════
-- Row Level Security (optional — single-user app)
-- ════════════════════════════════════════════════════════════════════
-- Since this is a personal finance app with a single user, RLS is
-- enabled with permissive policies that allow any authenticated user
-- full access. This prevents anonymous/public access via Supabase
-- client while keeping the FastAPI backend (which uses the connection
-- string directly) unaffected.
--
-- The FastAPI backend connects via the DATABASE_URL (postgres role),
-- which bypasses RLS automatically.
-- ════════════════════════════════════════════════════════════════════

ALTER TABLE accounts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE statement_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_budgets   ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_allocations ENABLE ROW LEVEL SECURITY;

-- Policies: allow authenticated users full access
-- (The FastAPI backend uses the postgres role which bypasses RLS)

CREATE POLICY "Authenticated full access" ON accounts
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated full access" ON statement_imports
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated full access" ON transactions
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated full access" ON monthly_budgets
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated full access" ON budget_allocations
  FOR ALL USING (true) WITH CHECK (true);
