from __future__ import annotations

import asyncio
import json

import typer

from app.master import MasterOrchestrator
from app.schemas.validation import QueryDialect, QueryRequest

cli = typer.Typer(help="CPV adaptive schema multi-agent backend CLI.")
ROLE_OPTION = typer.Option(["viewer"], "--role", "-r")


@cli.command()
def query(
    question: str,
    user_id: str = "local-user",
    role: list[str] = ROLE_OPTION,
    project: str | None = None,
    dialect: QueryDialect = QueryDialect.SQL,
) -> None:
    """Run a local mock orchestration request."""

    request = QueryRequest(
        question=question,
        user_id=user_id,
        roles=role,
        project=project,
        dialect=dialect,
    )
    result = asyncio.run(MasterOrchestrator().run(request))
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


@cli.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the FastAPI app with uvicorn."""

    import uvicorn

    uvicorn.run("app.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
