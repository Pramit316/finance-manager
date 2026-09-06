from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.gmail import GmailConnection


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"


def test_gmail_status_sync_and_disconnect_endpoints():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    db.add(GmailConnection(user_id="local-development-user", email="user@example.com", encrypted_refresh_token="refresh"))
    db.commit()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch.object(settings, "SUPABASE_URL", ""), patch.object(settings, "SUPABASE_JWKS_URL", ""), patch.object(settings, "SUPABASE_JWT_SECRET", ""):
            with patch("app.api.gmail.sync_nabil_alerts", return_value={"emails_found": 1, "new_transactions": 1, "duplicates_skipped": 0, "failed": 0, "failures": []}):
                with TestClient(app) as client:
                    status = client.get("/api/gmail/status")
                    sync = client.post("/api/gmail/sync")
                    disconnect = client.delete("/api/gmail/disconnect")

        assert status.status_code == 200
        assert status.json()["connected"] is True
        assert sync.status_code == 200
        assert sync.json()["new_transactions"] == 1
        assert disconnect.status_code == 200
        assert disconnect.json() == {"connected": False}
    finally:
        app.dependency_overrides.clear()
        db.close()
