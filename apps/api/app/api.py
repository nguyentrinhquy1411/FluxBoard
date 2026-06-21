from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_db
from app.master import MasterOrchestrator
from app.repositories import ProjectRepository, TaskRepository
from app.schemas.product import (
    AIQueryRequest,
    AIQueryResponse,
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
    SuggestionsResponse,
    TaskCreate,
    TaskMove,
    TaskRead,
    TaskUpdate,
)
from app.schemas.validation import OrchestrationResult, QueryRequest, SecurityViolation
from app.services.ai import KanbanAIService

settings = get_settings()
app = FastAPI(title=settings.app_name)
DB_DEPENDENCY = Depends(get_db)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=OrchestrationResult)
async def query(request: QueryRequest) -> OrchestrationResult:
    orchestrator = MasterOrchestrator()
    try:
        return await orchestrator.run(request)
    except SecurityViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/api/projects", response_model=list[ProjectRead])
def list_projects(db: Session = DB_DEPENDENCY) -> list[ProjectRead]:
    return ProjectRepository(db).list_projects()


@app.post("/api/projects", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = DB_DEPENDENCY) -> ProjectRead:
    try:
        return ProjectRepository(db).create_project(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/board", response_model=BoardRead)
def get_board(project_id: int, db: Session = DB_DEPENDENCY) -> BoardRead:
    try:
        return ProjectRepository(db).board(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/archived", response_model=list[TaskRead])
def list_archived_tasks(project_id: int, db: Session = DB_DEPENDENCY) -> list[TaskRead]:
    try:
        return ProjectRepository(db).archived_tasks(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/statuses", response_model=BoardRead, status_code=201)
def create_status(
    project_id: int,
    payload: StatusCreate,
    db: Session = DB_DEPENDENCY,
) -> BoardRead:
    try:
        return ProjectRepository(db).create_status(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/tasks", response_model=TaskRead, status_code=201)
def create_task(project_id: int, payload: TaskCreate, db: Session = DB_DEPENDENCY) -> TaskRead:
    try:
        return TaskRepository(db).create_task(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, db: Session = DB_DEPENDENCY) -> TaskRead:
    try:
        return TaskRepository(db).update_task(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/move", response_model=TaskRead)
def move_task(task_id: int, payload: TaskMove, db: Session = DB_DEPENDENCY) -> TaskRead:
    try:
        return TaskRepository(db).move_task(
            task_id,
            status_id=payload.status_id,
            after_task_id=payload.after_task_id,
            before_task_id=payload.before_task_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/archive", response_model=TaskRead)
def archive_task(task_id: int, db: Session = DB_DEPENDENCY) -> TaskRead:
    try:
        return TaskRepository(db).archive_task(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/restore", response_model=TaskRead)
def restore_task(task_id: int, db: Session = DB_DEPENDENCY) -> TaskRead:
    try:
        return TaskRepository(db).restore_task(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tasks/{task_id}/comments", response_model=list[CommentRead])
def list_comments(task_id: int, db: Session = DB_DEPENDENCY) -> list[CommentRead]:
    try:
        return TaskRepository(db).list_comments(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/comments", response_model=CommentRead, status_code=201)
def create_comment(
    task_id: int,
    payload: CommentCreate,
    db: Session = DB_DEPENDENCY,
) -> CommentRead:
    try:
        return TaskRepository(db).create_comment(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/ai/query", response_model=AIQueryResponse)
def ai_query(payload: AIQueryRequest, db: Session = DB_DEPENDENCY) -> AIQueryResponse:
    # Triggering reload to pick up master.py prompt updates on Windows
    return KanbanAIService(db, get_settings()).answer(
        payload.project_id, payload.question, payload.user_email
    )


@app.get("/api/projects/{project_id}/ai/suggestions", response_model=SuggestionsResponse)
def ai_suggestions(project_id: int, db: Session = DB_DEPENDENCY) -> SuggestionsResponse:
    return KanbanAIService(db, get_settings()).get_suggestions(project_id)


@app.get("/api/projects/{project_id}/members", response_model=list[ProjectMemberRead])
def list_project_members(project_id: int, db: Session = DB_DEPENDENCY) -> list[ProjectMemberRead]:
    try:
        return ProjectRepository(db).list_members(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/members", response_model=ProjectMemberRead, status_code=201)
def add_project_member(
    project_id: int, payload: ProjectMemberCreate, db: Session = DB_DEPENDENCY
) -> ProjectMemberRead:
    try:
        return ProjectRepository(db).add_member(project_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/members/{member_id}", status_code=204)
def remove_project_member(member_id: int, db: Session = DB_DEPENDENCY) -> None:
    try:
        ProjectRepository(db).remove_member(member_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/invites", response_model=ProjectInviteRead, status_code=201)
def create_project_invite(
    project_id: int, payload: ProjectInviteCreate, db: Session = DB_DEPENDENCY
) -> ProjectInviteRead:
    try:
        return ProjectRepository(db).create_invite(project_id, payload)
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
    token: str, payload: InviteAcceptPayload, db: Session = DB_DEPENDENCY
) -> dict[str, int]:
    try:
        project_id = ProjectRepository(db).accept_invite(token, payload)
        return {"project_id": project_id}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
