from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database.models import Base, Project, Status, Workspace
from app.services.ai import GroqRoutingDecision, KanbanAIService


def _create_mock_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()

    # Add workspace first
    ws = Workspace(name="Default Workspace", slug="default", created_by="local-user")
    session.add(ws)
    session.flush()

    # Add project and status so board_summary works
    proj = Project(
        workspace_id=ws.id,
        name="Test Proj",
        key="TEST",
        created_by="local-user",
        updated_by="local-user",
    )
    session.add(proj)
    session.flush()
    
    # Add project member
    from app.database.models import ProjectMember
    member = ProjectMember(project_id=proj.id, email="local-user@example.com", role="admin")
    session.add(member)
    session.flush()

    status = Status(project_id=proj.id, name="Todo", category="todo", color="blue", position=0)
    session.add(status)
    session.commit()
    return session, proj.id


def test_routing_agent_unrelated_query() -> None:
    session, project_id = _create_mock_session()
    settings = Settings(mock_mode=True, groq_api_key="fake-key", groq_model="fake-model")
    service = KanbanAIService(session, settings)

    # Mock ChatGroq.with_structured_output().invoke
    mock_decision = GroqRoutingDecision(
        is_related=False,
        rejection_message="Xin lỗi, tôi chỉ trả lời câu hỏi liên quan đến Kanban và công việc.",
    )

    with patch("langchain_groq.ChatGroq") as mock_chat_groq:
        mock_instance = MagicMock()
        mock_chat_groq.return_value = mock_instance
        mock_instance.with_structured_output.return_value.invoke.return_value = mock_decision

        # We query the service
        resp = service.answer(project_id, "Thủ đô của nước Pháp là gì?", roles=["admin"])

        assert resp.action == "reject_unrelated"
        assert resp.answer == "Xin lỗi, tôi chỉ trả lời câu hỏi liên quan đến Kanban và công việc."
        assert resp.used_model == "fake-model"
    session.close()


def test_routing_agent_related_query() -> None:
    session, project_id = _create_mock_session()
    settings = Settings(mock_mode=True, groq_api_key="fake-key", groq_model="fake-model")
    service = KanbanAIService(session, settings)

    mock_decision = GroqRoutingDecision(is_related=True, rejection_message="")

    with patch("langchain_groq.ChatGroq") as mock_chat_groq:
        mock_instance = MagicMock()
        mock_chat_groq.return_value = mock_instance
        mock_instance.with_structured_output.return_value.invoke.return_value = mock_decision

        # We query the service with a related board summary question
        resp = service.answer(project_id, "tóm tắt dự án hiện tại", roles=["admin"])

        # It should pass through the routing check and return the board summary
        assert resp.action == "read_board"
        assert "Board summary" in resp.answer
    session.close()
