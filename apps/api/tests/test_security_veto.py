import pytest

from app.master import default_project_schema
from app.schemas.validation import SecurityViolation, SQLOutput, SQLParameter
from app.sub_agents.security_veto import SecurityVetoAgent


def test_accepts_parameterized_select() -> None:
    result = SecurityVetoAgent().validate_sql(
        SQLOutput(
            query="SELECT * FROM tasks WHERE status = :status",
            parameters=[SQLParameter(name="status", value="completed")],
        )
    )

    assert result.allowed is True


@pytest.mark.parametrize(
    "query",
    ["DELETE FROM tasks", "UPDATE tasks SET status = 'done'", "DROP TABLE tasks"],
)
def test_rejects_mutation_commands(query: str) -> None:
    with pytest.raises(SecurityViolation):
        SecurityVetoAgent().validate_sql(SQLOutput(query=query))


def test_rejects_literal_without_parameters() -> None:
    with pytest.raises(SecurityViolation):
        SecurityVetoAgent().validate_sql(
            SQLOutput(query="SELECT * FROM tasks WHERE status = 'done'")
        )


def test_prunes_restricted_schema_by_role() -> None:
    result = SecurityVetoAgent().derive_visible_schema(default_project_schema(), roles=["viewer"])

    table_names = {table.name for table in result.visible_schema.tables}
    users = result.visible_schema.get_table("users")
    assert "audit_logs" not in table_names
    assert users is not None
    assert "email" not in {column.name for column in users.columns}
