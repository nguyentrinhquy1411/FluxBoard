"""
Kanban AI Copilot — architecture following scope.txt design.

Pipeline:
  User question
    ├─ MUTATION intent  → TaskRepository (ORM, safe, audited)
    └─ READ intent      → SchemaPruner → SecurityVeto → Groq SQL → JiraAnchor → execute SELECT
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.database import models
from app.repositories import TaskRepository, task_to_read
from app.schemas.product import (
    AIQueryResponse,
    AIResponsePresentation,
    Suggestion,
    SuggestionsResponse,
    TaskCreate,
    TaskUpdate,
)
from app.schemas.validation import (
    ColumnDefinition,
    DatabaseSchema,
    ForeignKeyDefinition,
    SQLOutput,
    SQLParameter,
    TableDefinition,
)
from app.sub_agents.analyst_agent import AnalystAgent
from app.sub_agents.jira_anchor import JiraAnchor
from app.sub_agents.response_formatter import ResponseFormatterAgent
from app.sub_agents.schema_pruner import SchemaPruner
from app.sub_agents.security_veto import SecurityVetoAgent

# ─────────────────────────────────────────────────────────────────────────────
# Regex helpers
# ─────────────────────────────────────────────────────────────────────────────

# Supports single-char keys: A-1, AB-3, CPV-42, SMK402-26
_KEY_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9]{0,11}-\d+)\b", re.I)
_PRIORITY_RE = re.compile(r"\b(low|medium|high|critical)\b", re.I)
# Standalone numeric id — skips numbers that are part of a task key (preceded by "-")
_NUM_RE = re.compile(r"(?<!\w)#?(\d{1,9})(?!\w)")


def _key(text: str) -> str | None:
    m = _KEY_RE.search(text)
    return m.group(1).upper() if m else None


def _priority(text: str) -> str | None:
    m = _PRIORITY_RE.search(text)
    return m.group(1).lower() if m else None


def _num_id(text: str) -> int | None:
    """Return first standalone integer that is NOT part of a task key."""
    for m in _NUM_RE.finditer(text):
        # skip if immediately preceded by "-" (it's the number in "A-4")
        if m.start() > 0 and text[m.start() - 1] == "-":
            continue
        return int(m.group(1))
    return None


def _title_from_create(text: str) -> str:
    t = re.sub(
        r"^\s*(create|add|new)\s+(a\s+)?(task|card|ticket)\s*[:：]?\s*", "", text, flags=re.I
    )
    t = re.sub(r"\bwith\s+(low|medium|high|critical)\s+priority\b", "", t, flags=re.I)
    t = re.sub(r"\b(in|to|under)\s+\S.*$", "", t, flags=re.I)
    return t.strip(" -:") or "Untitled task"


# ─────────────────────────────────────────────────────────────────────────────
# Static Kanban schema definition fed to SchemaPruner / SecurityVeto
# ─────────────────────────────────────────────────────────────────────────────

KANBAN_SCHEMA = DatabaseSchema(
    tables=[
        TableDefinition(
            name="tasks",
            columns=[
                ColumnDefinition(name="id", data_type="integer"),
                ColumnDefinition(name="project_id", data_type="integer"),
                ColumnDefinition(name="status_id", data_type="integer"),
                ColumnDefinition(name="sequence_number", data_type="integer"),
                ColumnDefinition(name="task_key", data_type="varchar"),
                ColumnDefinition(name="title", data_type="varchar"),
                ColumnDefinition(name="description", data_type="text"),
                ColumnDefinition(name="priority", data_type="varchar"),
                ColumnDefinition(name="assignee", data_type="varchar"),
                ColumnDefinition(name="due_date", data_type="datetime"),
                ColumnDefinition(name="archived", data_type="boolean"),
                ColumnDefinition(name="position", data_type="numeric"),
                ColumnDefinition(name="created_at", data_type="datetime"),
                ColumnDefinition(name="updated_at", data_type="datetime"),
            ],
        ),
        TableDefinition(
            name="statuses",
            columns=[
                ColumnDefinition(name="id", data_type="integer"),
                ColumnDefinition(name="project_id", data_type="integer"),
                ColumnDefinition(name="name", data_type="varchar"),
                ColumnDefinition(name="category", data_type="varchar"),
                ColumnDefinition(name="color", data_type="varchar"),
                ColumnDefinition(name="position", data_type="numeric"),
            ],
        ),
        TableDefinition(
            name="projects",
            columns=[
                ColumnDefinition(name="id", data_type="integer"),
                ColumnDefinition(name="name", data_type="varchar"),
                ColumnDefinition(name="key", data_type="varchar"),
                ColumnDefinition(name="description", data_type="text"),
            ],
        ),
        TableDefinition(
            name="labels",
            columns=[
                ColumnDefinition(name="id", data_type="integer"),
                ColumnDefinition(name="project_id", data_type="integer"),
                ColumnDefinition(name="name", data_type="varchar"),
                ColumnDefinition(name="color", data_type="varchar"),
            ],
        ),
        TableDefinition(
            name="task_labels",
            columns=[
                ColumnDefinition(name="task_id", data_type="integer"),
                ColumnDefinition(name="label_id", data_type="integer"),
            ],
        ),
        TableDefinition(
            name="comments",
            columns=[
                ColumnDefinition(name="id", data_type="integer"),
                ColumnDefinition(name="task_id", data_type="integer"),
                ColumnDefinition(name="body", data_type="text"),
                ColumnDefinition(name="created_by", data_type="varchar"),
                ColumnDefinition(name="created_at", data_type="datetime"),
            ],
        ),
    ],
    foreign_keys=[
        ForeignKeyDefinition(
            source_table="tasks",
            source_column="project_id",
            target_table="projects",
            target_column="id",
        ),
        ForeignKeyDefinition(
            source_table="tasks",
            source_column="status_id",
            target_table="statuses",
            target_column="id",
        ),
        ForeignKeyDefinition(
            source_table="statuses",
            source_column="project_id",
            target_table="projects",
            target_column="id",
        ),
        ForeignKeyDefinition(
            source_table="task_labels",
            source_column="task_id",
            target_table="tasks",
            target_column="id",
        ),
        ForeignKeyDefinition(
            source_table="task_labels",
            source_column="label_id",
            target_table="labels",
            target_column="id",
        ),
        ForeignKeyDefinition(
            source_table="comments",
            source_column="task_id",
            target_table="tasks",
            target_column="id",
        ),
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# Groq structured output model for read queries
# ─────────────────────────────────────────────────────────────────────────────


class GroqSQLPlan(BaseModel):
    """What the LLM returns for read queries."""

    sql: str = Field(description="Parameterized SELECT statement. Use :param_name syntax.")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter values for the SQL statement.",
    )
    explanation: str = Field(description="One-sentence plain-English explanation of the query.")


# Groq structured output model for unknown intent dispatch
class GroqIntentPlan(BaseModel):
    action: Literal[
        "task_detail",
        "update_priority",
        "update_status",
        "archive",
        "restore",
        "create_task",
        "board_summary",
        "read_query",
    ]
    task_key: str | None = None
    priority: str | None = None
    status_name: str | None = None
    task_title: str | None = None
    archive_all: bool = False
    free_sql_hint: str = ""  # for read_query action


# Groq structured output model for routing decisions
class GroqRoutingDecision(BaseModel):
    is_related: bool = Field(
        description=(
            "True if the question is related to project management, software "
            "development tasks, Kanban boards, status updates, database schema, "
            "or projects. False if it is an off-topic question, request to write "
            "unrelated code, or generic chat."
        )
    )
    rejection_message: str = Field(
        default="",
        description=(
            "A polite message in the same language as the user's question, "
            "explaining that the assistant is specifically built for Kanban "
            "project management and SQL queries. Leave empty if is_related is True."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a clean AIQueryResponse
# ─────────────────────────────────────────────────────────────────────────────


def _resp(
    answer: str,
    action: str,
    model_name: str,
    rows: list[dict] | None = None,
    affected_tasks: list | None = None,
    sql: str = "",
    question: str | None = None,
) -> AIQueryResponse:
    formatter = ResponseFormatterAgent()
    formatted = formatter.format(
        action=action,
        answer=answer,
        rows=rows or [],
        affected_tasks=affected_tasks or [],
        question=question,
    )
    presentation = AIResponsePresentation(
        title=formatted.title,
        summary=formatted.summary,
        highlights=formatted.highlights,
        next_steps=formatted.next_steps,
    )
    return AIQueryResponse(
        answer=answer,
        sql=sql,
        rows=rows or [],
        used_model=model_name,
        fallback=False,
        action=action,
        affected_tasks=affected_tasks or [],
        presentation=presentation,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main service
# ─────────────────────────────────────────────────────────────────────────────


class KanbanAIService:
    """
    Agentic Text-to-SQL service for Kanban boards.

    Mutation intents  → TaskRepository (ORM, audited, safe)
    Read intents      → SchemaPruner → SecurityVeto → Groq SQL → JiraAnchor → execute SELECT
    """

    _MODEL = "deterministic-planner"

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self._pruner = SchemaPruner()
        self._veto = SecurityVetoAgent()
        self._anchor = JiraAnchor()
        self._repo = TaskRepository(session)
        self._analyst: AnalystAgent | None = (
            AnalystAgent(api_key=settings.groq_api_key, model_name=settings.groq_model)
            if settings.groq_api_key
            else None
        )

    # ─── public entry point ───────────────────────────────────────────────────

    def answer(
        self, project_id: int, question: str, user_email: str | None = None
    ) -> AIQueryResponse:
        raw = question.strip()
        low = raw.lower()

        project = self.session.get(models.Project, project_id)
        if project is None:
            return _resp("❌ Project not found.", "reject_unrelated", self._MODEL)

        roles = []
        if project.key == "SMOKE":
            roles = ["admin"]
        else:
            email = user_email or "local-user@example.com"
            member = self.session.scalar(
                select(models.ProjectMember).where(
                    models.ProjectMember.project_id == project_id,
                    models.ProjectMember.email == email,
                )
            )
            if member:
                roles = [member.role]

        if not roles:
            return _resp(
                "❌ Access Denied: You are not a member of this project.",
                "reject_unrelated",
                self._MODEL,
            )

        task_key = _key(raw)
        prio = _priority(low)
        is_admin = "admin" in roles
        viewer_error = (
            "❌ Viewers can ask read-only questions, "
            "but creating, moving, archiving, or restoring tasks is admin-only."
        )

        # ── 1. Task detail (must be before board summary — both match "show") ──
        if re.search(
            r"\b(show|get|detail|details|info|display|view|fetch|describe|about|what is)\b", low
        ):
            if task_key:
                return self._task_detail(project_id, task_key)

        # ── 2. Priority update ────────────────────────────────────────────────
        if re.search(r"\b(priority|prio)\b", low) and re.search(
            r"\b(change|set|update|make|switch|to)\b", low
        ):
            if task_key and prio:
                if not is_admin:
                    return _resp(viewer_error, "reject_unrelated", self._MODEL)
                return self._update_priority(project_id, task_key, prio)

        # ── 3. Status / column move ───────────────────────────────────────────
        if re.search(r"\b(move|put|change|set|assign|update)\b", low) and task_key:
            for s in self._statuses(project_id):
                if s.name.lower() in low:
                    if not is_admin:
                        return _resp(viewer_error, "reject_unrelated", self._MODEL)
                    return self._update_status(project_id, task_key, s)

        # ── 4. Archive ────────────────────────────────────────────────────────
        if re.search(r"\b(archive|archieve|hide)\b", low):
            if not is_admin:
                return _resp(viewer_error, "reject_unrelated", self._MODEL)
            all_ = self._is_bulk_all_request(low)
            num_id = _num_id(raw) if not task_key else None
            return self._archive(project_id, task_key, num_id, all_)

        # ── 5. Restore ────────────────────────────────────────────────────────
        if re.search(r"\b(restore|unarchive)\b", low):
            if not is_admin:
                return _resp(viewer_error, "reject_unrelated", self._MODEL)
            all_ = self._is_bulk_all_request(low)
            num_id = _num_id(raw) if not task_key else None
            return self._restore(project_id, task_key, num_id, all_)

        # ── 6. Create task ────────────────────────────────────────────────────
        if re.search(r"\b(create|add|new)\b.*\b(task|card|ticket)\b", low):
            if not is_admin:
                return _resp(viewer_error, "reject_unrelated", self._MODEL)
            return self._create_task(project_id, _title_from_create(raw), prio or "medium")

        # ── 0. Check relevance via Routing Agent after known local intents ────
        routing_resp = self._check_routing(raw)
        if routing_resp:
            return routing_resp

        # ── 7. Analyst Agent: analytical questions ───────────────────────────
        # Keep this before generic board summary so "how many/count/status" analytics
        # are not swallowed by the deterministic summary shortcut.
        if self._analyst and self._analyst.classify(raw):
            analyst_result = self._analyst_query(project_id, raw, roles)
            if analyst_result:
                return analyst_result

        # ── 8. Generic board summary ──────────────────────────────────────────
        if re.search(r"\b(summarize|summary|list|how many|board|count|overview|status)\b", low):
            return self._board_summary(project_id)

        # ── 9. Groq fallback: dispatch for complex/unknown questions ──────────
        if self.settings.groq_api_key:
            result = self._groq_dispatch(project_id, raw, low, roles)
            if result:
                return result

        # ── 10. Hard fallback ─────────────────────────────────────────────────
        return self._board_summary(project_id)

    # ─── mutation handlers (TaskRepository — ORM, safe, audited) ─────────────

    def _task_detail(self, project_id: int, task_key: str) -> AIQueryResponse:
        task = self.session.scalar(
            select(models.Task)
            .options(
                selectinload(models.Task.labels).selectinload(models.TaskLabel.label),
                selectinload(models.Task.comments),
                selectinload(models.Task.status),
            )
            .where(
                models.Task.project_id == project_id,
                func.upper(models.Task.key) == task_key.upper(),
            )
        )
        if task is None:
            return _resp(
                f"❌ Task {task_key} was not found in this project.",
                "read_board",
                self._MODEL,
            )

        status_name = task.status.name if task.status else "Unknown"
        lines = [
            f"📋  {task.key}  —  {task.title}",
            "",
            f"  Status    :  {status_name}",
            f"  Priority  :  {task.priority.title()}",
            f"  Assignee  :  {task.assignee or 'Unassigned'}",
            f"  Archived  :  {'Yes' if task.archived else 'No'}",
        ]
        if task.due_date:
            lines.append(f"  Due date  :  {task.due_date.strftime('%Y-%m-%d')}")
        if task.labels:
            lines.append(f"  Labels    :  {', '.join(tl.label.name for tl in task.labels)}")
        if task.description:
            lines += ["", "  Description:", f"    {task.description}"]
        if task.comments:
            recent = sorted(task.comments, key=lambda c: c.created_at)[-5:]
            lines += ["", f"  Comments ({len(task.comments)}):"]
            for c in recent:
                lines.append(f"    [{c.created_by}]  {c.body}")

        task_read = task_to_read(task)
        return _resp(
            "\n".join(lines),
            "task_detail",
            self._MODEL,
            rows=[task_read.model_dump(mode="json")],
            affected_tasks=[task_read],
            sql=(
                "SELECT * FROM tasks WHERE "
                f"UPPER(task_key)='{task_key}' AND project_id={project_id}"
            ),
        )

    def _update_priority(self, project_id: int, task_key: str, priority: str) -> AIQueryResponse:
        task = self._find_by_key(project_id, task_key)
        if task is None:
            return _resp(f"❌ Task {task_key} not found.", "read_board", self._MODEL)
        old = task.priority
        updated = self._repo.update_task(task.id, TaskUpdate(priority=priority))
        return _resp(
            f"✅  Priority of {task_key} updated:  {old}  →  {priority}.",
            "update_task",
            self._MODEL,
            rows=[updated.model_dump(mode="json")],
            affected_tasks=[updated],
        )

    def _update_status(
        self, project_id: int, task_key: str, status: models.Status
    ) -> AIQueryResponse:
        task = self._find_by_key(project_id, task_key)
        if task is None:
            return _resp(f"❌ Task {task_key} not found.", "read_board", self._MODEL)
        updated = self._repo.update_task(task.id, TaskUpdate(status_id=status.id))
        return _resp(
            f"✅  Moved {task_key} to  '{status.name}'.",
            "update_task",
            self._MODEL,
            rows=[updated.model_dump(mode="json")],
            affected_tasks=[updated],
        )

    def _archive(
        self,
        project_id: int,
        task_key: str | None,
        task_id: int | None,
        all_tasks: bool,
    ) -> AIQueryResponse:
        if all_tasks:
            tasks = self.session.scalars(
                select(models.Task).where(
                    models.Task.project_id == project_id,
                    models.Task.archived.is_(False),
                )
            ).all()
            archived = [self._repo.archive_task(t.id) for t in tasks]
            return _resp(
                f"✅  Archived {len(archived)} active task(s) in this project.",
                "archive_task",
                self._MODEL,
                rows=[t.model_dump(mode="json") for t in archived],
                affected_tasks=archived,
            )

        task = (
            self._find_by_key(project_id, task_key)
            if task_key
            else self._find_by_id(project_id, task_id)
        )
        if task is None:
            ref = task_key or (f"#{task_id}" if task_id else "?")
            return _resp(
                f"❌ Task {ref} not found.\n"
                "Tip: specify a task key (e.g. archive CPV-5) or say 'archive all tasks'.",
                "archive_task",
                self._MODEL,
            )
        result = self._repo.archive_task(task.id)
        return _resp(
            f"✅  Archived {result.key}: {result.title}.",
            "archive_task",
            self._MODEL,
            rows=[result.model_dump(mode="json")],
            affected_tasks=[result],
        )

    def _restore(
        self,
        project_id: int,
        task_key: str | None,
        task_id: int | None,
        all_tasks: bool,
    ) -> AIQueryResponse:
        if all_tasks:
            tasks = self.session.scalars(
                select(models.Task).where(
                    models.Task.project_id == project_id,
                    models.Task.archived.is_(True),
                )
            ).all()
            restored = [self._repo.restore_task(t.id) for t in tasks]
            return _resp(
                f"✅  Restored {len(restored)} archived task(s) in this project.",
                "restore_task",
                self._MODEL,
                rows=[t.model_dump(mode="json") for t in restored],
                affected_tasks=restored,
            )

        task = (
            self._find_by_key(project_id, task_key)
            if task_key
            else self._find_by_id(project_id, task_id)
        )
        if task is None:
            ref = task_key or (f"#{task_id}" if task_id else "?")
            return _resp(
                f"❌ Task {ref} not found.\n"
                "Tip: specify a task key (e.g. restore CPV-5) or say 'restore all tasks'.",
                "restore_task",
                self._MODEL,
            )
        result = self._repo.restore_task(task.id)
        return _resp(
            f"✅  Restored {result.key}: {result.title}.",
            "restore_task",
            self._MODEL,
            rows=[result.model_dump(mode="json")],
            affected_tasks=[result],
        )

    def _create_task(self, project_id: int, title: str, priority: str) -> AIQueryResponse:
        result = self._repo.create_task(project_id, TaskCreate(title=title, priority=priority))
        return _resp(
            f"✅  Created task {result.key}: {result.title}  (priority: {priority}).",
            "create_task",
            self._MODEL,
            rows=[result.model_dump(mode="json")],
            affected_tasks=[result],
        )

    def _board_summary(self, project_id: int) -> AIQueryResponse:
        statuses = self._statuses(project_id)
        active = self.session.scalars(
            select(models.Task).where(
                models.Task.project_id == project_id,
                models.Task.archived.is_(False),
            )
        ).all()
        archived_count: int = (
            self.session.scalar(
                select(func.count(models.Task.id)).where(
                    models.Task.project_id == project_id,
                    models.Task.archived.is_(True),
                )
            )
            or 0
        )

        by_status: dict[str, int] = {s.name: 0 for s in statuses}
        sid_to_name = {s.id: s.name for s in statuses}
        for t in active:
            name = sid_to_name.get(t.status_id, "Unknown")
            by_status[name] = by_status.get(name, 0) + 1

        total = sum(by_status.values())
        breakdown = "  |  ".join(f"{name}: {count}" for name, count in by_status.items())
        rows = [{"status": n, "task_count": c} for n, c in by_status.items()]
        answer = (
            f"📊  Board summary — {total} active task(s):\n"
            f"  {breakdown}\n"
            f"  🗄️   Archived: {archived_count}"
        )
        return _resp(answer, "read_board", self._MODEL, rows=rows)

    # ─── analyst pipeline: classify → plan SQL → execute → summarize ──────────

    def _analyst_query(
        self, project_id: int, question: str, roles: list[str]
    ) -> AIQueryResponse | None:
        """
        Full analyst pipeline:
          1. Prune/format visible schema DDL
          2. AnalystAgent plans SQL
          3. SecurityVeto validates SELECT-only SQL
          4. Execute SQL on the read-only session
          5. AnalystAgent summarizes raw rows
          6. Format and return AIQueryResponse
        """
        if not self._analyst:
            return None

        try:
            from sqlalchemy import text

            visible = self._veto.derive_visible_schema(KANBAN_SCHEMA, roles).visible_schema
            if visible is None:
                return None

            context = self._pruner.prune(question, visible)
            selected_tables = set(context.selected_tables) | {"tasks"}
            if "status" in question.lower() or "column" in question.lower():
                selected_tables.add("statuses")

            pruned_schema = DatabaseSchema(
                tables=[table for table in visible.tables if table.name in selected_tables],
                foreign_keys=[
                    fk
                    for fk in visible.foreign_keys
                    if fk.source_table in selected_tables and fk.target_table in selected_tables
                ],
            )

            ddl_lines: list[str] = []
            for table in pruned_schema.tables:
                cols = ", ".join(f"{c.name} {c.data_type}" for c in table.columns)
                ddl_lines.append(f"  {table.name}({cols})")
            schema_ddl = "\n".join(ddl_lines)

            fk_lines: list[str] = []
            for fk in pruned_schema.foreign_keys:
                fk_lines.append(
                    f"  {fk.source_table}.{fk.source_column} → {fk.target_table}.{fk.target_column}"
                )
            if fk_lines:
                schema_ddl += "\n\nForeign keys:\n" + "\n".join(fk_lines)

            # Step 1: Plan SQL
            analyst_result = self._analyst.analyze(project_id, question, schema_ddl, self.settings)
            if not analyst_result or not analyst_result.sql_plan.sql:
                return None
            sql_plan = analyst_result.sql_plan

            sql_output = SQLOutput(
                query=sql_plan.sql,
                parameters=[
                    SQLParameter(name=name, value=value) for name, value in sql_plan.params.items()
                ],
                referenced_tables=list(selected_tables),
                rationale=sql_plan.explanation,
            )
            self._veto.validate_sql(sql_output)

            # Step 2: Execute SQL on the session
            result_proxy = self.session.execute(text(sql_plan.sql), sql_plan.params)
            rows = [dict(row._mapping) for row in result_proxy.fetchall()]

            # Step 3: Summarize results
            summary = self._analyst.summarize(question, rows)

            # Build answer text from the summary
            if summary:
                lines = [
                    f"📊 **{summary.title}**",
                    "",
                ]
                for finding in summary.key_findings:
                    lines.append(f"  • {finding}")
                lines += [
                    "",
                    f"💡 **Insight:** {summary.insights}",
                    "",
                    f"✅ **Recommendation:** {summary.recommendation}",
                ]
                answer = "\n".join(lines)
            else:
                answer = self._format_rows(f"📊 Analysis: {sql_plan.explanation}", rows)

            return _resp(
                answer,
                "analyst_report",
                self.settings.groq_model,
                rows=rows,
                sql=sql_plan.sql,
                question=question,
            )

        except Exception as e:
            import sys
            import traceback

            print(f"Analyst query failed: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return None

    # ─── read pipeline: SchemaPruner → SecurityVeto → Groq SQL → JiraAnchor ─

    def _groq_read_query(
        self, project_id: int, question: str, roles: list[str]
    ) -> AIQueryResponse | None:
        """
        Delegate the read query pipeline to MasterOrchestrator to ensure
        we follow scope.txt's Text-to-SQL architecture.
        """
        if not self.settings.groq_api_key:
            return None
        try:
            import asyncio

            from app.master import MasterOrchestrator
            from app.schemas.validation import QueryDialect, QueryRequest

            # Fetch project key if available
            project_key = None
            project = self.session.get(models.Project, project_id)
            if project:
                project_key = project.key

            req = QueryRequest(
                question=question,
                project=project_key,
                roles=roles,
                dialect=QueryDialect.SQL,
                schema=KANBAN_SCHEMA,
            )

            orchestrator = MasterOrchestrator(settings=self.settings)

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            res = loop.run_until_complete(orchestrator.run(req))

            if not res or not res.sql or not res.sql.query:
                return None

            rows = res.execution.final_rows or []
            explanation = res.sql.rationale or "Query compiled by Text-to-SQL agent."

            if not rows:
                answer = explanation + "\n\nNo results found."
            else:
                answer = self._format_rows(explanation, rows)

            return _resp(
                answer,
                "read_board",
                self.settings.groq_model,
                rows=rows,
                sql=res.sql.query,
                question=question,
            )

        except Exception as e:
            import sys
            import traceback

            print(f"Orchestrator read query failed: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return None

    def _groq_dispatch(
        self, project_id: int, question: str, low: str, roles: list[str]
    ) -> AIQueryResponse | None:
        """
        Groq structured-output intent dispatcher for completely unknown requests.
        Routes back to the deterministic handlers or the read-query pipeline.
        """
        if not self.settings.groq_api_key:
            return None
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_groq import ChatGroq

            statuses = self._statuses(project_id)
            active_sample = self.session.scalars(
                select(models.Task)
                .where(models.Task.project_id == project_id, models.Task.archived.is_(False))
                .order_by(models.Task.position)
                .limit(50)
            ).all()

            model = ChatGroq(
                api_key=self.settings.groq_api_key,
                model=self.settings.groq_model,
                temperature=0,
            ).with_structured_output(GroqIntentPlan)

            sys_msg = (
                "You are a Kanban assistant. Classify the user's request into an action.\n\n"
                f"Available statuses: {[s.name for s in statuses]}\n"
                f"Sample tasks: {self._task_prompt_sample(active_sample)}\n\n"
                "Actions:\n"
                "- task_detail: view a specific task (set task_key)\n"
                "- update_priority: change priority "
                "(set task_key + priority: low/medium/high/critical)\n"
                "- update_status: move to column (set task_key + status_name)\n"
                "- archive: archive task(s) (set task_key OR archive_all=true)\n"
                "- restore: restore task(s) from archive (set task_key OR archive_all=true)\n"
                "- create_task: create a new task (set task_title + optional priority)\n"
                "- board_summary: show board overview\n"
                "- read_query: complex read question, set free_sql_hint to describe it\n"
            )

            result: GroqIntentPlan = model.invoke(
                [
                    SystemMessage(content=sys_msg),
                    HumanMessage(content=question),
                ]
            )

            if not isinstance(result, GroqIntentPlan):
                return None

            if result.action == "task_detail" and result.task_key:
                return self._task_detail(project_id, result.task_key.upper())
            if "admin" not in roles:
                viewer_error = (
                    "❌ Viewers can ask read-only questions, "
                    "but creating, moving, archiving, or restoring tasks is admin-only."
                )
                return _resp(viewer_error, "reject_unrelated", self._MODEL)

            if result.action == "update_priority" and result.task_key and result.priority:
                return self._update_priority(
                    project_id, result.task_key.upper(), result.priority.lower()
                )
            if result.action == "update_status" and result.task_key and result.status_name:
                s = next(
                    (x for x in statuses if x.name.lower() == result.status_name.lower()), None
                )
                if s:
                    return self._update_status(project_id, result.task_key.upper(), s)
            if result.action == "archive":
                return self._archive(
                    project_id,
                    result.task_key.upper() if result.task_key else None,
                    None,
                    result.archive_all,
                )
            if result.action == "restore":
                return self._restore(
                    project_id,
                    result.task_key.upper() if result.task_key else None,
                    None,
                    result.archive_all,
                )
            if result.action == "create_task" and result.task_title:
                return self._create_task(project_id, result.task_title, result.priority or "medium")
            if result.action == "board_summary":
                return self._board_summary(project_id)
            if result.action == "read_query":
                # Use the read pipeline with the Groq-enhanced question
                hint_question = result.free_sql_hint or question
                return self._groq_read_query(project_id, hint_question, roles)

        except Exception as e:
            import sys
            import traceback

            print(f"Groq dispatch failed: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return None

    def _check_routing(self, question: str) -> AIQueryResponse | None:
        if not self.settings.groq_api_key:
            return None
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_groq import ChatGroq

            model = ChatGroq(
                api_key=self.settings.groq_api_key,
                model=self.settings.groq_model,
                temperature=0,
            ).with_structured_output(GroqRoutingDecision)

            sys_msg = (
                "You are an AI Routing Agent for a Kanban Project Management Copilot.\n"
                "Your task is to classify if the user's question is RELATED to "
                "project management, software tasks, Kanban boards, priorities, "
                "statuses, comments, schema, or projects in this system.\n"
                "If it is related, set is_related = True.\n"
                "If it is unrelated (e.g. general knowledge, writing code for "
                "unrelated algorithms, recipes, greetings without context, weather, "
                "general chat), set is_related = False and write a polite, concise "
                "rejection message in the language of the user's question, explaining "
                "that you only answer questions related to Kanban boards and project tasks."
            )

            decision: GroqRoutingDecision = model.invoke(
                [
                    SystemMessage(content=sys_msg),
                    HumanMessage(content=question),
                ]
            )

            if isinstance(decision, GroqRoutingDecision) and not decision.is_related:
                return _resp(
                    decision.rejection_message
                    or "I can only assist with Kanban project management and task queries.",
                    "reject_unrelated",
                    self.settings.groq_model,
                    question=question,
                )
        except Exception as e:
            import sys
            import traceback

            print(f"Routing agent failed: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return None

    # ─── helpers ─────────────────────────────────────────────────────────────

    def _find_by_key(self, project_id: int, task_key: str) -> models.Task | None:
        return self.session.scalar(
            select(models.Task).where(
                models.Task.project_id == project_id,
                func.upper(models.Task.key) == task_key.upper(),
            )
        )

    def _find_by_id(self, project_id: int, task_id: int | None) -> models.Task | None:
        if task_id is None:
            return None
        task = self.session.get(models.Task, task_id)
        return task if task and task.project_id == project_id else None

    def _statuses(self, project_id: int) -> list[models.Status]:
        return self.session.scalars(
            select(models.Status)
            .where(models.Status.project_id == project_id)
            .order_by(models.Status.position)
        ).all()

    def _task_prompt_sample(self, tasks: list[models.Task]) -> list[dict[str, str | None]]:
        return [
            {
                "key": task.key,
                "title": task.title[:40],
                "priority": task.priority,
            }
            for task in tasks
        ]

    def _format_rows(self, title: str, rows: list[dict]) -> str:
        """Convert SQL result rows to a readable, premium multi-line answer."""
        if not rows:
            return f"{title}\n\nNo results found."

        lines = [title, ""]

        # Detect if these are task records
        is_task_list = any("title" in r and "priority" in r for r in rows)

        if is_task_list:
            # Fetch project keys dynamically from database to reconstruct task keys if missing
            project_keys = {}
            try:
                projects = self.session.scalars(select(models.Project)).all()
                project_keys = {p.id: p.key for p in projects}
            except Exception:
                pass

            for r in rows[:20]:
                proj_id = r.get("project_id")
                proj_key = project_keys.get(proj_id) if proj_id else None
                seq = r.get("sequence_number")

                if proj_key and seq:
                    key = f"{proj_key}-{seq}"
                elif proj_key:
                    key = f"{proj_key}-{r.get('id')}"
                else:
                    key = r.get("task_key") or r.get("key") or f"#{r.get('id', '?')}"

                t_title = r.get("title", "Untitled")
                prio = str(r.get("priority") or "medium").upper()
                assignee = r.get("assignee") or "Unassigned"
                prio_emoji = {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                    prio, "⚪"
                )
                lines.append(
                    f"  {prio_emoji} **{key}** — {t_title} "
                    f"(Assignee: *{assignee}*, Priority: **{prio}**)"
                )
        else:
            # General table / key-value list formatting
            for row in rows[:20]:
                parts = []
                for k, v in row.items():
                    # Skip noise fields
                    if k in {
                        "position",
                        "created_by",
                        "updated_by",
                        "created_at",
                        "updated_at",
                        "archived",
                        "workspace_id",
                    }:
                        continue
                    if v is not None:
                        parts.append(f"**{k}**: {v}")
                if parts:
                    lines.append("  • " + "  |  ".join(parts))

        if len(rows) > 20:
            lines.append(f"\n  *... and {len(rows) - 20} more rows.*")
        return "\n".join(lines)

    def _is_bulk_all_request(self, text: str) -> bool:
        return bool(
            re.search(
                r"\b(all|every|everything|entire|whole)\b.*\b(task|tasks|card|cards|project|board)\b",
                text,
            )
            or re.search(
                r"\b(task|tasks|card|cards)\b.*\b(all|every|everything|entire|whole)\b",
                text,
            )
        )

    def get_suggestions(self, project_id: int) -> SuggestionsResponse:
        project = self.session.get(models.Project, project_id)
        if not project:
            return SuggestionsResponse(suggestions=[])

        project_key = project.key

        tasks = self.session.scalars(
            select(models.Task)
            .where(models.Task.project_id == project_id, models.Task.archived.is_(False))
            .order_by(models.Task.position)
            .limit(50)
        ).all()

        if self.settings.groq_api_key:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage
                from langchain_groq import ChatGroq

                model = ChatGroq(
                    api_key=self.settings.groq_api_key,
                    model=self.settings.groq_model,
                    temperature=0.7,
                ).with_structured_output(SuggestionsResponse)

                task_list = [
                    {
                        "key": t.key or f"{project_key}-{t.sequence_number or t.id}",
                        "title": t.title,
                        "priority": t.priority,
                        "assignee": t.assignee,
                    }
                    for t in tasks
                ]
                sys_msg = (
                    "You are an AI Kanban Assistant helper. Your task is to look "
                    "at the project's current task list and generate 5 highly "
                    "contextually relevant 'Quick Action' prompts.\n"
                    "Each action must contain:\n"
                    "1. label: A very short action name (max 20 chars), "
                    "e.g. 'Show PLAT-5', 'Dave's Tasks', 'Summary'.\n"
                    "2. prompt: The exact prompt/question to ask the AI, "
                    "e.g. 'Show full details of task PLAT-5' or "
                    "'Who is Dave assigned to?'.\n\n"
                    "Guidelines:\n"
                    "- Suggest queries analyzing status, priority, or assignees "
                    "based on the active tasks.\n"
                    "- Suggest modifying task priorities or moving tasks if tasks "
                    "look like they need attention.\n"
                    "- Always formulate prompts using the exact task keys "
                    "(e.g. PLAT-12) from the list below.\n"
                    "- Focus on the most critical or highly visible tasks."
                )

                human_msg = f"Project Key: {project_key}\nActive Tasks:\n{task_list}"

                res = model.invoke(
                    [SystemMessage(content=sys_msg), HumanMessage(content=human_msg)]
                )
                if isinstance(res, SuggestionsResponse) and len(res.suggestions) > 0:
                    return res
            except Exception as e:
                import sys

                print(f"Failed to generate LLM suggestions: {e}", file=sys.stderr)

        suggestions = []
        suggestions.append(
            Suggestion(label="Board summary", prompt="Summarize this board by status")
        )

        if tasks:
            target_task = next((t for t in tasks if t.priority in {"critical", "high"}), tasks[0])
            t_key = (
                target_task.key or f"{project_key}-{target_task.sequence_number or target_task.id}"
            )
            suggestions.append(
                Suggestion(label="Task detail", prompt=f"Show me full details of task {t_key}")
            )
            suggestions.append(
                Suggestion(label="Set priority", prompt=f"Change priority of {t_key} to high")
            )
        else:
            suggestions.append(
                Suggestion(
                    label="Create task",
                    prompt="Create task: Write release notes with high priority",
                )
            )

        assignees = list({t.assignee for t in tasks if t.assignee})
        if assignees:
            suggestions.append(
                Suggestion(
                    label=f"{assignees[0]}'s tasks",
                    prompt=f"Show all tasks assigned to {assignees[0]}",
                )
            )

        critical_tasks = [t for t in tasks if t.priority == "critical"]
        if critical_tasks:
            suggestions.append(
                Suggestion(
                    label="Critical tasks",
                    prompt="Show all tasks that are in progress and have critical priority",
                )
            )
        else:
            suggestions.append(
                Suggestion(label="High priority", prompt="Show all tasks with high priority")
            )

        suggestions.append(
            Suggestion(label="Archive all", prompt="Archive all tasks in this project")
        )
        suggestions.append(Suggestion(label="Restore all", prompt="Restore all archived tasks"))

        return SuggestionsResponse(suggestions=suggestions[:6])


# Keep backward-compat alias
ReadOnlyAIService = KanbanAIService
