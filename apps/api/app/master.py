from __future__ import annotations

from app.config import Settings, get_settings
from app.database.connection import BranchExecutor, make_branch_executor
from app.schemas.validation import (
    ColumnDefinition,
    DatabaseSchema,
    ForeignKeyDefinition,
    OrchestrationResult,
    QueryRequest,
    SchemaContext,
    SQLOutput,
    SQLParameter,
    TableDefinition,
)
from app.sub_agents.jira_anchor import JiraAnchor
from app.sub_agents.schema_pruner import InProcessTTLCache, SchemaPruner
from app.sub_agents.security_veto import SecurityVetoAgent
from app.sub_agents.tidb_branch import SpeculativeBranchAgent


class MasterOrchestrator:
    def __init__(
        self,
        settings: Settings | None = None,
        branch_executor: BranchExecutor | None = None,
        schema_pruner: SchemaPruner | None = None,
        jira_anchor: JiraAnchor | None = None,
        security_agent: SecurityVetoAgent | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        cache = InProcessTTLCache(default_ttl_seconds=self.settings.cache_ttl_seconds)
        self.schema_pruner = schema_pruner or SchemaPruner(cache=cache)
        self.security_agent = security_agent or SecurityVetoAgent()
        self.jira_anchor = jira_anchor or JiraAnchor(cache=cache)
        self.branch_agent = SpeculativeBranchAgent(
            executor=branch_executor or make_branch_executor(self.settings),
            settings=self.settings,
        )

    async def run(self, request: QueryRequest) -> OrchestrationResult:
        source_schema = request.database_schema or default_project_schema()
        schema_security = self.security_agent.derive_visible_schema(source_schema, request.roles)
        visible_schema = schema_security.visible_schema or DatabaseSchema(tables=[])
        schema_context = self.schema_pruner.prune(request.question, visible_schema)
        sql = self._compile_sql(request, schema_context)
        self.security_agent.validate_sql(sql)
        execution = await self.branch_agent.execute_with_feedback(sql)
        grounding = []
        if "component" in request.question.lower():
            grounding.append(
                await self.jira_anchor.ground(
                    field="component",
                    query_fragment=request.question,
                    candidates=["backend", "frontend", "mobile", "billing"],
                )
            )
        return OrchestrationResult(
            request=request,
            security=schema_security,
            schema_context=schema_context,
            sql=sql,
            execution=execution,
            grounding=grounding,
        )

    def _compile_sql(self, request: QueryRequest, context: SchemaContext) -> SQLOutput:
        sql_model = _build_sql_model(self.settings)
        if sql_model is not None and not self.settings.mock_mode:
            try:
                from langchain_core.messages import HumanMessage, SystemMessage

                visible_schema = request.database_schema or default_project_schema()
                selected = set(context.selected_tables or [])

                compact_ddl_lines: list[str] = []
                for table in visible_schema.tables:
                    if table.name not in selected:
                        continue
                    cols = ", ".join(f"{c.name} {c.data_type}" for c in table.columns)
                    compact_ddl_lines.append(f"  {table.name}({cols})")
                compact_ddl = "\n".join(compact_ddl_lines) or "(all tables)"

                fk_hints = "; ".join(
                    f"{fk.source_table}.{fk.source_column} → {fk.target_table}.{fk.target_column}"
                    for fk in visible_schema.foreign_keys
                    if fk.source_table in selected or fk.target_table in selected
                )

                model = sql_model

                sys_prompt = (
                    "You are a Text-to-SQL assistant. Translate the user question "
                    "into a safe, parameterized SQL SELECT query using MySQL/TiDB "
                    "dialect.\n"
                    "RULES:\n"
                    "1. Only SELECT statements are allowed. Do not use PostgreSQL "
                    "specific syntax like FILTER (WHERE ...) or ::float casting. "
                    "Use MySQL syntax (e.g. SUM(CASE WHEN ... THEN 1 ELSE 0 END) "
                    "or COUNT(CASE WHEN ... THEN 1 END)).\n"
                    "2. Use :param_name for all user-supplied values. List them in parameters.\n"
                    "3. If a project key or project filter is specified, query it "
                    "using the correct column name from the provided schema "
                    "(e.g. p.key = :project_key or t.project_id = :project_id).\n"
                    "4. If you cannot construct a valid SQL query or if the "
                    'columns/tables needed are missing, you MUST still call the tool. '
                    'Set query = "" and explain why in the rationale field. '
                    "DO NOT return plain text.\n"
                    f"Available schema:\n{compact_ddl}\n\n"
                    f"Foreign keys: {fk_hints}\n"
                )

                human_msg = f"Question: {request.question}\nProject context: {request.project}"
                sql_out = model.invoke(
                    [
                        SystemMessage(content=sys_prompt),
                        HumanMessage(content=human_msg),
                    ]
                )

                if isinstance(sql_out, SQLOutput):
                    if not sql_out.referenced_tables:
                        sql_out.referenced_tables = list(selected)
                    sql_out.rationale = "Dynamic LLM compiler output"
                    return sql_out
            except Exception as e:
                import sys
                import traceback

                print(f"LLM SQL compilation failed: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

        selected_tables = list(context.selected_tables or ["tasks"])
        primary_table = "tasks" if "tasks" in selected_tables else selected_tables[0]

        clauses: list[str] = []
        parameters: list[SQLParameter] = []
        question = request.question.lower()

        if primary_table == "tasks":
            # Build SQL query with joins to match physical schema
            query = "SELECT t.* FROM tasks t"
            joins = []

            # Check if we need statuses table
            if "completed" in question or "done" in question or "statuses" in selected_tables:
                joins.append("JOIN statuses s ON t.status_id = s.id")
                if "statuses" not in selected_tables:
                    selected_tables.append("statuses")
                if "completed" in question or "done" in question:
                    clauses.append("(s.category = :status_category OR s.name = :status_name)")
                    parameters.append(SQLParameter(name="status_category", value="done"))
                    parameters.append(SQLParameter(name="status_name", value="Done"))

            # Check if we need projects table
            if request.project or "projects" in selected_tables:
                joins.append("JOIN projects p ON t.project_id = p.id")
                if "projects" not in selected_tables:
                    selected_tables.append("projects")
                if request.project:
                    clauses.append("p.key = :project_key")
                    parameters.append(
                        SQLParameter(name="project_key", value=request.project.upper())
                    )

            if joins:
                query = f"SELECT t.* FROM tasks t {' '.join(joins)}"
            else:
                query = "SELECT * FROM tasks"
        else:
            query = f"SELECT * FROM {primary_table}"
            if request.project and primary_table == "projects":
                clauses.append("key = :project_key")
                parameters.append(SQLParameter(name="project_key", value=request.project.upper()))

        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"{query}{where_clause} LIMIT 100"

        return SQLOutput(
            query=query,
            parameters=parameters,
            referenced_tables=sorted(list(set(selected_tables))),
            confidence=0.78,
            rationale="deterministic physical query compiler",
        )


def _build_sql_model(settings: Settings):
    """Return a structured-output chat model for SQL compilation, or ``None``.

    Provider-agnostic: selects Groq or a local Ollama model based on
    ``settings.llm_provider``. Returns ``None`` in mock mode or when no provider
    is configured, so the caller falls back to the deterministic compiler.
    """
    if settings.mock_mode:
        return None
    provider = (settings.llm_provider or "groq").lower()
    try:
        if provider == "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0,
            ).with_structured_output(SQLOutput)
        if settings.groq_api_key:
            from langchain_groq import ChatGroq

            return ChatGroq(
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                temperature=0,
            ).with_structured_output(SQLOutput)
    except Exception as exc:
        # Don't fail silently: a provider/import error here makes the caller
        # fall back to the limited deterministic compiler, which would
        # otherwise look like a correct (but degraded) answer.
        import sys

        print(f"SQL model init failed (provider={provider}): {exc}", file=sys.stderr)
        return None
    return None


def default_project_schema() -> DatabaseSchema:
    return DatabaseSchema(
        tables=[
            TableDefinition(
                name="projects",
                columns=[
                    ColumnDefinition(name="id", data_type="int"),
                    ColumnDefinition(name="project_key"),
                    ColumnDefinition(name="name"),
                    ColumnDefinition(name="business_unit"),
                ],
            ),
            TableDefinition(
                name="tasks",
                columns=[
                    ColumnDefinition(name="id", data_type="int"),
                    ColumnDefinition(name="project_id", data_type="int"),
                    ColumnDefinition(name="project_key"),
                    ColumnDefinition(name="summary"),
                    ColumnDefinition(name="description"),
                    ColumnDefinition(name="status"),
                    ColumnDefinition(name="priority"),
                    ColumnDefinition(name="assignee_id", data_type="int"),
                    ColumnDefinition(name="created_at", data_type="datetime"),
                ],
            ),
            TableDefinition(
                name="users",
                columns=[
                    ColumnDefinition(name="id", data_type="int"),
                    ColumnDefinition(name="display_name"),
                    ColumnDefinition(name="email", sensitive=True, roles_allowed={"admin"}),
                ],
            ),
            TableDefinition(
                name="task_labels",
                columns=[
                    ColumnDefinition(name="task_id", data_type="int"),
                    ColumnDefinition(name="label_id", data_type="int"),
                ],
            ),
            TableDefinition(
                name="labels",
                columns=[
                    ColumnDefinition(name="id", data_type="int"),
                    ColumnDefinition(name="name"),
                ],
            ),
            TableDefinition(
                name="audit_logs",
                roles_allowed={"admin"},
                columns=[
                    ColumnDefinition(name="id", data_type="int"),
                    ColumnDefinition(name="actor_id", data_type="int"),
                    ColumnDefinition(name="payload", sensitive=True, roles_allowed={"admin"}),
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
                source_column="assignee_id",
                target_table="users",
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
        ],
    )
