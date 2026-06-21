from app.master import default_project_schema
from app.schemas.validation import (
    ColumnDefinition,
    DatabaseSchema,
    ForeignKeyDefinition,
    TableDefinition,
)
from app.sub_agents.schema_pruner import SchemaPruner


def test_physical_table_matching_handles_singular_plural() -> None:
    context = SchemaPruner().prune("show every task", default_project_schema())

    assert "tasks" in context.selected_tables
    assert context.entity_matches["physical"] == ["tasks"]


def test_business_entity_mapping_selects_tables() -> None:
    context = SchemaPruner().prune("completed tasks by project", default_project_schema())

    assert "tasks" in context.selected_tables
    assert "tasks" in context.entity_matches["business"]


def test_column_matching_ignores_common_short_terms() -> None:
    schema = DatabaseSchema(
        tables=[
            TableDefinition(
                name="tasks",
                columns=[
                    ColumnDefinition(name="status"),
                    ColumnDefinition(name="deployment_target"),
                ],
            ),
            TableDefinition(
                name="releases",
                columns=[ColumnDefinition(name="status")],
            ),
        ]
    )

    context = SchemaPruner().prune("deployment target status", schema)

    assert context.entity_matches["columns"] == ["tasks"]


def test_bfs_includes_intermediary_join_table() -> None:
    schema = DatabaseSchema(
        tables=[
            TableDefinition(name="tasks", columns=[ColumnDefinition(name="id")]),
            TableDefinition(name="task_labels", columns=[ColumnDefinition(name="task_id")]),
            TableDefinition(name="labels", columns=[ColumnDefinition(name="id")]),
        ],
        foreign_keys=[
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

    context = SchemaPruner().prune("tasks with labels", schema)

    assert context.selected_tables == ["labels", "task_labels", "tasks"]
    assert ["labels", "task_labels", "tasks"] in context.join_paths or [
        "tasks",
        "task_labels",
        "labels",
    ] in context.join_paths
