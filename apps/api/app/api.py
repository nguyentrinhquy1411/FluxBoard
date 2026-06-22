from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_optional_user, router as auth_router
from app.config import get_settings
from app.database import models
from app.database.session import get_db
from app.master import MasterOrchestrator
from app.repositories import ProjectRepository, TaskRepository
from app.schemas.auth import UserRead
from app.schemas.product import (
    AIQueryRequest,
    AIQueryResponse,
    BoardRead,
    CommentCreate,
    CommentRead,
    DigestResponse,
    InviteAcceptPayload,
    ProjectCreate,
    ProjectInviteCreate,
    ProjectInviteRead,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
    StatusCreate,
    SuggestionsResponse,
    TaskCreate,
    TaskMove,
    TaskRead,
    TaskUpdate,
)
from app.schemas.validation import OrchestrationResult, QueryRequest, SecurityViolation
from app.security import normalize_email
from app.services.ai import KanbanAIService

settings = get_settings()
app = FastAPI(title=settings.app_name)
DB_DEPENDENCY = Depends(get_db)
CURRENT_USER_DEP = Depends(get_current_user)
OPTIONAL_USER_DEP = Depends(get_optional_user)

app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def is_public_project(project: models.Project) -> bool:
    return project.key == "SMOKE"


def _load_project(project_id: int, db: Session) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def require_membership(
    project: models.Project,
    user: models.User | None,
    db: Session,
) -> models.ProjectMember | None:
    if is_public_project(project):
        return None
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    email = normalize_email(user.email)
    member = db.scalar(
        select(models.ProjectMember).where(
            models.ProjectMember.project_id == project.id,
            models.ProjectMember.email == email,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="You are not a member of this project")
    return member


def require_admin(
    project: models.Project,
    user: models.User | None,
    db: Session,
) -> models.ProjectMember | None:
    if is_public_project(project):
        # Any logged-in user can write on SMOKE (public playground)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required to write to this project")
        return None
    member = require_membership(project, user, db)
    if member is None or member.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required for this action")
    return member


def require_task_access(
    task_id: int,
    user: models.User | None,
    require_admin_role: bool = False,
    db: Session = None,
) -> models.Task:
    task = db.get(models.Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    project = _load_project(task.project_id, db)
    if require_admin_role:
        require_admin(project, user, db)
    else:
        require_membership(project, user, db)
    return task


def require_member_access(
    member_id: int,
    user: models.User | None,
    require_admin_role: bool = False,
    db: Session = None,
) -> models.ProjectMember:
    member = db.get(models.ProjectMember, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    project = _load_project(member.project_id, db)
    if require_admin_role:
        require_admin(project, user, db)
    else:
        require_membership(project, user, db)
    return member


def _actor(user: models.User | None) -> str:
    return normalize_email(user.email) if user else "system"


# ── Core routes ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=OrchestrationResult)
async def query(
    request: QueryRequest,
    user: models.User = CURRENT_USER_DEP,
) -> OrchestrationResult:
    # For the HTTP path, override any client-supplied roles with a safe default.
    # In-process callers (CLI, eval harness) supply roles programmatically and
    # never go through this endpoint.
    safe_request = request.model_copy(update={"roles": ["viewer"]})
    orchestrator = MasterOrchestrator()
    try:
        return await orchestrator.run(safe_request)
    except SecurityViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/api/projects", response_model=list[ProjectRead])
def list_projects(
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> list[ProjectRead]:
    email = normalize_email(user.email) if user else None
    return ProjectRepository(db, actor=_actor(user)).list_projects(user_email=email)


@app.post("/api/projects", response_model=ProjectRead, status_code=201)
def create_project(
    payload: ProjectCreate,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> ProjectRead:
    email = normalize_email(user.email)
    try:
        return ProjectRepository(db, actor=email).create_project(payload, creator_email=email)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> ProjectRead:
    project = _load_project(project_id, db)
    require_membership(project, user, db)
    return ProjectRead.model_validate(project)


@app.get("/api/projects/{project_id}/membership")
def get_project_membership(
    project_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> dict:
    project = _load_project(project_id, db)
    if is_public_project(project):
        if user is None:
            return {"role": "viewer", "is_member": False}
        email = normalize_email(user.email)
        member = db.scalar(
            select(models.ProjectMember).where(
                models.ProjectMember.project_id == project_id,
                models.ProjectMember.email == email,
            )
        )
        role = member.role if member else "admin"  # logged-in users can write on SMOKE
        return {"role": role, "is_member": member is not None}
    if user is None:
        return {"role": None, "is_member": False}
    email = normalize_email(user.email)
    member = db.scalar(
        select(models.ProjectMember).where(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.email == email,
        )
    )
    if member is None:
        return {"role": None, "is_member": False}
    return {"role": member.role, "is_member": True}


@app.get("/api/projects/{project_id}/board", response_model=BoardRead)
def get_board(
    project_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> BoardRead:
    project = _load_project(project_id, db)
    require_membership(project, user, db)
    try:
        return ProjectRepository(db, actor=_actor(user)).board(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/archived", response_model=list[TaskRead])
def list_archived_tasks(
    project_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> list[TaskRead]:
    project = _load_project(project_id, db)
    require_membership(project, user, db)
    try:
        return ProjectRepository(db, actor=_actor(user)).archived_tasks(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/statuses", response_model=BoardRead, status_code=201)
def create_status(
    project_id: int,
    payload: StatusCreate,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> BoardRead:
    project = _load_project(project_id, db)
    require_admin(project, user, db)
    try:
        return ProjectRepository(db, actor=_actor(user)).create_status(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/tasks", response_model=TaskRead, status_code=201)
def create_task(
    project_id: int,
    payload: TaskCreate,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> TaskRead:
    project = _load_project(project_id, db)
    require_admin(project, user, db)
    try:
        return TaskRepository(db, actor=_actor(user)).create_task(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.patch("/api/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> TaskRead:
    require_task_access(task_id, user, require_admin_role=True, db=db)
    try:
        return TaskRepository(db, actor=_actor(user)).update_task(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/move", response_model=TaskRead)
def move_task(
    task_id: int,
    payload: TaskMove,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> TaskRead:
    require_task_access(task_id, user, require_admin_role=True, db=db)
    try:
        return TaskRepository(db, actor=_actor(user)).move_task(
            task_id,
            status_id=payload.status_id,
            after_task_id=payload.after_task_id,
            before_task_id=payload.before_task_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/archive", response_model=TaskRead)
def archive_task(
    task_id: int,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> TaskRead:
    require_task_access(task_id, user, require_admin_role=True, db=db)
    try:
        return TaskRepository(db, actor=_actor(user)).archive_task(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/restore", response_model=TaskRead)
def restore_task(
    task_id: int,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> TaskRead:
    require_task_access(task_id, user, require_admin_role=True, db=db)
    try:
        return TaskRepository(db, actor=_actor(user)).restore_task(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Comments ──────────────────────────────────────────────────────────────────

@app.get("/api/tasks/{task_id}/comments", response_model=list[CommentRead])
def list_comments(
    task_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> list[CommentRead]:
    require_task_access(task_id, user, require_admin_role=False, db=db)
    try:
        return TaskRepository(db, actor=_actor(user)).list_comments(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/comments", response_model=CommentRead, status_code=201)
def create_comment(
    task_id: int,
    payload: CommentCreate,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> CommentRead:
    require_task_access(task_id, user, require_admin_role=False, db=db)
    try:
        return TaskRepository(db, actor=_actor(user)).create_comment(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── AI ────────────────────────────────────────────────────────────────────────

@app.post("/api/ai/query", response_model=AIQueryResponse)
def ai_query(
    payload: AIQueryRequest,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> AIQueryResponse:
    project = db.get(models.Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Derive role from authenticated identity
    if is_public_project(project):
        if user is None:
            roles = ["viewer"]
            actor_email = "anonymous"
        else:
            email = normalize_email(user.email)
            member = db.scalar(
                select(models.ProjectMember).where(
                    models.ProjectMember.project_id == payload.project_id,
                    models.ProjectMember.email == email,
                )
            )
            roles = [member.role] if member else ["admin"]  # logged-in on SMOKE -> can write
            actor_email = email
    else:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        email = normalize_email(user.email)
        member = db.scalar(
            select(models.ProjectMember).where(
                models.ProjectMember.project_id == payload.project_id,
                models.ProjectMember.email == email,
            )
        )
        if member is None:
            raise HTTPException(status_code=403, detail="You are not a member of this project")
        roles = [member.role]
        actor_email = email

    return KanbanAIService(db, get_settings()).answer(
        payload.project_id, payload.question, actor_email=actor_email, roles=roles
    )


@app.get("/api/projects/{project_id}/ai/suggestions", response_model=SuggestionsResponse)
def ai_suggestions(
    project_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> SuggestionsResponse:
    project = _load_project(project_id, db)
    require_membership(project, user, db)
    return KanbanAIService(db, get_settings()).get_suggestions(project_id)


@app.get("/api/projects/{project_id}/ai/digest", response_model=DigestResponse)
def ai_digest(
    project_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> DigestResponse:
    project = _load_project(project_id, db)
    require_membership(project, user, db)
    return KanbanAIService(db, get_settings()).digest(project_id)


# ── Members ───────────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/members", response_model=list[ProjectMemberRead])
def list_project_members(
    project_id: int,
    user: models.User | None = OPTIONAL_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> list[ProjectMemberRead]:
    project = _load_project(project_id, db)
    require_membership(project, user, db)
    try:
        return ProjectRepository(db, actor=_actor(user)).list_members(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/members", response_model=ProjectMemberRead, status_code=201)
def add_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> ProjectMemberRead:
    project = _load_project(project_id, db)
    require_admin(project, user, db)
    try:
        return ProjectRepository(db, actor=_actor(user)).add_member(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/members/{member_id}", status_code=204)
def remove_project_member(
    member_id: int,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> None:
    require_member_access(member_id, user, require_admin_role=True, db=db)
    try:
        ProjectRepository(db, actor=_actor(user)).remove_member(member_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Invites ───────────────────────────────────────────────────────────────────

@app.post("/api/projects/{project_id}/invites", response_model=ProjectInviteRead, status_code=201)
def create_project_invite(
    project_id: int,
    payload: ProjectInviteCreate,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> ProjectInviteRead:
    project = _load_project(project_id, db)
    require_admin(project, user, db)
    try:
        return ProjectRepository(db, actor=_actor(user)).create_invite(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/invites/{token}", response_model=ProjectInviteRead)
def get_project_invite(token: str, db: Session = DB_DEPENDENCY) -> ProjectInviteRead:
    try:
        return ProjectRepository(db).get_invite(token)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.post("/api/invites/{token}/accept")
def accept_project_invite(
    token: str,
    payload: InviteAcceptPayload,
    user: models.User = CURRENT_USER_DEP,
    db: Session = DB_DEPENDENCY,
) -> dict[str, int]:
    try:
        project_id = ProjectRepository(db, actor=_actor(user)).accept_invite(
            token,
            user_email=normalize_email(user.email),
            display_name=payload.name,
        )
        return {"project_id": project_id}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
