from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="local-user")

    projects: Mapped[list[Project]] = relationship(back_populates="workspace")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="local-user")
    updated_by: Mapped[str] = mapped_column(String(120), nullable=False, default="local-user")

    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    statuses: Mapped[list[Status]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Status.position",
    )
    tasks: Mapped[list[Task]] = relationship(back_populates="project", cascade="all, delete-orphan")
    members: Mapped[list[ProjectMember]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_projects_workspace_key"),)


class Status(Base, TimestampMixin):
    __tablename__ = "statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    color: Mapped[str] = mapped_column(String(24), nullable=False, default="slate")
    position: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"))

    project: Mapped[Project] = relationship(back_populates="statuses")
    tasks: Mapped[list[Task]] = relationship(back_populates="status")

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_statuses_project_name"),)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(ForeignKey("statuses.id"), nullable=False)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    key: Mapped[str | None] = mapped_column("task_key", String(64))
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    assignee: Mapped[str | None] = mapped_column(String(160))
    due_date: Mapped[datetime | None] = mapped_column(DateTime)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="local-user")
    updated_by: Mapped[str] = mapped_column(String(120), nullable=False, default="local-user")

    project: Mapped[Project] = relationship(back_populates="tasks")
    status: Mapped[Status] = relationship(back_populates="tasks")
    labels: Mapped[list[TaskLabel]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_tasks_project_status_position", "project_id", "status_id", "position"),
        UniqueConstraint("project_id", "task_key", name="uq_tasks_project_task_key"),
    )


class Label(Base, TimestampMixin):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(24), nullable=False, default="slate")

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_labels_project_name"),)


class TaskLabel(Base):
    __tablename__ = "task_labels"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    label_id: Mapped[int] = mapped_column(ForeignKey("labels.id"), primary_key=True)

    task: Mapped[Task] = relationship(back_populates="labels")
    label: Mapped[Label] = relationship()


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="local-user")

    task: Mapped[Task] = relationship(back_populates="comments")


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="local-user")
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProjectMember(Base, TimestampMixin):
    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="viewer")

    project: Mapped[Project] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("project_id", "email", name="uq_project_members_project_email"),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProjectInvite(Base):
    __tablename__ = "project_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="viewer")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped[Project] = relationship()
