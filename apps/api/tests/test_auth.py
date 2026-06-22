"""Unit + integration tests for the auth layer (security.py + /api/auth endpoints)."""
from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app
from app.database.models import Base
from app.database.session import get_db
from app.security import (
    AuthError,
    decode_token,
    encode_token,
    hash_password,
    normalize_email,
    verify_password,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


SECRET = "test-auth-secret-do-not-use-in-prod"


# ── security.py unit tests ────────────────────────────────────────────────────

def test_normalize_email():
    assert normalize_email("  Alice@Example.COM  ") == "alice@example.com"


def test_password_hash_round_trip():
    h = hash_password("mysecret")
    assert verify_password("mysecret", h) is True


def test_wrong_password_returns_false():
    h = hash_password("correct")
    assert verify_password("wrong", h) is False


def test_malformed_hash_returns_false():
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "scrypt$bad") is False
    assert verify_password("anything", "") is False


def test_jwt_round_trip():
    payload = {"sub": "alice@example.com", "uid": 1}
    token = encode_token(payload, SECRET, ttl_minutes=60)
    decoded = decode_token(token, SECRET)
    assert decoded["sub"] == "alice@example.com"
    assert decoded["uid"] == 1
    assert "exp" in decoded and "iat" in decoded


def test_jwt_tampered_signature_rejected():
    token = encode_token({"sub": "alice"}, SECRET, ttl_minutes=60)
    parts = token.split(".")
    # Flip a character in the signature
    bad_sig = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
    bad_token = ".".join([parts[0], parts[1], bad_sig])
    with pytest.raises(AuthError):
        decode_token(bad_token, SECRET)


def test_jwt_expired_token_rejected():
    payload = {"sub": "alice", "uid": 1, "iat": int(time.time()) - 200, "exp": int(time.time()) - 100}
    import base64, json, hmac, hashlib

    def b64url(b):
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64url(json.dumps(payload).encode())
    signing = f"{header}.{body}".encode()
    sig = b64url(hmac.new(SECRET.encode(), signing, hashlib.sha256).digest())
    token = f"{header}.{body}.{sig}"

    with pytest.raises(AuthError):
        decode_token(token, SECRET)


def test_jwt_wrong_secret_rejected():
    token = encode_token({"sub": "alice"}, SECRET, ttl_minutes=60)
    with pytest.raises(AuthError):
        decode_token(token, "wrong-secret")


def test_jwt_malformed_rejected():
    with pytest.raises(AuthError):
        decode_token("not.a.valid.token.here", SECRET)
    with pytest.raises(AuthError):
        decode_token("onlytwoparts.here", SECRET)


# ── Auth endpoint integration tests ──────────────────────────────────────────

def test_register_success(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "Password123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "alice@example.com"


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={"email": "bob@example.com", "password": "Password123"})
    r = client.post("/api/auth/register", json={"email": "bob@example.com", "password": "Different1"})
    assert r.status_code == 409


def test_register_normalizes_email(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "  Carol@Example.COM  ", "password": "Password123"},
    )
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "carol@example.com"


def test_login_success(client):
    client.post("/api/auth/register", json={"email": "dave@example.com", "password": "Password123"})
    r = client.post("/api/auth/login", json={"email": "dave@example.com", "password": "Password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "eve@example.com", "password": "Password123"})
    r = client.post("/api/auth/login", json={"email": "eve@example.com", "password": "WrongPass1"})
    assert r.status_code == 401
    # Generic message — does not reveal whether email exists
    assert "Invalid" in r.json()["detail"]


def test_login_unknown_email_generic_error(client):
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Password1"})
    assert r.status_code == 401
    assert "Invalid" in r.json()["detail"]


def test_me_with_valid_token(client):
    r = client.post("/api/auth/register", json={"email": "frank@example.com", "password": "Password123"})
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "frank@example.com"


def test_me_without_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").lower() == "bearer"


def test_me_with_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer notavalidtoken"})
    assert r.status_code == 401


def test_me_with_forged_token(client):
    # Forged token signed with a different secret
    forged = encode_token({"sub": "hacker@example.com", "uid": 9999}, "wrong-secret", 60)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
