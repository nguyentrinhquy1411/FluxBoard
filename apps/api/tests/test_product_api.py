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
