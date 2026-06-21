from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from sqlalchemy import text

from app.config import Settings
from app.database.session import session_scope
from app.schemas.validation import BranchSessionPointer, ExecutionAttempt, SQLOutput


class BranchExecutor(Protocol):
    async def create_branch(self, git_commit_hash: str) -> BranchSessionPointer: ...

    async def execute(self, pointer: BranchSessionPointer, sql: SQLOutput) -> ExecutionAttempt: ...

    async def teardown_branch(self, pointer: BranchSessionPointer) -> None: ...


@dataclass
class MockBranchExecutor:
    fail_first_for: set[str] = field(default_factory=set)
    torn_down: list[str] = field(default_factory=list)
    created: list[BranchSessionPointer] = field(default_factory=list)
    _attempts_by_query: dict[str, int] = field(default_factory=dict)

    async def create_branch(self, git_commit_hash: str) -> BranchSessionPointer:
        pointer = BranchSessionPointer(
            git_commit_hash=git_commit_hash,
            tidb_branch_id=f"mock-branch-{uuid4().hex[:8]}",
            virtual_env_id=f"venv-{uuid4().hex[:8]}",
        )
        self.created.append(pointer)
        return pointer

    async def execute(self, pointer: BranchSessionPointer, sql: SQLOutput) -> ExecutionAttempt:
        next_attempt = self._attempts_by_query.get(sql.query, 0) + 1
        self._attempts_by_query[sql.query] = next_attempt
        should_fail = sql.query in self.fail_first_for and next_attempt == 1
        if should_fail:
            return ExecutionAttempt(
                attempt=next_attempt,
                query=sql.query,
                success=False,
                error="mock syntax feedback: unknown column in sandbox branch",
            )
        return ExecutionAttempt(
            attempt=next_attempt,
            query=sql.query,
            success=True,
            rows=[
                {
                    "branch_id": pointer.tidb_branch_id,
                    "result": "ok",
                    "referenced_tables": ",".join(sql.referenced_tables),
                }
            ],
        )

    async def teardown_branch(self, pointer: BranchSessionPointer) -> None:
        self.torn_down.append(pointer.tidb_branch_id)


@asynccontextmanager
async def read_replica_session(settings: Settings) -> AsyncIterator[str]:
    yield settings.tidb_read_replica_dsn


def make_mock_executor(fail_first_for: Sequence[str] | None = None) -> MockBranchExecutor:
    return MockBranchExecutor(fail_first_for=set(fail_first_for or []))


class TiDBReadOnlyExecutor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = None
        if settings.tidb_read_replica_dsn and settings.tidb_read_replica_dsn.startswith("mysql"):
            from sqlalchemy import create_engine

            from app.database.session import engine_kwargs

            url = settings.tidb_read_replica_dsn.replace("mysql://", "mysql+pymysql://", 1)
            self.engine = create_engine(url, **engine_kwargs(settings))

    async def create_branch(self, git_commit_hash: str) -> BranchSessionPointer:
        return BranchSessionPointer(
            git_commit_hash=git_commit_hash,
            tidb_branch_id="tidb-live-readonly",
            virtual_env_id=f"sqlalchemy-session-{uuid4().hex[:8]}",
        )

    async def execute(self, pointer: BranchSessionPointer, sql: SQLOutput) -> ExecutionAttempt:
        del pointer
        params = {parameter.name: parameter.value for parameter in sql.parameters}
        try:
            if self.engine:
                from sqlalchemy.orm import Session

                with Session(self.engine) as session:
                    rows = [dict(row._mapping) for row in session.execute(text(sql.query), params)]
            else:
                with session_scope() as session:
                    rows = [dict(row._mapping) for row in session.execute(text(sql.query), params)]
            return ExecutionAttempt(attempt=1, query=sql.query, success=True, rows=rows)
        except Exception as exc:
            return ExecutionAttempt(attempt=1, query=sql.query, success=False, error=str(exc))

    async def teardown_branch(self, pointer: BranchSessionPointer) -> None:
        del pointer


def make_branch_executor(settings: Settings) -> BranchExecutor:
    if settings.mock_mode or not settings.tidb_url:
        return make_mock_executor()
    return TiDBReadOnlyExecutor(settings)
