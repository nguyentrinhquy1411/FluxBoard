from __future__ import annotations

import typer
from sqlalchemy import inspect, text

from app.config import get_settings
from app.database.models import Base
from app.database.session import ensure_database_exists, get_engine

cli = typer.Typer(help="Database migration utilities.")


@cli.command()
def upgrade() -> None:
    """Create the CPV app database and tables if they do not exist."""

    settings = get_settings()
    ensure_database_exists(settings)
    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_task_key_columns(engine)
    ensure_invite_and_member_columns(engine)
    typer.echo(f"Database schema is ready for {settings.app_db_name}.")


def ensure_invite_and_member_columns(engine) -> None:
    """Add columns that were introduced after initial deployment."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    # Add display_name to project_members if missing
    if "project_members" in table_names:
        col_names = {c["name"] for c in inspector.get_columns("project_members")}
        with engine.begin() as conn:
            if "display_name" not in col_names:
                conn.execute(
                    text("ALTER TABLE project_members ADD COLUMN display_name VARCHAR(160) NULL")
                )

    # Ensure project_invites table exists (create_all handles new tables, but belt-and-suspenders)
    if "project_invites" not in table_names:
        # create_all already ran above, so this is a no-op; kept for clarity
        pass


def ensure_task_key_columns(engine) -> None:
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("tasks")}
    with engine.begin() as connection:
        if "sequence_number" not in column_names:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN sequence_number INT NULL"))
        if "task_key" not in column_names:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN task_key VARCHAR(64) NULL"))

    inspector = inspect(engine)
    index_names = {index["name"] for index in inspector.get_indexes("tasks")}
    unique_names = {constraint["name"] for constraint in inspector.get_unique_constraints("tasks")}
    if "uq_tasks_project_task_key" not in index_names | unique_names:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX uq_tasks_project_task_key ON tasks (project_id, task_key)"
                )
            )

    backfill_task_keys(engine)


def backfill_task_keys(engine) -> None:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT t.id, t.project_id, t.sequence_number, t.task_key, p.`key` AS project_key "
                "FROM tasks t JOIN projects p ON p.id = t.project_id "
                "ORDER BY t.project_id, t.id"
            )
        ).mappings()

        counters: dict[int, int] = {}
        updates: list[dict] = []
        for row in rows:
            project_id = int(row["project_id"])
            current = row["sequence_number"]
            if current is None:
                counters[project_id] = counters.get(project_id, 0) + 1
                sequence = counters[project_id]
            else:
                sequence = int(current)
                counters[project_id] = max(counters.get(project_id, 0), sequence)
            task_key = row["task_key"] or f"{str(row['project_key']).upper()}-{sequence}"
            if row["sequence_number"] != sequence or row["task_key"] != task_key:
                updates.append({"id": row["id"], "sequence_number": sequence, "task_key": task_key})

        for update in updates:
            connection.execute(
                text(
                    "UPDATE tasks SET sequence_number = :sequence_number, task_key = :task_key "
                    "WHERE id = :id"
                ),
                update,
            )


if __name__ == "__main__":
    upgrade()
