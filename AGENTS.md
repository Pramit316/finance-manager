# Personal Finance AI — Agent Guide

## Project Purpose

Build a personal finance application that allows the user to upload financial statements from multiple financial institutions and consolidate them into one trustworthy financial dataset.

Initial supported sources:

* eSewa XLS statement exports
* Nabil Bank PDF statements

The application must eventually support:

1. Statement ingestion from different financial institutions.
2. Source-specific parsing.
3. Canonical transaction normalisation.
4. Duplicate-safe imports.
5. Raw financial data preservation.
6. Statement validation and reconciliation.
7. Transaction classification.
8. Internal-transfer detection.
9. Spending and income analysis.
10. Savings and cash-flow analytics.
11. Account and net-worth tracking.
12. AI-assisted categorisation.
13. AI-powered financial insights.
14. Natural-language financial questions.

---

# Core Financial Principles

Financial correctness is more important than convenience.

Never silently:

* discard a valid transaction
* modify raw financial data
* merge uncertain transactions
* duplicate transactions
* classify uncertain data as certain

Every transformation must be explainable and auditable.

All valid transactions should be preserved before semantic classification.

The following responsibilities must remain logically separate:

* parsing
* normalisation
* validation
* reconciliation
* deduplication
* classification
* analytics
* AI interpretation

---

# Persistent Project Memory

Important project knowledge must not exist only in conversation history.

Before substantial work, always read:

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. relevant project skills
4. relevant implementation documentation
5. relevant source samples when necessary

Do not rely on conversation history as permanent project memory.

`docs/PROJECT_CONTEXT.md` is the durable source of truth for stable project decisions and verified source-file knowledge.

When stable project knowledge changes, automatically update the relevant documentation as part of the same implementation task.

Use the `context-maintenance` skill for this behaviour.

---

# Context Maintenance

After substantial implementation or investigation:

1. implement the change
2. run relevant tests
3. verify the behaviour
4. determine whether stable project knowledge changed
5. update the relevant context/documentation file
6. continue development

Do not wait for the user to explicitly request documentation updates.

Persist information such as:

* verified statement structures
* new parsing edge cases
* deduplication changes
* reconciliation rules
* schema changes
* architectural decisions
* supported financial institutions
* API contract changes
* important validation rules

Do NOT persist:

* temporary debugging output
* abandoned experiments
* speculative ideas
* temporary terminal commands
* transient errors that have already been resolved

---

# Source of Truth Priority

If information conflicts, use this order:

1. verified automated tests
2. actual source/sample files
3. current working implementation
4. `docs/PROJECT_CONTEXT.md`
5. other project documentation
6. conversation history

If documentation becomes outdated, update it.

Never document an assumption as a verified fact.

---

# Initial Architecture

## Frontend

* React
* TypeScript
* Next.js or Vite React depending on which produces the simpler maintainable solution

## Backend

* Python
* FastAPI
* SQLAlchemy
* Alembic

## Database

* PostgreSQL

## Data Processing

* Python
* Decimal for authoritative monetary calculations
* appropriate XLS/PDF parsing libraries

## AI

* OpenAI API in later phases

Do not introduce:

* Spark
* Databricks
* Kafka
* microservices
* message queues
* distributed processing

unless a demonstrated requirement appears.

The expected financial data volume is small.

---

# Data Architecture

Use three conceptual layers:

RAW
→ CLEAN
→ ENRICHED

## RAW

Preserve original financial information.

Examples:

* original filename
* source
* raw transaction description
* original transaction date/time
* original debit
* original credit
* original balance
* source reference
* original parsed payload

Raw financial values must never be overwritten by cleaned or AI-generated values.

## CLEAN

Convert source-specific records into the canonical transaction model.

Examples:

* normalised timestamp
* signed canonical amount
* standard currency
* account association
* source reference
* transaction fingerprint/hash

## ENRICHED

Add semantic information later.

Examples:

* transaction kind
* category
* subcategory
* merchant
* internal-transfer detection
* recurring-payment detection
* classification confidence
* classification reason
* AI-generated metadata

---

# Source Adapter Architecture

Each financial institution or statement format should have its own parser.

Example:

```text
parsers/
    base.py
    esewa.py
    nabil.py
```

Shared ingestion logic must operate on a canonical parsed structure.

Adding a new bank should normally require adding a source-specific parser rather than rewriting the ingestion pipeline.

---

# Current Source Rules

Detailed verified source information is stored in:

`docs/PROJECT_CONTEXT.md`

## eSewa

Initial source:

* legacy XLS statement export

Important:

* inspect the actual sample when parser behaviour needs verification
* eSewa reference codes are not guaranteed unique per financial row
* wallet loads must not automatically be classified as income
* metadata, totals and status summaries are not transactions

## Nabil Bank

Initial source:

* electronic PDF statement with embedded text

Important:

* OCR is not required for the current sample
* transaction descriptions may span multiple visual lines
* generic PDF table detection is not sufficiently reliable
* the Opening Balance row is metadata, not a transaction
* withdrawals produce negative canonical amounts
* deposits produce positive canonical amounts

---

# Monetary Rules

Authoritative financial calculations must use:

* Python `Decimal`
* database `NUMERIC` / equivalent exact decimal type

Never use binary floating-point values for authoritative financial calculations.

Canonical signed amount:

* money entering an account → positive
* money leaving an account → negative

Preserve source debit and credit values where available.

---

# Transaction Deduplication

Imports must be idempotent.

Uploading the same statement repeatedly must not create additional copies of existing transactions.

Uploading overlapping statements must also not create duplicate transactions.

Use:

1. reliable source identifiers where appropriate
2. source-specific stable information
3. deterministic transaction fingerprints

Never rely solely on:

`date + amount + description`

because legitimate identical transactions may exist.

Deduplication rules may differ by source.

If duplicate status is uncertain:

* preserve the transaction
* or flag it for review

Do not silently delete a potentially legitimate transaction.

---

# Statement Reconciliation

Where opening and closing balances exist, reconcile:

```text
calculated closing balance
=
opening balance
+ deposits
- withdrawals
```

Compare against the statement-provided closing balance.

Where running balances exist, validate transaction-to-transaction balance continuity where practical.

If reconciliation fails materially:

* record the difference
* flag the import
* expose the issue to the user
* do not silently mark the statement valid

---

# Transaction Classification

Classification occurs after:

1. parsing
2. normalisation
3. validation
4. reconciliation
5. deduplication
6. storage

Initial transaction kinds may include:

* EXPENSE
* INCOME
* INTERNAL_TRANSFER
* REFUND
* BANK_FEE
* INTEREST
* TAX
* UNKNOWN

Valid transactions remain stored regardless of their classification.

---

# Internal Transfers

Movement between accounts owned by the user is not income and is not an expense.

Examples:

* Nabil → eSewa
* eSewa → Nabil
* Bank A → Bank B

Both sides should remain stored.

Internal transfers should eventually be excluded from:

* expense totals
* income totals
* spending category totals

But retained for:

* account balances
* transaction history
* reconciliation
* net-worth tracking
* auditing

Matching transactions may later share a transfer-group identifier.

Do not remove transfer-looking transactions during ingestion.

---

# AI Principles

AI is for semantic interpretation, not authoritative financial calculation.

Appropriate future AI uses include:

* transaction categorisation
* merchant interpretation
* transfer classification
* financial trend explanation
* unusual spending explanation
* natural-language financial queries

Use deterministic application logic or SQL for:

* balances
* totals
* percentages
* income
* expenses
* savings rate
* category totals
* monthly summaries

AI must never modify raw transaction data.

AI classification should support:

* classification source
* classification confidence
* classification reason

User corrections override AI classifications.

---

# Development Rules

Before modifying code:

1. read persistent project context
2. understand the existing implementation
3. inspect the affected data flow
4. load relevant skills
5. inspect source samples only when necessary
6. identify assumptions
7. preserve verified business logic

After modifying code:

1. run relevant tests
2. validate edge cases
3. verify duplicate protection
4. verify reconciliation where applicable
5. verify financial totals
6. update durable context if stable knowledge changed
7. continue implementation unless a genuine blocker exists

Do not make unrelated changes.

Do not remove useful comments without reason.

Prefer simple solutions over unnecessary abstractions.

---

# Build Behaviour

When the user asks to build or continue building:

DO NOT repeatedly stop to:

* restate architecture
* propose the same design again
* re-investigate already verified source structures
* ask approval for ordinary implementation decisions

Use:

BUILD
→ TEST
→ FIX
→ CONTINUE

Only stop when:

1. information genuinely cannot be derived from the repository;
2. an unresolved financial ambiguity risks corrupting data;
3. a destructive external action requires confirmation;
4. the actual samples contradict documented assumptions.

Normal coding decisions do not require user approval.

---

# Security

Never store:

* banking passwords
* eSewa passwords
* card PINs
* CVVs

Secrets must never be committed to Git.

Use environment variables for:

* API keys
* database credentials
* authentication secrets

Uploaded personal financial statements should not be committed to source control.

AI should receive only the minimum financial information necessary.

Avoid logging:

* complete statements
* credentials
* authentication tokens
* unnecessary sensitive financial payloads

---

# Testing Principles

Every parser should have automated tests using anonymised sample statements.

Test at minimum:

* successful parsing
* date conversion
* debit/credit conversion
* monetary precision
* repeated imports
* overlapping imports
* duplicate detection
* malformed rows
* missing fields
* metadata exclusion
* statement reconciliation
* running-balance validation where supported
* multi-line descriptions
* source-specific edge cases

The same statement should be safely processable repeatedly without changing the final financial result.

---

# Current Development Priority

## Phase 1

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

## Phase 2

* transaction browsing
* account views
* basic transaction filtering

## Phase 3

* transaction classification
* internal-transfer matching
* user corrections
* merchant mappings

## Phase 4

* financial dashboard
* income/expense analytics
* savings
* cash flow
* net worth

## Phase 5

* AI-assisted categorisation
* financial insights
* anomaly explanation

## Phase 6

* conversational financial assistant

Do not implement future phases unless explicitly requested or required by the current task.

---

# Skill Usage

Detailed specialist behaviour lives in project skills.

Relevant skills include:

* `transaction-ingestion`
* `data-validation`
* `app-security`
* `finance-ai`
* `context-maintenance`

`AGENTS.md` defines project-wide behaviour.

Skills define specialist implementation behaviour.

`docs/PROJECT_CONTEXT.md` contains durable project memory and verified implementation/source knowledge.
