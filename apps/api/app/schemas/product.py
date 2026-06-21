from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    key: str = Field(min_length=1, max_length=32)
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class StatusCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = "active"
    color: str = "slate"


class StatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    color: str
    position: Decimal


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=220)
    description: str | None = None
    status_id: int | None = None
    priority: str = "medium"
    assignee: str | None = None
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=220)
    description: str | None = None
    status_id: int | None = None
    priority: str | None = None
    assignee: str | None = None
    due_date: datetime | None = None
    archived: bool | None = None


class TaskMove(BaseModel):
    status_id: int
    after_task_id: int | None = None
    before_task_id: int | None = None


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str | None = None
    sequence_number: int | None = None
    rank: Decimal
    project_id: int
    status_id: int
    title: str
    description: str | None = None
    priority: str
    assignee: str | None = None
    due_date: datetime | None = None
    archived: bool
    position: Decimal
    labels: list[LabelRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BoardColumn(BaseModel):
    status: StatusRead
    tasks: list[TaskRead]


class BoardRead(BaseModel):
    project: ProjectRead
    columns: list[BoardColumn]


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    body: str
    created_by: str
    created_at: datetime


class AIQueryRequest(BaseModel):
    project_id: int
    question: str = Field(min_length=1)
    user_email: str | None = None


class ProjectMemberCreate(BaseModel):
    email: str = Field(min_length=1, max_length=160)
    role: str = "viewer"


class ProjectMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    email: str
    display_name: str | None = None
    role: str
    created_at: datetime


class AIResponsePresentation(BaseModel):
    title: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class AIQueryResponse(BaseModel):
    answer: str
    sql: str
    rows: list[dict]
    used_model: str
    fallback: bool = False
    action: str = "read_board"
    affected_tasks: list[TaskRead] = Field(default_factory=list)
    presentation: AIResponsePresentation | None = None


class Suggestion(BaseModel):
    label: str
    prompt: str


class SuggestionsResponse(BaseModel):
    suggestions: list[Suggestion]


class ProjectInviteCreate(BaseModel):
    role: str = "viewer"
    expires_in_hours: int = 24


class ProjectInviteRead(BaseModel):
    id: int
    project_id: int
    project_name: str
    token: str
    role: str
    expires_at: datetime
    created_at: datetime


class InviteAcceptPayload(BaseModel):
    email: str = Field(min_length=1, max_length=160)
    name: str | None = Field(default=None, max_length=160)
