from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app
from app.database.models import Base
from app.database.session import get_db


def client_with_db() -> TestClient:
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
    return TestClient(app)


def _register(client: TestClient, email: str, password: str = "Password123") -> str:
    """Register a user and return the bearer token."""
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_board_task_lifecycle_and_ai_query() -> None:
    client = client_with_db()
    try:
        token = _register(client, "owner@example.com")

        project_response = client.post(
            "/api/projects",
            json={"name": "Platform Delivery", "key": "PLAT"},
            headers=_auth(token),
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=_auth(token)).json()
        backlog_status_id = board["columns"][0]["status"]["id"]
        done_status_id = board["columns"][-1]["status"]["id"]

        task_response = client.post(
            f"/api/projects/{project_id}/tasks",
            json={"title": "Ship real Kanban", "status_id": backlog_status_id, "priority": "high"},
            headers=_auth(token),
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]

        move_response = client.post(
            f"/api/tasks/{task_id}/move",
            json={"status_id": done_status_id},
            headers=_auth(token),
        )
        assert move_response.status_code == 200
        assert move_response.json()["status_id"] == done_status_id

        comment_response = client.post(
            f"/api/tasks/{task_id}/comments",
            json={"body": "Looks good"},
            headers=_auth(token),
        )
        assert comment_response.status_code == 201

        ai_response = client.post(
            "/api/ai/query",
            json={"project_id": project_id, "question": "Summarize tasks by status"},
            headers=_auth(token),
        )
        assert ai_response.status_code == 200
        assert ai_response.json()["action"] == "read_board"

        ai_create = client.post(
            "/api/ai/query",
            json={
                "project_id": project_id,
                "question": "Create task: Prepare launch checklist with critical priority",
            },
            headers=_auth(token),
        )
        assert ai_create.status_code == 200
        assert ai_create.json()["action"] == "create_task"
        created_task_id = ai_create.json()["affected_tasks"][0]["id"]

        ai_archive = client.post(
            "/api/ai/query",
            json={"project_id": project_id, "question": f"Archive task {created_task_id}"},
            headers=_auth(token),
        )
        assert ai_archive.status_code == 200
        assert ai_archive.json()["action"] == "archive_task"

        archived_response = client.get(
            f"/api/projects/{project_id}/archived", headers=_auth(token)
        )
        assert archived_response.status_code == 200
        archived_ids = {task["id"] for task in archived_response.json()}
        assert created_task_id in archived_ids

        restore_response = client.post(
            f"/api/tasks/{created_task_id}/restore", headers=_auth(token)
        )
        assert restore_response.status_code == 200
        assert restore_response.json()["archived"] is False

        # Archive all tasks via AI
        archive_all_response = client.post(
            "/api/ai/query",
            json={"project_id": project_id, "question": "archive all tasks in the project"},
            headers=_auth(token),
        )
        assert archive_all_response.status_code == 200
        assert archive_all_response.json()["action"] == "archive_task"

        board_after = client.get(f"/api/projects/{project_id}/board", headers=_auth(token)).json()
        for col in board_after["columns"]:
            assert len(col["tasks"]) == 0

        # Viewer trying to create a task via AI is blocked
        viewer_token = _register(client, "viewer@example.com")
        client.post(
            f"/api/projects/{project_id}/members",
            json={"email": "viewer@example.com", "role": "viewer"},
            headers=_auth(token),
        )
        ai_create_viewer = client.post(
            "/api/ai/query",
            json={
                "project_id": project_id,
                "question": "Create task: Viewer task",
            },
            headers=_auth(viewer_token),
        )
        assert ai_create_viewer.status_code == 200
        assert ai_create_viewer.json()["action"] == "reject_unrelated"
        assert "Viewers can ask" in ai_create_viewer.json()["answer"]
    finally:
        app.dependency_overrides.clear()


def test_auth_flow_and_project_isolation() -> None:
    client = client_with_db()
    try:
        # 1. No token -> projects returns SMOKE only
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["key"] == "SMOKE"
        smoke_id = projects[0]["id"]

        # 2. Register user1 and create a project
        user1_token = _register(client, "user1@example.com")
        resp = client.post(
            "/api/projects",
            json={"name": "User 1 Project", "key": "USR1"},
            headers=_auth(user1_token),
        )
        assert resp.status_code == 201
        usr1_proj_id = resp.json()["id"]

        # user1 is admin on their own project
        members_resp = client.get(
            f"/api/projects/{usr1_proj_id}/members",
            headers=_auth(user1_token),
        )
        assert members_resp.status_code == 200
        members = members_resp.json()
        assert len(members) == 1
        assert members[0]["email"] == "user1@example.com"
        assert members[0]["role"] == "admin"

        # 3. user1's project list includes SMOKE + USR1
        resp = client.get("/api/projects", headers=_auth(user1_token))
        assert resp.status_code == 200
        keys = {p["key"] for p in resp.json()}
        assert keys == {"SMOKE", "USR1"}

        # 4. user2 (not a member) cannot read usr1_proj board -> 401/403
        user2_token = _register(client, "user2@example.com")
        resp = client.get(f"/api/projects/{usr1_proj_id}/board", headers=_auth(user2_token))
        assert resp.status_code == 403

        # 5. user2 cannot create task in usr1_proj -> 403
        resp = client.post(
            f"/api/projects/{usr1_proj_id}/tasks",
            json={"title": "Hack task"},
            headers=_auth(user2_token),
        )
        assert resp.status_code == 403

        # 6. Members list of usr1_proj is NOT accessible to non-members (IDOR fix)
        resp = client.get(
            f"/api/projects/{usr1_proj_id}/members",
            headers=_auth(user2_token),
        )
        assert resp.status_code == 403

        # Anonymous cannot list members either
        resp = client.get(f"/api/projects/{usr1_proj_id}/members")
        assert resp.status_code in (401, 403)

        # 7. Add viewer to usr1_proj
        viewer_token = _register(client, "viewer1@example.com")
        resp = client.post(
            f"/api/projects/{usr1_proj_id}/members",
            json={"email": "viewer1@example.com", "role": "viewer"},
            headers=_auth(user1_token),
        )
        assert resp.status_code == 201

        # viewer can read board
        resp = client.get(f"/api/projects/{usr1_proj_id}/board", headers=_auth(viewer_token))
        assert resp.status_code == 200

        # viewer cannot create task -> 403
        resp = client.post(
            f"/api/projects/{usr1_proj_id}/tasks",
            json={"title": "Viewer task"},
            headers=_auth(viewer_token),
        )
        assert resp.status_code == 403

        # 8. SMOKE is publicly readable (no token)
        resp = client.get(f"/api/projects/{smoke_id}/board")
        assert resp.status_code == 200

        # SMOKE write without token -> 401
        smoke_board = resp.json()
        backlog_status_id = smoke_board["columns"][0]["status"]["id"]
        resp = client.post(
            f"/api/projects/{smoke_id}/tasks",
            json={"title": "Anon task", "status_id": backlog_status_id},
        )
        assert resp.status_code == 401

        # Logged-in user can write to SMOKE
        smoke_writer_token = _register(client, "smokewriter@example.com")
        resp = client.post(
            f"/api/projects/{smoke_id}/tasks",
            json={"title": "Logged-in task", "status_id": backlog_status_id},
            headers=_auth(smoke_writer_token),
        )
        assert resp.status_code == 201
        task_id = resp.json()["id"]

        done_status_id = smoke_board["columns"][-1]["status"]["id"]
        resp = client.post(
            f"/api/tasks/{task_id}/move",
            json={"status_id": done_status_id},
            headers=_auth(smoke_writer_token),
        )
        assert resp.status_code == 200

        # 9. GET /api/projects/{id} requires membership (IDOR fix)
        resp = client.get(f"/api/projects/{usr1_proj_id}")
        assert resp.status_code in (401, 403)

        resp = client.get(f"/api/projects/{usr1_proj_id}", headers=_auth(user2_token))
        assert resp.status_code == 403

        # user1 can still read their own project
        resp = client.get(f"/api/projects/{usr1_proj_id}", headers=_auth(user1_token))
        assert resp.status_code == 200
        assert resp.json()["key"] == "USR1"

    finally:
        app.dependency_overrides.clear()
