import sys
from sqlalchemy import create_engine, MetaData, text
from app.config import settings

# Get database URL from settings
db_url = settings.DATABASE_URL
engine = create_engine(db_url)
metadata = MetaData()
metadata.reflect(bind=engine)

print("Current tables:", list(metadata.tables.keys()))
print("Dropping all tables...")
metadata.drop_all(bind=engine)

# Also drop alembic_version table if it exists
try:
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS accounttype CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS statementsource CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS importstatus CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS reconciliationstatus CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS account_type_enum CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS statement_source_enum CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS import_status_enum CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS reconciliation_status_enum CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS transaction_kind_enum CASCADE;"))
        print("Dropped enum types.")
except Exception as e:
    print("Error dropping enums:", e)

print("Done.")
