"""Export data from local PostgreSQL and import into Supabase.

This script:
1. Exports all data from the local PostgreSQL database to JSON files
2. Imports that data into Supabase PostgreSQL, preserving UUIDs
3. Handles duplicate protection during import
4. Does NOT delete local data

Usage:
  # Step 1: Export from local DB
  python scripts/migrate_data.py export

  # Step 2: Import into Supabase (set DATABASE_URL to Supabase first)
  DATABASE_URL="postgresql://postgres.[REF]:[PASS]@..." python scripts/migrate_data.py import
"""

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

# Add parent directory to path for app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

EXPORT_DIR = Path(__file__).parent / "data_export"

# Tables in dependency order (parents before children)
TABLES = [
    "accounts",
    "statement_imports",
    "transactions",
    "monthly_budgets",
    "budget_allocations",
]


class JSONEncoder(json.JSONEncoder):
    """Handle UUID, Decimal, datetime, date serialisation."""
    def default(self, o):
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


def get_engine(url: str | None = None):
    db_url = url or os.environ.get("DATABASE_URL", "postgresql://postgres:12345@localhost:5432/finance_tracker")
    return create_engine(db_url, echo=False)


def export_data():
    """Export all tables from local PostgreSQL to JSON files."""
    engine = get_engine()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    with engine.connect() as conn:
        for table in TABLES:
            result = conn.execute(text(f"SELECT * FROM {table}"))
            rows = [dict(row._mapping) for row in result]
            filepath = EXPORT_DIR / f"{table}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(rows, f, cls=JSONEncoder, indent=2, ensure_ascii=False)
            print(f"  Exported {len(rows):>5} rows from {table} → {filepath.name}")

    print(f"\nExport complete. Files saved to: {EXPORT_DIR}")


def import_data():
    """Import JSON data into target PostgreSQL (Supabase)."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: Set DATABASE_URL environment variable to your Supabase connection string.")
        print('  Example: DATABASE_URL="postgresql://postgres.[REF]:[PASS]@..." python scripts/migrate_data.py import')
        sys.exit(1)

    if "localhost" in db_url or "127.0.0.1" in db_url:
        confirm = input(
            "WARNING: DATABASE_URL points to localhost. Are you sure this is your Supabase URL? (yes/no): "
        )
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    engine = get_engine(db_url)

    with engine.connect() as conn:
        for table in TABLES:
            filepath = EXPORT_DIR / f"{table}.json"
            if not filepath.exists():
                print(f"  SKIP {table} — no export file found")
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                rows = json.load(f)

            if not rows:
                print(f"  SKIP {table} — empty")
                continue

            # Check how many already exist
            existing = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

            inserted = 0
            skipped = 0

            for row in rows:
                # Check if row already exists by primary key
                pk_check = conn.execute(
                    text(f"SELECT 1 FROM {table} WHERE id = :id"),
                    {"id": row["id"]}
                ).fetchone()

                if pk_check:
                    skipped += 1
                    continue

                # Build INSERT
                columns = list(row.keys())
                placeholders = ", ".join(f":{c}" for c in columns)
                col_names = ", ".join(columns)

                try:
                    conn.execute(
                        text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"),
                        row
                    )
                    inserted += 1
                except Exception as e:
                    print(f"  ERROR inserting into {table}: {e}")
                    skipped += 1

            conn.commit()
            print(f"  {table}: {inserted} inserted, {skipped} skipped (already existed), {existing} pre-existing")

    print("\nImport complete. Local database was NOT modified.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("export", "import"):
        print("Usage:")
        print("  python scripts/migrate_data.py export    — Export local data to JSON")
        print("  python scripts/migrate_data.py import    — Import JSON into Supabase")
        sys.exit(1)

    action = sys.argv[1]
    if action == "export":
        print("Exporting data from local PostgreSQL...")
        export_data()
    elif action == "import":
        print("Importing data into target PostgreSQL...")
        import_data()


if __name__ == "__main__":
    main()
