from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryDialect(StrEnum):
    SQL = "sql"
    JQL = "jql"
    DSL = "dsl"


class QueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(min_length=1)
    user_id: str = Field(default="local-user", min_length=1)
    roles: list[str] = Field(default_factory=lambda: ["viewer"])
    dialect: QueryDialect = QueryDialect.SQL
    project: str | None = None
    database_schema: DatabaseSchema | None = Field(default=None, alias="schema")


class ColumnDefinition(BaseModel):
    name: str
    data_type: str = "text"
    sensitive: bool = False
    roles_allowed: set[str] = Field(default_factory=set)

    def allowed_for(self, roles: set[str]) -> bool:
        return not self.roles_allowed or bool(self.roles_allowed & roles)


class ForeignKeyDefinition(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str


class TableDefinition(BaseModel):
    name: str
    columns: list[ColumnDefinition]
    roles_allowed: set[str] = Field(default_factory=set)

    def allowed_for(self, roles: set[str]) -> bool:
        return not self.roles_allowed or bool(self.roles_allowed & roles)


class DatabaseSchema(BaseModel):
    tables: list[TableDefinition]
    foreign_keys: list[ForeignKeyDefinition] = Field(default_factory=list)

    def table_names(self) -> set[str]:
        return {table.name for table in self.tables}

    def get_table(self, name: str) -> TableDefinition | None:
        return next((table for table in self.tables if table.name == name), None)


class SchemaContext(BaseModel):
    selected_tables: list[str]
    selected_columns: dict[str, list[str]]
    join_paths: list[list[str]] = Field(default_factory=list)
    entity_matches: dict[str, list[str]] = Field(default_factory=dict)
    token_budget_reduction_ratio: float = Field(ge=0.0, le=1.0)


class SecurityViolation(Exception):
    """Raised when a query violates the security veto policy."""


class SecurityResult(BaseModel):
    allowed: bool
    reason: str = "allowed"
    visible_schema: DatabaseSchema | None = None
    violations: list[str] = Field(default_factory=list)


class SQLParameter(BaseModel):
    name: str
    value: str | int | float | bool | None


class SQLOutput(BaseModel):
    dialect: QueryDialect = QueryDialect.SQL
    query: str
    parameters: list[SQLParameter] = Field(default_factory=list)
    referenced_tables: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    rationale: str = "deterministic local compiler output"

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query cannot be empty")
        return stripped


class BranchSessionPointer(BaseModel):
    git_commit_hash: str
    tidb_branch_id: str
    virtual_env_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionAttempt(BaseModel):
    attempt: int
    query: str
    success: bool
    error: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ExecutionFeedback(BaseModel):
    success: bool
    pointer: BranchSessionPointer
    attempts: list[ExecutionAttempt]
    final_rows: list[dict[str, Any]] = Field(default_factory=list)
    final_error: str | None = None
    branch_torn_down: bool = False


class GroundingCandidate(BaseModel):
    value: str
    score: float


class GroundingResult(BaseModel):
    field: str
    query_fragment: str
    candidates: list[GroundingCandidate]
    best_value: str | None = None


class OrchestrationResult(BaseModel):
    request: QueryRequest
    security: SecurityResult
    schema_context: SchemaContext
    sql: SQLOutput
    execution: ExecutionFeedback
    grounding: list[GroundingResult] = Field(default_factory=list)


class JsonRpcError(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JsonRpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    id: str | int | None = Field(default_factory=lambda: str(uuid4()))


class JsonRpcResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    result: Any | None = None
    error: JsonRpcError | None = None
    id: str | int | None = None


QueryRequest.model_rebuild()
