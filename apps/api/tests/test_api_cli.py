import json

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app.api import app
from main import cli


def test_api_query_smoke() -> None:
    response = TestClient(app).post(
        "/query",
        json={"question": "show completed tasks by project", "roles": ["viewer"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sql"]["query"].startswith("SELECT")
    assert body["execution"]["success"] is True


def test_cli_query_smoke() -> None:
    result = CliRunner().invoke(cli, ["query", "show completed tasks by project"])

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["sql"]["query"].startswith("SELECT")
    assert body["execution"]["success"] is True
