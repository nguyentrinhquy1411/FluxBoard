from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import models
from app.schemas.product import (
    BoardColumn,
    BoardRead,
    CommentCreate,
    CommentRead,
    InviteAcceptPayload,
    ProjectCreate,
    ProjectInviteCreate,
    ProjectInviteRead,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
    StatusCreate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)

LOCAL_USER = "local-user"


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _ensure_smoke_project(self) -> models.Project:
        smoke = self.session.scalar(
            select(models.Project).where(models.Project.key == "SMOKE")
        )
        if smoke is not None:
            return smoke

        workspace = self._ensure_workspace()
        smoke = models.Project(
            workspace_id=workspace.id,
            name="Smoke Project",
            key="SMOKE",
            description="A public project for guests to test the app.",
            created_by=LOCAL_USER,
            updated_by=LOCAL_USER,
        )
        self.session.add(smoke)
        self.session.flush()
        # Add default admin project member
        self.session.add(
            models.ProjectMember(
                project_id=smoke.id, email="local-user@example.com", role="admin"
            )
        )
        self.session.flush()
        for index, (name, category, color) in enumerate(
            [
                ("Backlog", "todo", "slate"),
                ("In Progress", "active", "blue"),
                ("Review", "active", "amber"),
                ("Done", "done", "green"),
            ]
        ):
            self.session.add(
                models.Status(
                    project_id=smoke.id,
                    name=name,
                    category=category,
                    color=color,
                    position=Decimal(index * 1000),
                )
            )
        self._activity(smoke.id, None, "project.created", {"name": smoke.name})
        self.session.flush()

        # Seed default tasks in the SMOKE project for play testing
        statuses = self.session.scalars(
            select(models.Status)
            .where(models.Status.project_id == smoke.id)
            .order_by(models.Status.position)
        ).all()

        task_prefixes = [
            "Refactor",
            "Implement",
            "Design",
            "Write tests for",
            "Fix bug in",
            "Optimize",
            "Document",
            "Review",
            "Deploy",
            "Investigate",
        ]
        task_nouns = [
            "authentication flow",
            "database indexes",
            "UI components",
            "API endpoints",
            "AI assistant agent",
            "invite link logic",
            "payment gateway integration",
            "search functionality",
            "analytics dashboard",
            "notification system",
        ]
        task_descriptions = [
            "Ensure that this component operates cleanly under high concurrent load.",
            "Review code with team members and obtain approval before merging.",
            "Write comprehensive unit and integration tests to cover all edge cases.",
            "Document the API surface area and publish to internal wiki.",
            "Optimize execution time and memory footprint of the core routine.",
        ]
        priorities = ["low", "medium", "high", "critical"]

        # Generate exactly 100 mock tasks distributed across the 4 statuses
        for idx in range(1, 101):
            prefix = task_prefixes[(idx - 1) % len(task_prefixes)]
            noun = task_nouns[(idx - 1) % len(task_nouns)]
            desc = task_descriptions[(idx - 1) % len(task_descriptions)]
            priority = priorities[(idx - 1) % len(priorities)]

            # Columns: Backlog (30), In Progress (30), Review (20), Done (20)
            if idx <= 30:
                status_id = statuses[0].id
                pos_multiplier = idx
            elif idx <= 60:
                status_id = statuses[1].id
                pos_multiplier = idx - 30
            elif idx <= 80:
                status_id = statuses[2].id
                pos_multiplier = idx - 60
            else:
                status_id = statuses[3].id
                pos_multiplier = idx - 80

            self.session.add(
                models.Task(
                    project_id=smoke.id,
                    status_id=status_id,
                    sequence_number=idx,
                    key=f"SMOKE-{idx}",
                    title=f"{prefix} {noun} (#{idx})",
                    description=desc,
                    priority=priority,
                    position=Decimal(pos_multiplier * 1000),
                    created_by=LOCAL_USER,
                    updated_by=LOCAL_USER,
                )
            )

        self.session.flush()
        self.session.refresh(smoke)
        return smoke

    def list_projects(self, user_email: str | None = None) -> list[ProjectRead]:
        self._ensure_smoke_project()
        query = select(models.Project)
        if user_email:
            member_project_ids = select(models.ProjectMember.project_id).where(
                models.ProjectMember.email == user_email
            )
            query = query.where(
                (models.Project.id.in_(member_project_ids)) |
                (models.Project.key == "SMOKE")
            )
        else:
            query = query.where(models.Project.key == "SMOKE")

        projects = self.session.scalars(
            query.order_by(models.Project.created_at)
        ).all()
        return [ProjectRead.model_validate(project) for project in projects]

    def create_project(
        self, payload: ProjectCreate, creator_email: str = "local-user@example.com"
    ) -> ProjectRead:
        workspace = self._ensure_workspace()

        # Automatically deduplicate project keys in the workspace
        base_key = payload.key.upper()
        unique_key = base_key
        counter = 1
        while self.session.scalar(
            select(models.Project).where(
                models.Project.workspace_id == workspace.id,
                models.Project.key == unique_key,
            )
        ) is not None:
            suffix = str(counter)
            unique_key = f"{base_key[:32 - len(suffix)]}{suffix}"
            counter += 1

        project = models.Project(
            workspace_id=workspace.id,
            name=payload.name,
            key=unique_key,
            description=payload.description,
            created_by=creator_email,
            updated_by=creator_email,
        )
        self.session.add(project)
        self.session.flush()
        # Add creator as admin project member
        self.session.add(
            models.ProjectMember(
                project_id=project.id, email=creator_email, role="admin"
            )
        )
        self.session.flush()
        for index, (name, category, color) in enumerate(
            [
                ("Backlog", "todo", "slate"),
                ("In Progress", "active", "blue"),
                ("Review", "active", "amber"),
                ("Done", "done", "green"),
            ]
        ):
            self.session.add(
                models.Status(
                    project_id=project.id,
                    name=name,
                    category=category,
                    color=color,
                    position=Decimal(index * 1000),
                )
            )
        self._activity(project.id, None, "project.created", {"name": project.name})
        self.session.flush()
        self.session.refresh(project)
        return ProjectRead.model_validate(project)

    def get_project(self, project_id: int) -> models.Project:
        project = self.session.get(models.Project, project_id)
        if project is None:
            raise LookupError("project not found")
        return project

    def create_status(self, project_id: int, payload: StatusCreate) -> BoardRead:
        self.get_project(project_id)
        max_position = self.session.scalar(
            select(func.max(models.Status.position)).where(models.Status.project_id == project_id)
        )
        next_position = Decimal(max_position or 0) + Decimal(1000)
        self.session.add(
            models.Status(
                project_id=project_id,
                name=payload.name,
                category=payload.category,
                color=payload.color,
                position=next_position,
            )
        )
        self._activity(project_id, None, "status.created", payload.model_dump())
        self.session.flush()
        return self.board(project_id)

    def board(self, project_id: int) -> BoardRead:
        project = self.get_project(project_id)
        statuses = self.session.scalars(
            select(models.Status)
            .where(models.Status.project_id == project_id)
            .order_by(models.Status.position)
        ).all()
        tasks = self.session.scalars(
            select(models.Task)
            .options(selectinload(models.Task.labels).selectinload(models.TaskLabel.label))
            .where(models.Task.project_id == project_id, models.Task.archived.is_(False))
            .order_by(models.Task.status_id, models.Task.position, models.Task.created_at)
        ).all()
        tasks_by_status: dict[int, list[TaskRead]] = {status.id: [] for status in statuses}
        for task in tasks:
            tasks_by_status.setdefault(task.status_id, []).append(task_to_read(task))
        return BoardRead(
            project=ProjectRead.model_validate(project),
            columns=[
                BoardColumn(
                    status=status,
                    tasks=tasks_by_status.get(status.id, []),
                )
                for status in statuses
            ],
        )

    def archived_tasks(self, project_id: int) -> list[TaskRead]:
        self.get_project(project_id)
        tasks = self.session.scalars(
            select(models.Task)
            .options(selectinload(models.Task.labels).selectinload(models.TaskLabel.label))
            .where(models.Task.project_id == project_id, models.Task.archived.is_(True))
            .order_by(models.Task.updated_at.desc(), models.Task.created_at.desc())
        ).all()
        return [task_to_read(task) for task in tasks]

    def _ensure_workspace(self) -> models.Workspace:
        workspace = self.session.scalar(
            select(models.Workspace).where(models.Workspace.slug == "default")
        )
        if workspace is not None:
            return workspace
        workspace = models.Workspace(
            name="Default Workspace",
            slug="default",
            created_by=LOCAL_USER,
        )
        self.session.add(workspace)
        self.session.flush()
        return workspace

    def _activity(
        self,
        project_id: int,
        task_id: int | None,
        event_type: str,
        payload: dict,
    ) -> None:
        self.session.add(
            models.ActivityEvent(
                project_id=project_id,
                task_id=task_id,
                actor=LOCAL_USER,
                event_type=event_type,
                payload=json.dumps(payload, default=str),
            )
        )

    def list_members(self, project_id: int) -> list[models.ProjectMember]:
        self.get_project(project_id)
        members = self.session.scalars(
            select(models.ProjectMember)
            .where(models.ProjectMember.project_id == project_id)
            .order_by(models.ProjectMember.created_at)
        ).all()
        return list(members)

    def add_member(self, project_id: int, payload: ProjectMemberCreate) -> models.ProjectMember:
        self.get_project(project_id)
        existing = self.session.scalar(
            select(models.ProjectMember).where(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.email == payload.email,
            )
        )
        if existing:
            existing.role = payload.role
            self.session.flush()
            return existing

        member = models.ProjectMember(project_id=project_id, email=payload.email, role=payload.role)
        self.session.add(member)
        self.session.flush()
        return member

    def remove_member(self, member_id: int) -> None:
        member = self.session.get(models.ProjectMember, member_id)
        if not member:
            raise LookupError(f"Project member with ID {member_id} not found")
        self.session.delete(member)
        self.session.flush()

    def create_invite(self, project_id: int, payload: ProjectInviteCreate) -> ProjectInviteRead:
        project = self.get_project(project_id)
        token = str(uuid.uuid4())
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            hours=payload.expires_in_hours
        )

        invite = models.ProjectInvite(
            project_id=project_id, token=token, role=payload.role, expires_at=expires_at
        )
        self.session.add(invite)
        self.session.flush()
        self.session.commit()

        return ProjectInviteRead(
            id=invite.id,
            project_id=invite.project_id,
            project_name=project.name,
            token=invite.token,
            role=invite.role,
            expires_at=invite.expires_at,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )

    def get_invite(self, token: str) -> ProjectInviteRead:
        invite = self.session.scalar(
            select(models.ProjectInvite).where(models.ProjectInvite.token == token)
        )
        if not invite:
            raise LookupError("Invitation link is invalid or has been removed.")

        now = datetime.now(UTC).replace(tzinfo=None)
        if invite.expires_at < now:
            raise ValueError("This invitation link has expired.")

        project = self.session.get(models.Project, invite.project_id)
        if not project:
            raise LookupError("Associated project was not found.")

        return ProjectInviteRead(
            id=invite.id,
            project_id=invite.project_id,
            project_name=project.name,
            token=invite.token,
            role=invite.role,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )

    def accept_invite(self, token: str, payload: InviteAcceptPayload) -> int:
        invite_data = self.get_invite(token)

        self.add_member(
            invite_data.project_id, ProjectMemberCreate(email=payload.email, role=invite_data.role)
        )
        return invite_data.project_id


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_task(self, project_id: int, payload: TaskCreate) -> TaskRead:
        status_id = payload.status_id or self._first_status_id(project_id)
        self._ensure_status_in_project(project_id, status_id)
        position = self._next_position(project_id, status_id)
        sequence_number = self._next_sequence_number(project_id)
        task_key = f"{self._project_key(project_id)}-{sequence_number}"
        task = models.Task(
            project_id=project_id,
            status_id=status_id,
            sequence_number=sequence_number,
            key=task_key,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            assignee=payload.assignee,
            due_date=payload.due_date,
            position=position,
            created_by=LOCAL_USER,
            updated_by=LOCAL_USER,
        )
        self.session.add(task)
        self.session.flush()
        self._activity(project_id, task.id, "task.created", payload.model_dump())
        self.session.refresh(task)
        return task_to_read(task)

    def update_task(self, task_id: int, payload: TaskUpdate) -> TaskRead:
        task = self._get_task(task_id)
        changes = payload.model_dump(exclude_unset=True)
        if "status_id" in changes and changes["status_id"] is not None:
            self._ensure_status_in_project(task.project_id, changes["status_id"])
        for key, value in changes.items():
            setattr(task, key, value)
        task.updated_by = LOCAL_USER
        self._activity(task.project_id, task.id, "task.updated", changes)
        self.session.flush()
        self.session.refresh(task)
        return task_to_read(task)

    def move_task(
        self,
        task_id: int,
        status_id: int,
        after_task_id: int | None = None,
        before_task_id: int | None = None,
    ) -> TaskRead:
        task = self._get_task(task_id)
        self._ensure_status_in_project(task.project_id, status_id)
        task.status_id = status_id
        task.position = self._position_between(
            task.project_id,
            status_id,
            after_task_id,
            before_task_id,
        )
        task.updated_by = LOCAL_USER
        self._activity(
            task.project_id,
            task.id,
            "task.moved",
            {"status_id": status_id, "position": str(task.position)},
        )
        self.session.flush()
        self.session.refresh(task)
        return task_to_read(task)

    def archive_task(self, task_id: int) -> TaskRead:
        task = self._get_task(task_id)
        task.archived = True
        task.updated_by = LOCAL_USER
        self._activity(task.project_id, task.id, "task.archived", {"archived": True})
        self.session.flush()
        self.session.refresh(task)
        return task_to_read(task)

    def restore_task(self, task_id: int) -> TaskRead:
        task = self._get_task(task_id)
        task.archived = False
        task.updated_by = LOCAL_USER
        self._activity(task.project_id, task.id, "task.restored", {"archived": False})
        self.session.flush()
        self.session.refresh(task)
        return task_to_read(task)

    def find_task_for_project(
        self,
        project_id: int,
        task_id: int | None,
        title: str | None,
        task_key: str | None = None,
    ) -> models.Task:
        if task_key:
            task = self.session.scalar(
                select(models.Task).where(
                    models.Task.project_id == project_id,
                    func.lower(models.Task.key) == task_key.lower(),
                )
            )
            if task is not None:
                return task
        if task_id is not None:
            task = self._get_task(task_id)
            if task.project_id != project_id:
                raise LookupError("task not found in project")
            return task
        if title:
            task = self._semantic_task_match(project_id, title)
            if task is not None:
                return task
        raise LookupError("task not found")

    def list_comments(self, task_id: int) -> list[CommentRead]:
        self._get_task(task_id)
        comments = self.session.scalars(
            select(models.Comment)
            .where(models.Comment.task_id == task_id)
            .order_by(models.Comment.created_at)
        ).all()
        return [CommentRead.model_validate(comment) for comment in comments]

    def create_comment(self, task_id: int, payload: CommentCreate) -> CommentRead:
        task = self._get_task(task_id)
        comment = models.Comment(task_id=task_id, body=payload.body, created_by=LOCAL_USER)
        self.session.add(comment)
        self._activity(task.project_id, task.id, "comment.created", {"body": payload.body})
        self.session.flush()
        self.session.refresh(comment)
        return CommentRead.model_validate(comment)

    # ── Members ──────────────────────────────────────────────────────────────

    def list_members(self, project_id: int) -> list[ProjectMemberRead]:
        self.get_project(project_id)
        members = self.session.scalars(
            select(models.ProjectMember)
            .where(models.ProjectMember.project_id == project_id)
            .order_by(models.ProjectMember.created_at)
        ).all()
        return [ProjectMemberRead.model_validate(m) for m in members]

    def add_member(self, project_id: int, payload: ProjectMemberCreate) -> ProjectMemberRead:
        self.get_project(project_id)
        # Upsert: if already exists just update the role
        existing = self.session.scalar(
            select(models.ProjectMember).where(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.email == payload.email,
            )
        )
        if existing:
            existing.role = payload.role
            self.session.flush()
            self.session.refresh(existing)
            return ProjectMemberRead.model_validate(existing)
        member = models.ProjectMember(
            project_id=project_id,
            email=payload.email,
            role=payload.role,
        )
        self.session.add(member)
        self.session.flush()
        self.session.refresh(member)
        return ProjectMemberRead.model_validate(member)

    def remove_member(self, member_id: int) -> None:
        member = self.session.get(models.ProjectMember, member_id)
        if member is None:
            raise LookupError("member not found")
        self.session.delete(member)
        self.session.flush()

    # ── Invites ───────────────────────────────────────────────────────────────

    def create_invite(self, project_id: int, payload: ProjectInviteCreate) -> ProjectInviteRead:
        project = self.get_project(project_id)
        token = uuid.uuid4().hex
        expires_at = datetime.now(tz=UTC) + timedelta(hours=payload.expires_in_hours)
        invite = models.ProjectInvite(
            project_id=project_id,
            token=token,
            role=payload.role,
            expires_at=expires_at,
        )
        self.session.add(invite)
        self.session.flush()
        self.session.refresh(invite)
        return ProjectInviteRead(
            id=invite.id,
            project_id=invite.project_id,
            project_name=project.name,
            token=invite.token,
            role=invite.role,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )

    def get_invite(self, token: str) -> ProjectInviteRead:
        invite = self.session.scalar(
            select(models.ProjectInvite).where(models.ProjectInvite.token == token)
        )
        if invite is None:
            raise LookupError("invite not found")
        if invite.expires_at.replace(tzinfo=UTC) < datetime.now(tz=UTC):
            raise ValueError("invite has expired")
        return ProjectInviteRead(
            id=invite.id,
            project_id=invite.project_id,
            project_name=invite.project.name,
            token=invite.token,
            role=invite.role,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )

    def accept_invite(self, token: str, payload: InviteAcceptPayload) -> int:
        invite = self.session.scalar(
            select(models.ProjectInvite).where(models.ProjectInvite.token == token)
        )
        if invite is None:
            raise LookupError("invite not found")
        if invite.expires_at.replace(tzinfo=UTC) < datetime.now(tz=UTC):
            raise ValueError("invite has expired")
        # Add or update member
        existing = self.session.scalar(
            select(models.ProjectMember).where(
                models.ProjectMember.project_id == invite.project_id,
                models.ProjectMember.email == payload.email,
            )
        )
        if existing:
            existing.role = invite.role
            if payload.name:
                existing.display_name = payload.name
        else:
            member = models.ProjectMember(
                project_id=invite.project_id,
                email=payload.email,
                display_name=payload.name,
                role=invite.role,
            )
            self.session.add(member)
        self.session.flush()
        return invite.project_id

    def _get_task(self, task_id: int) -> models.Task:
        task = self.session.get(models.Task, task_id)
        if task is None:
            raise LookupError("task not found")
        return task

    def _first_status_id(self, project_id: int) -> int:
        status_id = self.session.scalar(
            select(models.Status.id)
            .where(models.Status.project_id == project_id)
            .order_by(models.Status.position)
            .limit(1)
        )
        if status_id is None:
            raise LookupError("project has no statuses")
        return status_id

    def _ensure_status_in_project(self, project_id: int, status_id: int) -> None:
        exists = self.session.scalar(
            select(models.Status.id)
            .where(models.Status.project_id == project_id, models.Status.id == status_id)
            .limit(1)
        )
        if exists is None:
            raise LookupError("status not found in project")

    def _next_position(self, project_id: int, status_id: int) -> Decimal:
        max_position = self.session.scalar(
            select(func.max(models.Task.position)).where(
                models.Task.project_id == project_id,
                models.Task.status_id == status_id,
            )
        )
        return Decimal(max_position or 0) + Decimal(1000)

    def _next_sequence_number(self, project_id: int) -> int:
        max_sequence = self.session.scalar(
            select(func.max(models.Task.sequence_number)).where(
                models.Task.project_id == project_id
            )
        )
        return int(max_sequence or 0) + 1

    def _project_key(self, project_id: int) -> str:
        project_key = self.session.scalar(
            select(models.Project.key).where(models.Project.id == project_id)
        )
        if not project_key:
            raise LookupError("project not found")
        return project_key.upper()

    def _semantic_task_match(self, project_id: int, query: str) -> models.Task | None:
        query_tokens = _semantic_tokens(query)
        if not query_tokens:
            return None
        tasks = self.session.scalars(
            select(models.Task)
            .where(models.Task.project_id == project_id)
            .order_by(models.Task.archived, models.Task.updated_at.desc())
        ).all()
        best_task: models.Task | None = None
        best_score = 0.0
        for task in tasks:
            haystack = " ".join(
                part
                for part in [task.key or "", task.title, task.description or "", task.priority]
                if part
            )
            score = _token_similarity(query_tokens, _semantic_tokens(haystack))
            if score > best_score:
                best_score = score
                best_task = task
        return best_task if best_score >= 0.34 else None

    def _position_between(
        self,
        project_id: int,
        status_id: int,
        after_task_id: int | None,
        before_task_id: int | None,
    ) -> Decimal:
        after_position = None
        before_position = None
        if after_task_id is not None:
            after_position = self._get_task(after_task_id).position
        if before_task_id is not None:
            before_position = self._get_task(before_task_id).position
        if after_position is not None and before_position is not None:
            return (Decimal(after_position) + Decimal(before_position)) / Decimal(2)
        if after_position is not None:
            return Decimal(after_position) + Decimal(1000)
        if before_position is not None:
            return Decimal(before_position) / Decimal(2)
        return self._next_position(project_id, status_id)

    def _activity(
        self,
        project_id: int,
        task_id: int | None,
        event_type: str,
        payload: dict,
    ) -> None:
        self.session.add(
            models.ActivityEvent(
                project_id=project_id,
                task_id=task_id,
                actor=LOCAL_USER,
                event_type=event_type,
                payload=json.dumps(payload, default=str),
            )
        )


def task_to_read(task: models.Task) -> TaskRead:
    return TaskRead(
        id=task.id,
        key=task.key,
        sequence_number=task.sequence_number,
        rank=task.position,
        project_id=task.project_id,
        status_id=task.status_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        assignee=task.assignee,
        due_date=task.due_date,
        archived=task.archived,
        position=task.position,
        labels=[task_label.label for task_label in task.labels],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _semantic_tokens(value: str) -> set[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in value)
    tokens = {token for token in normalized.split() if len(token) > 2}
    synonyms = {
        "bug": {"issue", "defect", "fix"},
        "archive": {"archieve", "hide", "remove"},
        "todo": {"backlog", "open"},
        "done": {"complete", "completed", "closed"},
    }
    expanded = set(tokens)
    for token in tokens:
        expanded.update(synonyms.get(token, set()))
    return expanded


def _token_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    exact = len(left & right) / len(left | right)
    partial = 0.0
    for token in left:
        if any(token in candidate or candidate in token for candidate in right):
            partial += 1
    fuzzy = 0.0
    for token in left:
        fuzzy = max(
            fuzzy,
            *(SequenceMatcher(None, token, candidate).ratio() for candidate in right),
        )
    return max(exact, partial / max(len(left), 1) * 0.72, fuzzy * 0.58)
