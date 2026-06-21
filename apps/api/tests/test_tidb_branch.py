import pytest

from app.config import Settings
from app.database.connection import make_mock_executor
from app.schemas.validation import SQLOutput
from app.sub_agents.tidb_branch import SpeculativeBranchAgent


@pytest.mark.asyncio
async def test_branch_pointer_and_teardown_are_reported() -> None:
    executor = make_mock_executor()
    agent = SpeculativeBranchAgent(executor, Settings(default_git_commit_hash="abc123"))

    feedback = await agent.execute_with_feedback(SQLOutput(query="SELECT * FROM tasks"))

    assert feedback.success is True
    assert feedback.pointer.git_commit_hash == "abc123"
    assert feedback.pointer.tidb_branch_id.startswith("mock-branch-")
    assert feedback.pointer.virtual_env_id.startswith("venv-")
    assert feedback.branch_torn_down is True
    assert feedback.pointer.tidb_branch_id in executor.torn_down


@pytest.mark.asyncio
async def test_execution_feedback_retries_until_success() -> None:
    query = "SELECT * FROM tasks"
    executor = make_mock_executor(fail_first_for=[query])
    agent = SpeculativeBranchAgent(executor, Settings(max_execution_retries=2))

    feedback = await agent.execute_with_feedback(SQLOutput(query=query))

    assert feedback.success is True
    assert len(feedback.attempts) == 2
    assert feedback.attempts[0].success is False
    assert feedback.attempts[1].success is True
