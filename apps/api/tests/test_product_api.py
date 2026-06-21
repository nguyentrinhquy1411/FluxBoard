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


def test_board_task_lifecycle_and_ai_query() -> None:
    client = client_with_db()
    try:
        project_response = client.post(
            "/api/projects",
            json={"name": "Platform Delivery", "key": "PLAT"},
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        board = client.get(f"/api/projects/{project_id}/board").json()
        backlog_status_id = board["columns"][0]["status"]["id"]
        done_status_id = board["columns"][-1]["status"]["id"]

        task_response = client.post(
            f"/api/projects/{project_id}/tasks",
            json={"title": "Ship real Kanban", "status_id": backlog_status_id, "priority": "high"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]

        move_response = client.post(
            f"/api/tasks/{task_id}/move",
            json={"status_id": done_status_id},
        )
        assert move_response.status_code == 200
        assert move_response.json()["status_id"] == done_status_id

        comment_response = client.post(
            f"/api/tasks/{task_id}/comments",
            json={"body": "Looks good"},
        )
        assert comment_response.status_code == 201

        ai_response = client.post(
            "/api/ai/query",
            json={"project_id": project_id, "question": "Summarize tasks by status"},
        )
        assert ai_response.status_code == 200
        assert ai_response.json()["action"] == "read_board"

        ai_create = client.post(
            "/api/ai/query",
            json={
                "project_id": project_id,
                "question": "Create task: Prepare launch checklist with critical priority",
            },
        )
        assert ai_create.status_code == 200
        assert ai_create.json()["action"] == "create_task"
        created_task_id = ai_create.json()["affected_tasks"][0]["id"]

        ai_archive = client.post(
            "/api/ai/query",
            json={"project_id": project_id, "question": f"Archive task {created_task_id}"},
        )
        assert ai_archive.status_code == 200
        assert ai_archive.json()["action"] == "archive_task"

        archived_response = client.get(f"/api/projects/{project_id}/archived")
        assert archived_response.status_code == 200
        archived_ids = {task["id"] for task in archived_response.json()}
        assert created_task_id in archived_ids

        restore_response = client.post(f"/api/tasks/{created_task_id}/restore")
        assert restore_response.status_code == 200
        assert restore_response.json()["archived"] is False

        # Test: Archive all tasks in the project via Text-to-SQL
        archive_all_response = client.post(
            "/api/ai/query",
            json={"project_id": project_id, "question": "archive all tasks in the project"},
        )
        assert archive_all_response.status_code == 200
        assert archive_all_response.json()["action"] == "archive_task"

        # Verify that all active tasks are indeed archived
        board_after = client.get(f"/api/projects/{project_id}/board").json()
        for col in board_after["columns"]:
            assert len(col["tasks"]) == 0

        # Test: Viewer trying to create a task via AI is blocked
        client.post(
            f"/api/projects/{project_id}/members",
            json={"email": "viewer@example.com", "role": "viewer"},
        )
        ai_create_viewer = client.post(
            "/api/ai/query",
            json={
                "project_id": project_id,
                "question": "Create task: Viewer task",
                "user_email": "viewer@example.com",
            },
        )
        assert ai_create_viewer.status_code == 200
        assert ai_create_viewer.json()["action"] == "reject_unrelated"
        assert "Viewers can ask" in ai_create_viewer.json()["answer"]
    finally:
        app.dependency_overrides.clear()


def test_auth_flow_and_project_isolation() -> None:
    client = client_with_db()
    try:
        # 1. Get projects without header/query -> only SMOKE project is returned
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["key"] == "SMOKE"
        smoke_id = projects[0]["id"]

        # 2. Create project as user1@example.com
        resp = client.post(
            "/api/projects",
            json={"name": "User 1 Project", "key": "USR1"},
            headers={"X-User-Email": "user1@example.com"},
        )
        assert resp.status_code == 201
        usr1_proj = resp.json()
        usr1_proj_id = usr1_proj["id"]

        # Verify usr1 is indeed a member (admin)
        members_resp = client.get(
            f"/api/projects/{usr1_proj_id}/members",
            headers={"X-User-Email": "user1@example.com"},
        )
        assert members_resp.status_code == 200
        members = members_resp.json()
        assert len(members) == 1
        assert members[0]["email"] == "user1@example.com"
        assert members[0]["role"] == "admin"

        # 3. Get projects as user1@example.com -> both SMOKE and USR1 projects returned
        resp = client.get("/api/projects", headers={"X-User-Email": "user1@example.com"})
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) == 2
        keys = {p["key"] for p in projects}
        assert keys == {"SMOKE", "USR1"}

        # Get projects as user2@example.com -> only SMOKE is returned
        resp = client.get("/api/projects", headers={"X-User-Email": "user2@example.com"})
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["key"] == "SMOKE"

        # 4. user2@example.com tries to read usr1_proj board -> 403 Forbidden
        resp = client.get(
            f"/api/projects/{usr1_proj_id}/board",
            headers={"X-User-Email": "user2@example.com"},
        )
        assert resp.status_code == 403

        # 5. user2@example.com tries to create task in usr1_proj -> 403 Forbidden
        resp = client.post(
            f"/api/projects/{usr1_proj_id}/tasks",
            json={"title": "Hack task"},
            headers={"X-User-Email": "user2@example.com"},
        )
        assert resp.status_code == 403

        # 6. Add viewer1@example.com as viewer to usr1_proj
        resp = client.post(
            f"/api/projects/{usr1_proj_id}/members",
            json={"email": "viewer1@example.com", "role": "viewer"},
            headers={"X-User-Email": "user1@example.com"},
        )
        assert resp.status_code == 201

        # viewer1@example.com can read board
        resp = client.get(
            f"/api/projects/{usr1_proj_id}/board",
            headers={"X-User-Email": "viewer1@example.com"},
        )
        assert resp.status_code == 200

        # viewer1@example.com cannot create task -> 403 Forbidden
        resp = client.post(
            f"/api/projects/{usr1_proj_id}/tasks",
            json={"title": "Viewer task"},
            headers={"X-User-Email": "viewer1@example.com"},
        )
        assert resp.status_code == 403

        # 7. Smoke project allows anyone (even guest@example.com) to read and write
        resp = client.get(
            f"/api/projects/{smoke_id}/board",
            headers={"X-User-Email": "guest@example.com"},
        )
        assert resp.status_code == 200
        smoke_board = resp.json()
        backlog_status_id = smoke_board["columns"][0]["status"]["id"]

        # guest can create task on SMOKE project
        resp = client.post(
            f"/api/projects/{smoke_id}/tasks",
            json={"title": "Guest task", "status_id": backlog_status_id},
            headers={"X-User-Email": "guest@example.com"},
        )
        assert resp.status_code == 201
        task_id = resp.json()["id"]

        # guest can move task on SMOKE project
        done_status_id = smoke_board["columns"][-1]["status"]["id"]
        resp = client.post(
            f"/api/tasks/{task_id}/move",
            json={"status_id": done_status_id},
            headers={"X-User-Email": "guest@example.com"},
        )
        assert resp.status_code == 200

        # 8. Test public metadata endpoints (GET /api/projects/{id} and members list)
        resp = client.get(
            f"/api/projects/{usr1_proj_id}",
            headers={"X-User-Email": "guest@example.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["key"] == "USR1"

        resp = client.get(
            f"/api/projects/{usr1_proj_id}/members",
            headers={"X-User-Email": "guest@example.com"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2  # user1@example.com + viewer1@example.com

    finally:
        app.dependency_overrides.clear()

