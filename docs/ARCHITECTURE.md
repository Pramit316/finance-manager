# Architecture

FastAPI routes use SQLAlchemy models and deterministic services. Imported
statements continue through the existing parser, validation, reconciliation,
deduplication, and classification flow.

Manual entry uses the same transaction model and analytics services, with a
separate CRUD route that only permits records marked manual. Monthly budget
CRUD is exposed under `/api/budgets`; planned-vs-actual analytics are exposed
at `/api/analytics/budget?year=YYYY&month=MM`.

The React frontend provides Transactions manual entry and deletion
confirmation, plus a Monthly Plan page. Arithmetic remains in the backend;
the frontend renders API results.