"""
Analyst Agent — LangChain-powered analytical query planner and summarizer.

When a user asks an analytical question (aggregations, distributions, comparisons,
trends), this agent:
  1. Plans which SQL to run against the Kanban database
  2. After execution, summarizes the raw rows into structured insights

Uses Groq LLM via langchain-groq with structured Pydantic output.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, SecretStr

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic output models
# ─────────────────────────────────────────────────────────────────────────────


class AnalystSQLPlan(BaseModel):
    """LLM output: the SQL query plan for an analytical question."""

    sql: str = Field(
        description=(
            "A safe, parameterized SELECT query using MySQL/TiDB dialect. "
            "Use :param_name syntax for parameters. Must be SELECT only."
        )
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter values for the SQL statement.",
    )
    explanation: str = Field(
        description="One-sentence explanation of what this query fetches and why.",
    )


class AnalystSummary(BaseModel):
    """LLM output: structured summary of analytical query results."""

    title: str = Field(
        description="A short, descriptive title for the analysis (max 60 chars).",
    )
    key_findings: list[str] = Field(
        description="3-5 bullet-point key findings from the data.",
    )
    insights: str = Field(
        description=(
            "A 2-3 sentence analytical insight connecting the findings "
            "and providing actionable context for project managers."
        ),
    )
    recommendation: str = Field(
        description="One concrete, actionable recommendation based on the analysis.",
    )


class AnalystResult(BaseModel):
    """Complete analyst agent output combining SQL plan, rows, and summary."""

    sql_plan: AnalystSQLPlan
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: AnalystSummary | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Classification output
# ─────────────────────────────────────────────────────────────────────────────


class AnalyticalClassification(BaseModel):
    """LLM output: whether a question is analytical."""

    is_analytical: bool = Field(
        description=(
            "True if the question asks for aggregation, distribution, comparison, "
            "trend analysis, workload analysis, statistics, counts across categories, "
            "or any insight that requires GROUP BY / COUNT / SUM / AVG queries. "
            "False for simple task lookups, mutations, detail views, or board summaries."
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────


class AnalystAgent:
    """
    LangChain-powered analyst agent for Kanban project analytics.

    Two-step chain:
      Step 1 (Plan):      question + schema → SQL plan
      Step 2 (Summarize): question + raw rows → structured insights
    """

    def __init__(self, api_key: str, model_name: str) -> None:
        self._api_key = api_key
        self._model_name = model_name

    def _llm(self, temperature: float = 0):
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=SecretStr(self._api_key),
            model=self._model_name,
            temperature=temperature,
        )

    # ── Step 0: Classify ──────────────────────────────────────────────────────

    def classify(self, question: str) -> bool:
        """Return True if the question is analytical and should be routed here."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            model = self._llm(temperature=0).with_structured_output(AnalyticalClassification)

            sys_msg = (
                "You are a question classifier for a Kanban project management system.\n"
                "Classify whether the user's question is ANALYTICAL — meaning it requires "
                "aggregation, counting, grouping, distribution analysis, trend analysis, "
                "workload comparison, or statistical insights across multiple tasks.\n\n"
                "Examples of ANALYTICAL questions:\n"
                '- "How many tasks per status column?"\n'
                '- "What is the priority distribution?"\n'
                '- "Who has the most tasks assigned?"\n'
                '- "Show workload breakdown by assignee"\n'
                '- "Compare task counts across statuses"\n'
                '- "What percentage of tasks are critical?"\n\n'
                "Examples of NON-analytical questions (return False):\n"
                '- "Show task CPV-5" (detail lookup)\n'
                '- "Create a new task" (mutation)\n'
                '- "Move CPV-3 to Done" (mutation)\n'
                '- "Archive all tasks" (mutation)\n'
                '- "Summarize this board" (simple board summary)\n'
                '- "What is the weather?" (off-topic)\n'
            )

            result = model.invoke(
                [
                    SystemMessage(content=sys_msg),
                    HumanMessage(content=question),
                ]
            )

            if isinstance(result, AnalyticalClassification):
                return result.is_analytical
        except Exception:
            import sys
            import traceback

            print("AnalystAgent.classify failed:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return False

    # ── Step 1: Plan SQL ──────────────────────────────────────────────────────

    def plan_sql(self, question: str, schema_ddl: str, project_id: int) -> AnalystSQLPlan | None:
        """Use LLM to plan the optimal SQL query for the analytical question."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            model = self._llm(temperature=0).with_structured_output(AnalystSQLPlan)

            sys_msg = (
                "You are an analytical SQL planner for a Kanban project management database.\n"
                "Given the user's analytical question and the database schema, produce a SQL "
                "SELECT query that answers the question with appropriate aggregations.\n\n"
                "RULES:\n"
                "1. Only SELECT statements. No INSERT, UPDATE, DELETE, DROP, etc.\n"
                "2. Use MySQL/TiDB dialect. No PostgreSQL syntax.\n"
                "3. Use :param_name for user-supplied values.\n"
                "4. Always filter by project_id = :project_id for the current project.\n"
                "5. Filter out archived tasks (archived = 0) unless the question "
                "is about archives.\n"
                "6. Use GROUP BY, COUNT, SUM, AVG, etc. for analytical aggregations.\n"
                "7. Join with statuses table if grouping by status name.\n"
                "8. LIMIT results to 100 rows maximum.\n\n"
                f"Database Schema:\n{schema_ddl}\n"
            )

            human_msg = f"Question: {question}\nCurrent project_id: {project_id}"

            result = model.invoke(
                [
                    SystemMessage(content=sys_msg),
                    HumanMessage(content=human_msg),
                ]
            )

            if isinstance(result, AnalystSQLPlan):
                # Always inject project_id param
                result.params["project_id"] = project_id
                return result
        except Exception:
            import sys
            import traceback

            print("AnalystAgent.plan_sql failed:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return None

    # ── Step 2: Summarize ─────────────────────────────────────────────────────

    def analyze(
        self,
        project_id: int,
        question: str,
        schema_ddl: str,
        settings: Any | None = None,
        rows: list[dict[str, Any]] | None = None,
    ) -> AnalystResult | None:
        """
        Plan analytical SQL and, when rows are supplied by the caller, summarize them.

        SQL execution intentionally remains outside the agent so the service can run
        the existing read-only validation/execution path before summarization.
        """
        sql_plan = self.plan_sql(question, schema_ddl, project_id)
        if not sql_plan:
            return None

        result = AnalystResult(sql_plan=sql_plan, rows=rows or [])
        if rows is not None:
            result.summary = self.summarize(question, rows)
        return result

    def summarize(
        self, question: str, rows: list[dict[str, Any]]
    ) -> AnalystSummary | None:
        """Summarize raw SQL result rows into structured analytical insights."""
        if not rows:
            return AnalystSummary(
                title="No Data Found",
                key_findings=["The query returned no results for this project."],
                insights=(
                    "There may be no tasks matching the criteria, or the project may be empty."
                ),
                recommendation=(
                    "Try broadening the question or check if the project has active tasks."
                ),
            )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            model = self._llm(temperature=0.3).with_structured_output(AnalystSummary)

            # Truncate rows for context window
            display_rows = rows[:50]
            rows_text = "\n".join(str(r) for r in display_rows)
            if len(rows) > 50:
                rows_text += f"\n... and {len(rows) - 50} more rows"

            sys_msg = (
                "You are a project analytics expert. Given raw query results from a "
                "Kanban project management database, produce a structured analytical "
                "summary.\n\n"
                "Guidelines:\n"
                "- Title should be concise and descriptive (max 60 chars)\n"
                "- Key findings should be 3-5 specific, data-backed bullet points\n"
                "- Include actual numbers and percentages where possible\n"
                "- Insights should connect the findings to actionable project context\n"
                "- Recommendation should be one concrete, actionable step\n"
                "- Write in a professional but approachable tone\n"
            )

            human_msg = (
                f"Original question: {question}\n"
                f"Total rows returned: {len(rows)}\n\n"
                f"Data:\n{rows_text}"
            )

            result = model.invoke(
                [
                    SystemMessage(content=sys_msg),
                    HumanMessage(content=human_msg),
                ]
            )

            if isinstance(result, AnalystSummary):
                return result
        except Exception:
            import sys
            import traceback

            print("AnalystAgent.summarize failed:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return None
