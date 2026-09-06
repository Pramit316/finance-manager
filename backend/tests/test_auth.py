"""Tests for Supabase JWT authentication and protected endpoints."""

import io
import time
import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.account import Account, AccountType
from tests.conftest import SAMPLE_ESEWA, SAMPLE_NABIL


@pytest.fixture(scope="module")
def auth_test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def auth_test_db(auth_test_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(auth_test_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def ec_keypair():
    """Generate an EC P-256 keypair for testing ES256 tokens."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture
def valid_es256_token(ec_keypair):
    """Create a valid Supabase user access token signed with ES256."""
    private_key, _ = ec_keypair
    user_id = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "email": "user@example.com",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    headers = {"alg": "ES256", "kid": "test-key-id"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


@pytest.fixture
def expired_es256_token(ec_keypair):
    """Create an expired Supabase user access token signed with ES256."""
    private_key, _ = ec_keypair
    user_id = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "email": "user@example.com",
        "exp": int(time.time()) - 3600,
        "iat": int(time.time()) - 7200,
    }
    headers = {"alg": "ES256", "kid": "test-key-id"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


@pytest.fixture
def anon_es256_token(ec_keypair):
    """Create an anon token (role=anon, no sub) to verify anon key rejection."""
    private_key, _ = ec_keypair
    payload = {
        "iss": "supabase",
        "role": "anon",
        "aud": "anon",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    headers = {"alg": "ES256", "kid": "test-key-id"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


@pytest.fixture
def valid_hs256_token():
    """Create a valid Supabase user access token signed with HS256."""
    user_id = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "email": "hs256user@example.com",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, "test-secret-key-12345", algorithm="HS256")


# ─── PUBLIC ENDPOINT TESTS ───────────────────────────────────────────────────

def test_health_endpoint_is_public(client):
    """Verify that /health is accessible without any Authorization header."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# ─── PROTECTED ENDPOINT TESTS ────────────────────────────────────────────────

def test_protected_endpoint_missing_token(client):
    """Protected API routes must return 401 when no token is provided."""
    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"):
        res = client.get("/api/accounts/")
        assert res.status_code == 401
        assert res.json()["detail"] == "Authentication required"


def test_protected_endpoint_malformed_token(client):
    """Protected API routes must return 401 when a malformed token is provided."""
    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"):
        headers = {"Authorization": "Bearer not-a-valid-jwt-token"}
        res = client.get("/api/accounts/", headers=headers)
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid token"


def test_protected_endpoint_expired_token(client, expired_es256_token, ec_keypair):
    """Protected API routes must return 401 'Token expired' when token has expired."""
    _, public_key = ec_keypair
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"), \
         patch("app.auth.get_jwks_client", return_value=mock_jwks_client):
        headers = {"Authorization": f"Bearer {expired_es256_token}"}
        res = client.get("/api/accounts/", headers=headers)
        assert res.status_code == 401
        assert res.json()["detail"] == "Token expired"


def test_protected_endpoint_rejects_anon_key(client, anon_es256_token, ec_keypair):
    """Protected API routes must reject anon keys with 401 'Invalid token'."""
    _, public_key = ec_keypair
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"), \
         patch("app.auth.get_jwks_client", return_value=mock_jwks_client):
        headers = {"Authorization": f"Bearer {anon_es256_token}"}
        res = client.get("/api/accounts/", headers=headers)
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid token"


def test_protected_endpoint_valid_es256_jwt(client, valid_es256_token, ec_keypair):
    """Protected API routes must succeed when a valid ES256 user access token is provided."""
    _, public_key = ec_keypair
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"), \
         patch("app.auth.get_jwks_client", return_value=mock_jwks_client):
        headers = {"Authorization": f"Bearer {valid_es256_token}"}
        res = client.get("/api/accounts/", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


def test_protected_endpoint_valid_hs256_fallback(client, valid_hs256_token):
    """Protected API routes must succeed when a valid HS256 token is verified against SUPABASE_JWT_SECRET."""
    with patch.object(settings, "SUPABASE_JWT_SECRET", "test-secret-key-12345"), \
         patch.object(settings, "SUPABASE_JWKS_URL", ""):
        headers = {"Authorization": f"Bearer {valid_hs256_token}"}
        res = client.get("/api/accounts/", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


# ─── STATEMENT UPLOAD ENDPOINT TESTS ────────────────────────────────────────

def test_upload_endpoint_requires_auth(client):
    """POST /api/imports/upload must return 401 when no token is provided."""
    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"):
        with open(SAMPLE_NABIL, "rb") as f:
            pdf_bytes = f.read()

        files = {"file": ("sample_nabil.pdf", pdf_bytes, "application/pdf")}
        data = {"source": "NABIL"}
        res = client.post("/api/imports/upload", files=files, data=data)
        assert res.status_code == 401
        assert res.json()["detail"] == "Authentication required"


def test_upload_endpoint_authenticated_nabil_pdf(client, auth_test_db, valid_es256_token, ec_keypair):
    """POST /api/imports/upload succeeds with valid ES256 Bearer token importing Nabil PDF."""
    _, public_key = ec_keypair
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    # Create account for Nabil
    acc = Account(name="Nabil Main Account", institution="NABIL", account_type=AccountType.BANK)
    auth_test_db.add(acc)
    auth_test_db.commit()

    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"), \
         patch("app.auth.get_jwks_client", return_value=mock_jwks_client):
        with open(SAMPLE_NABIL, "rb") as f:
            pdf_bytes = f.read()

        headers = {"Authorization": f"Bearer {valid_es256_token}"}
        files = {"file": ("sample_nabil.pdf", pdf_bytes, "application/pdf")}
        data = {"source": "NABIL", "account_id": str(acc.id)}
        res = client.post("/api/imports/upload", headers=headers, files=files, data=data)

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["source"] == "NABIL"
        assert body["status"] == "IMPORTED"
        assert body["rows_inserted"] == 24


def test_upload_endpoint_authenticated_esewa_xls(client, auth_test_db, valid_es256_token, ec_keypair):
    """POST /api/imports/upload succeeds with valid ES256 Bearer token importing eSewa XLS."""
    _, public_key = ec_keypair
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    # Create account for eSewa
    acc = Account(name="eSewa Wallet", institution="ESEWA", account_type=AccountType.WALLET, account_number="9861828662")
    auth_test_db.add(acc)
    auth_test_db.commit()

    with patch.object(settings, "SUPABASE_JWKS_URL", "https://example.supabase.co/auth/v1/.well-known/jwks.json"), \
         patch("app.auth.get_jwks_client", return_value=mock_jwks_client):
        with open(SAMPLE_ESEWA, "rb") as f:
            xls_bytes = f.read()

        headers = {"Authorization": f"Bearer {valid_es256_token}"}
        files = {"file": ("sample_esewa.xls", xls_bytes, "application/vnd.ms-excel")}
        data = {"source": "ESEWA", "account_id": str(acc.id)}
        res = client.post("/api/imports/upload", headers=headers, files=files, data=data)

        assert res.status_code == 200, res.text
        body = res.json()
        assert body["source"] == "ESEWA"
        assert body["status"] == "IMPORTED"
        assert body["rows_inserted"] == 41


# ─── DATABASE_URL ENCODING TESTS ────────────────────────────────────────────

def test_database_url_encodes_special_characters():
    """Verify format_database_url encodes special characters in passwords so SQLAlchemy parses correctly."""
    from app.config import format_database_url
    from sqlalchemy.engine.url import make_url

    # Password with @, #, $, !, +
    raw_pass = "my#P@ss$123+!"
    url = f"postgresql://postgres.irvnzqygeoyjgwzdlxxd:{raw_pass}@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
    formatted = format_database_url(url)

    parsed = make_url(formatted)
    assert parsed.password == raw_pass
    assert parsed.host == "aws-0-ap-southeast-1.pooler.supabase.com"
    assert parsed.port == 6543
    assert parsed.username == "postgres.irvnzqygeoyjgwzdlxxd"
    assert parsed.database == "postgres"


def test_database_url_preserves_already_encoded():
    """Verify format_database_url does not double-encode already-encoded passwords."""
    from app.config import format_database_url
    from sqlalchemy.engine.url import make_url

    raw_pass = "my#P@ss$123+!"
    import urllib.parse
    encoded_pass = urllib.parse.quote(raw_pass, safe="")
    url = f"postgresql://postgres.irvn:{encoded_pass}@localhost:5432/db"

    formatted = format_database_url(url)
    parsed = make_url(formatted)
    assert parsed.password == raw_pass
    assert parsed.host == "localhost"


def test_protected_endpoint_iss_derivation(client, ec_keypair):
    """Verify that when SUPABASE_URL is empty, auth derives the JWKS endpoint from token 'iss'."""
    private_key, public_key = ec_keypair
    user_id = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "iss": "https://irvnzqygeoyjgwzdlxxd.supabase.co/auth/v1",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    headers = {"alg": "ES256", "kid": "test-key-id"}
    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch.object(settings, "SUPABASE_URL", ""), \
         patch.object(settings, "SUPABASE_JWKS_URL", ""), \
         patch.object(settings, "SUPABASE_JWT_SECRET", "dummy-secret-to-enable-auth"), \
         patch("app.auth.get_jwks_client", return_value=mock_jwks_client):
        res = client.get("/api/accounts/", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200


def test_database_url_converts_direct_supabase_to_pooler():
    """Verify that direct IPv6-only Supabase URLs are translated to IPv4 connection poolers."""
    from app.config import format_database_url
    from sqlalchemy.engine.url import make_url

    raw_url = "postgresql://postgres:mysecretpass@db.irvnzqygeoyjgwzdlxxd.supabase.co:5432/postgres"
    formatted = format_database_url(raw_url)
    parsed = make_url(formatted)

    assert parsed.host == "aws-0-ap-northeast-1.pooler.supabase.com"
    assert parsed.port == 6543
    assert parsed.username == "postgres.irvnzqygeoyjgwzdlxxd"
    assert parsed.password == "mysecretpass"
    assert "sslmode=require" in formatted
