---

name: context-maintenance
description: Maintain durable project memory and technical context whenever verified project behaviour, architecture, source formats or business rules change.
--------------------------------------------------------------------------------------------------------------------------------------------------------------

# Context Maintenance

Use this skill whenever substantial project knowledge changes.

The objective is to ensure important information does not exist only in conversation history.

---

# Persistent Context

The primary durable project-memory file is:

`docs/PROJECT_CONTEXT.md`

Also maintain relevant implementation documentation such as:

* `docs/ARCHITECTURE.md`
* `docs/DATA_MODEL.md`
* `docs/INGESTION.md`

Do not rely solely on chat history.

---

# Before Substantial Work

Read:

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. relevant project skills
4. relevant implementation documentation
5. source fixtures when necessary

Do not repeat source investigation when verified information already exists unless:

* a test fails
* the current file contradicts documented behaviour
* the source layout appears to have changed

---

# Automatic Context Update Rule

After implementing or investigating a meaningful change:

1. implement the change
2. run relevant tests
3. establish verified behaviour
4. determine whether stable project knowledge changed
5. update the appropriate context/documentation file
6. continue development

Do not wait for explicit user approval for ordinary context/documentation maintenance.

---

# Update PROJECT_CONTEXT.md When

Examples include:

* a new financial institution is supported
* a source statement format changes
* a new verified parsing edge case is discovered
* transaction fingerprinting changes
* deduplication behaviour changes
* reconciliation behaviour changes
* canonical transaction rules change
* internal-transfer business rules change
* technology decisions materially change
* development phases change
* a major security principle changes

---

# Update ARCHITECTURE.md When

Examples:

* components are added or removed
* responsibilities move between layers
* application data flow changes
* frontend/backend architecture changes
* infrastructure changes
* a new major service is introduced

Keep architecture documentation aligned with the real implementation.

---

# Update DATA_MODEL.md When

Examples:

* database tables change
* columns change
* relationships change
* constraints change
* enum values change
* transaction uniqueness rules change
* indexes change
* canonical transaction fields change

Do not let schema documentation drift from migrations/models.

---

# Update INGESTION.md When

Examples:

* parser workflow changes
* new source parser is added
* statement detection changes
* deduplication logic changes
* validation logic changes
* reconciliation logic changes
* error-handling states change
* import status behaviour changes

---

# Source-Specific Knowledge

Verified source information should be persisted.

Examples:

## eSewa

Persist:

* file type
* workbook structure
* sheet name
* metadata location
* transaction columns
* ordering
* debit/credit semantics
* duplicate-reference behaviour
* footer/status rows
* fingerprint requirements
* known parser edge cases

## Nabil

Persist:

* PDF characteristics
* page structure
* metadata fields
* transaction columns
* geometry
* description reconstruction behaviour
* repeated headers
* opening/closing balance handling
* reconciliation behaviour
* known parser edge cases

Never store assumptions as verified source behaviour.

---

# Verification Categories

When useful, distinguish documentation statements as:

## VERIFIED

Confirmed by:

* source fixture
* automated test
* successful implementation behaviour

## CURRENT DESIGN

An implementation decision currently used by the application.

## FUTURE

Planned but not yet implemented.

Do not describe FUTURE behaviour as implemented.

---

# Source of Truth Priority

When conflicting information exists, prefer:

1. verified automated tests
2. actual source/sample files
3. current working implementation
4. `docs/PROJECT_CONTEXT.md`
5. other project documentation
6. conversation history

If documentation is outdated, update it during the same change.

---

# Do Not Persist Noise

Do not add permanent context for:

* terminal commands
* temporary debugging logs
* failed experiments that were abandoned
* speculative ideas
* incomplete thought processes
* temporary workarounds already removed
* one-off errors with no lasting significance

Context should remain useful and readable.

---

# Keep Context Concise

Durable context is not a development diary.

Prefer:

```text
Verified behaviour
Reason
Important constraint
Relevant example
```

over long chronological narratives.

Avoid duplicating large pieces of source code in context documents.

The implementation remains the source for implementation details.

---

# New Discovery Workflow

When investigation reveals a new source behaviour:

```text
DISCOVER
↓
VERIFY AGAINST SOURCE
↓
ADD TEST
↓
IMPLEMENT / FIX
↓
RUN TEST
↓
UPDATE PROJECT_CONTEXT
↓
CONTINUE
```

Example:

A future eSewa export introduces a new footer row.

Do not merely change the parser.

Also:

1. add a regression test
2. update source-specific context
3. document that the row is non-transaction metadata

---

# Implementation Change Workflow

For a significant feature:

```text
READ CONTEXT
↓
IMPLEMENT
↓
TEST
↓
VERIFY
↓
UPDATE CONTEXT IF NEEDED
↓
CONTINUE
```

Do not stop development merely to announce that documentation needs updating.

Update it automatically.

---

# Agent Behaviour

When operating in Build mode:

Prefer action over repeated planning.

Do not repeatedly:

* rediscover established source structures
* rewrite the same architecture proposal
* stop after each successful milestone
* ask the user to approve ordinary implementation choices

Persistent context exists specifically to prevent repeated investigation.

Use it.

---

# Completion Reporting

After a meaningful task, briefly report:

* implementation completed
* tests executed
* pass/fail status
* context/documentation files updated

Do not produce a lengthy context-maintenance report unless requested.
