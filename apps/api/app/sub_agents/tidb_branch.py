from __future__ import annotations

from app.config import Settings
from app.database.connection import BranchExecutor
from app.schemas.validation import ExecutionFeedback, SQLOutput


class SpeculativeBranchAgent:
    def __init__(self, executor: BranchExecutor, settings: Settings) -> None:
        self.executor = executor
        self.settings = settings

    async def execute_with_feedback(self, sql: SQLOutput) -> ExecutionFeedback:
        pointer = await self.executor.create_branch(self.settings.default_git_commit_hash)
        attempts = []
        feedback: ExecutionFeedback | None = None
        try:
            for _ in range(self.settings.max_execution_retries + 1):
                attempt = await self.executor.execute(pointer, sql)
                attempts.append(attempt)
                if attempt.success:
                    feedback = ExecutionFeedback(
                        success=True,
                        pointer=pointer,
                        attempts=attempts,
                        final_rows=attempt.rows,
                        branch_torn_down=False,
                    )
                    break
            if feedback is None:
                feedback = ExecutionFeedback(
                    success=False,
                    pointer=pointer,
                    attempts=attempts,
                    final_error=attempts[-1].error if attempts else "execution did not run",
                    branch_torn_down=False,
                )
            return feedback
        finally:
            await self.executor.teardown_branch(pointer)
            if feedback is not None:
                feedback.branch_torn_down = True
