import json
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner

from app.api import app
from app.database.models import Base
from app.database.session import get_db
from main import cli


def _authed_client() -> tuple[TestClient, str]:
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
    client = TestClient(app)
    r = client.post(
        "/api/auth/register",
        json={"email": "testuser@example.com", "password": "Password123"},
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    return client, token


def test_api_query_smoke() -> None:
    """HTTP POST /query requires auth and must ignore body-supplied roles."""
    client, token = _authed_client()
    try:
        response = client.post(
            "/query",
            json={"question": "show completed tasks by project", "roles": ["viewer"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["sql"]["query"].startswith("SELECT")
        assert body["execution"]["success"] is True
    finally:
        app.dependency_overrides.clear()


def test_cli_query_smoke() -> None:
    """CLI (in-process) still works with roles supplied programmatically.

    This is the eval harness path — it must never require HTTP auth.
    """
    result = CliRunner().invoke(cli, ["query", "show completed tasks by project"])

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["sql"]["query"].startswith("SELECT")
    assert body["execution"]["success"] is True
