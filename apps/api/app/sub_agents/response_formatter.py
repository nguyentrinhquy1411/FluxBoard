from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FormattedResponse:
    title: str
    summary: str
    highlights: list[str]
    next_steps: list[str]


class ResponseFormatterAgent:
    """
    Shapes raw AI execution output into a stable user-facing response payload.

    The first MVP keeps this deterministic so the UI can rely on a consistent
    structure even when the planner/executor path changes underneath it later.
    """

    _ACTION_TITLES = {
        "read_board": "Board analysis",
        "task_detail": "Task details",
        "create_task": "Task created",
        "update_task": "Task updated",
        "archive_task": "Tasks archived",
        "restore_task": "Tasks restored",
        "reject_unrelated": "Out of scope",
    }

    def format(
        self,
        *,
        action: str,
        answer: str,
        rows: list[dict[str, Any]],
        affected_tasks: list[Any],
        question: str | None = None,
    ) -> FormattedResponse:
        title = self._ACTION_TITLES.get(action, "AI response")
        summary = self._summary_from_answer(answer, action)
        highlights = self._build_highlights(
            rows=rows, affected_tasks=affected_tasks, answer=answer
        )
        next_steps = self._build_next_steps(
            action=action, question=question, affected_tasks=affected_tasks
        )
        return FormattedResponse(
            title=title,
            summary=summary,
            highlights=highlights,
            next_steps=next_steps,
        )

    def _summary_from_answer(self, answer: str, action: str) -> str:
        if action == "task_detail":
            return answer
        parts = [line.strip() for line in answer.splitlines() if line.strip()]
        return parts[0] if parts else "The agent completed the request."

    def _build_highlights(
        self,
        *,
        rows: list[dict[str, Any]],
        affected_tasks: list[Any],
        answer: str,
    ) -> list[str]:
        highlights: list[str] = []

        for task in affected_tasks[:3]:
            key = getattr(task, "key", None) or f"#{getattr(task, 'id', '?')}"
            title = getattr(task, "title", "Untitled task")
            status_id = getattr(task, "status_id", None)
            priority = getattr(task, "priority", None)
            line = f"{key}: {title}"
            if priority:
                line += f" ({priority})"
            if status_id is not None:
                line += f" [status {status_id}]"
            highlights.append(line)

        if not highlights:
            for row in rows[:4]:
                pieces = []
                for key, value in row.items():
                    if value in (None, "", False):
                        continue
                    if key in {"position", "created_at", "updated_at"}:
                        continue
                    pieces.append(f"{key}: {value}")
                if pieces:
                    highlights.append(" | ".join(pieces[:3]))

        if not highlights:
            fallback_lines = [line.strip(" •-") for line in answer.splitlines() if line.strip()]
            highlights.extend(fallback_lines[1:4])

        return highlights[:4]

    def _build_next_steps(
        self,
        *,
        action: str,
        question: str | None,
        affected_tasks: list[Any],
    ) -> list[str]:
        task_key = None
        if affected_tasks:
            task_key = getattr(affected_tasks[0], "key", None)

        if action == "read_board":
            return [
                "Ask for a narrower filter by assignee, status, or priority.",
                "Open a task by key to inspect comments, labels, and due dates.",
            ]
        if action == "create_task" and task_key:
            return [
                f"Review {task_key} and add more detail if needed.",
                f"Move {task_key} into the right column when work starts.",
            ]
        if action == "update_task" and task_key:
            return [
                f"Check whether {task_key} now appears in the expected column.",
                "Ask for a fresh summary to confirm board impact.",
            ]
        if action == "archive_task":
            return [
                "Open Archived to review hidden work.",
                "Ask to restore specific tasks if anything was archived too aggressively.",
            ]
        if action == "restore_task":
            return [
                "Refresh the board and confirm the restored tasks are back in the right column.",
                "Archive completed work again once the board is clean.",
            ]
        if action == "reject_unrelated":
            return [
                "Try a question about tasks, statuses, assignees, priorities, or archived work.",
            ]

        if question:
            return [f'Continue from this result with a follow-up like: "{question}"']
        return []
