"""The full FluxBoard project-management schema as a ``DatabaseSchema``.

Derived faithfully from ``app/database/models.py`` (the SQLAlchemy ORM models).
The 6-table ``default_project_schema()`` in ``app/master.py`` is a reduced
demo schema; for the paper we evaluate against the complete 10-table model so
the token-reduction and RBAC numbers reflect a realistic enterprise board.

RBAC annotations follow the same policy the production demo schema uses
(``users.email`` and ``audit_logs`` are admin-only): an end-user with the
``viewer`` role must not see the audit trail, member email addresses, or
invite tokens. These are the columns/tables a leaking text-to-SQL system would
expose.
"""

from __future__ import annotations

from app.schemas.validation import (
    ColumnDefinition,
    DatabaseSchema,
    ForeignKeyDefinition,
    TableDefinition,
)

ADMIN_ONLY = {"admin"}


def col(name: str, data_type: str = "text", *, sensitive: bool = False, admin: bool = False) -> ColumnDefinition:
    return ColumnDefinition(
        name=name,
        data_type=data_type,
        sensitive=sensitive,
        roles_allowed=ADMIN_ONLY if admin else set(),
    )


def full_project_schema() -> DatabaseSchema:
    """Return the complete 10-table FluxBoard schema with RBAC annotations."""
    tables = [
        TableDefinition(
            name="workspaces",
            columns=[
                col("id", "int"),
                col("name", "varchar"),
                col("slug", "varchar"),
                col("created_by", "varchar"),
                col("created_at", "datetime"),
                col("updated_at", "datetime"),
            ],
        ),
        TableDefinition(
            name="projects",
            columns=[
                col("id", "int"),
                col("workspace_id", "int"),
                col("name", "varchar"),
                col("key", "varchar"),
                col("description", "text"),
                col("created_by", "varchar"),
                col("updated_by", "varchar"),
                col("created_at", "datetime"),
                col("updated_at", "datetime"),
            ],
        ),
        TableDefinition(
            name="statuses",
            columns=[
                col("id", "int"),
                col("project_id", "int"),
                col("name", "varchar"),
                col("category", "varchar"),
                col("color", "varchar"),
                col("position", "decimal"),
            ],
        ),
        TableDefinition(
            name="tasks",
            columns=[
                col("id", "int"),
                col("project_id", "int"),
                col("status_id", "int"),
                col("sequence_number", "int"),
                col("task_key", "varchar"),
                col("title", "varchar"),
                col("description", "text"),
                col("priority", "varchar"),
                col("assignee", "varchar"),
                col("due_date", "datetime"),
                col("archived", "boolean"),
                col("position", "decimal"),
                col("created_by", "varchar"),
                col("updated_by", "varchar"),
                col("created_at", "datetime"),
                col("updated_at", "datetime"),
            ],
        ),
        TableDefinition(
            name="labels",
            columns=[
                col("id", "int"),
                col("project_id", "int"),
                col("name", "varchar"),
                col("color", "varchar"),
            ],
        ),
        TableDefinition(
            name="task_labels",
            columns=[
                col("task_id", "int"),
                col("label_id", "int"),
            ],
        ),
        TableDefinition(
            name="comments",
            columns=[
                col("id", "int"),
                col("task_id", "int"),
                col("body", "text"),
                col("created_by", "varchar"),
                col("created_at", "datetime"),
                col("updated_at", "datetime"),
            ],
        ),
        # Audit trail -- admin only (mirrors the demo schema's `audit_logs`).
        TableDefinition(
            name="activity_events",
            roles_allowed=ADMIN_ONLY,
            columns=[
                col("id", "int"),
                col("project_id", "int"),
                col("task_id", "int"),
                col("actor", "varchar"),
                col("event_type", "varchar"),
                col("payload", "text", sensitive=True, admin=True),
                col("created_at", "datetime"),
            ],
        ),
        TableDefinition(
            name="project_members",
            columns=[
                col("id", "int"),
                col("project_id", "int"),
                # Member PII -- admin only.
                col("email", "varchar", sensitive=True, admin=True),
                col("display_name", "varchar"),
                col("role", "varchar"),
                col("created_at", "datetime"),
                col("updated_at", "datetime"),
            ],
        ),
        TableDefinition(
            name="project_invites",
            columns=[
                col("id", "int"),
                col("project_id", "int"),
                # Invite secret -- admin only.
                col("token", "varchar", sensitive=True, admin=True),
                col("role", "varchar"),
                col("expires_at", "datetime"),
                col("created_at", "datetime"),
            ],
        ),
    ]

    foreign_keys = [
        ForeignKeyDefinition(source_table="projects", source_column="workspace_id", target_table="workspaces", target_column="id"),
        ForeignKeyDefinition(source_table="statuses", source_column="project_id", target_table="projects", target_column="id"),
        ForeignKeyDefinition(source_table="tasks", source_column="project_id", target_table="projects", target_column="id"),
        ForeignKeyDefinition(source_table="tasks", source_column="status_id", target_table="statuses", target_column="id"),
        ForeignKeyDefinition(source_table="labels", source_column="project_id", target_table="projects", target_column="id"),
        ForeignKeyDefinition(source_table="task_labels", source_column="task_id", target_table="tasks", target_column="id"),
        ForeignKeyDefinition(source_table="task_labels", source_column="label_id", target_table="labels", target_column="id"),
        ForeignKeyDefinition(source_table="comments", source_column="task_id", target_table="tasks", target_column="id"),
        ForeignKeyDefinition(source_table="activity_events", source_column="project_id", target_table="projects", target_column="id"),
        ForeignKeyDefinition(source_table="activity_events", source_column="task_id", target_table="tasks", target_column="id"),
        ForeignKeyDefinition(source_table="project_members", source_column="project_id", target_table="projects", target_column="id"),
        ForeignKeyDefinition(source_table="project_invites", source_column="project_id", target_table="projects", target_column="id"),
    ]

    return DatabaseSchema(tables=tables, foreign_keys=foreign_keys)


# (table, column) pairs a viewer must never see; column=None means whole table.
VIEWER_SENSITIVE_TARGETS: list[tuple[str, str | None]] = [
    ("activity_events", None),
    ("project_members", "email"),
    ("project_invites", "token"),
]
