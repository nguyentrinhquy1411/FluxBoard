"""Scalability study (offline, deterministic): how schema-pruning token
reduction and pruning latency behave as the schema grows from 10 to 300 tables.

This addresses the reviewer concern that token reduction is only demonstrated on
a single small schema. We synthesise connected star-style schemas of increasing
size, prune them for a fixed question workload, and measure the true sub-word
token reduction of the rendered DDL and the wall-clock pruning latency.

The synthetic schemas are intentionally simple (a central fact table joined to N
dimension tables); we report them as a controlled scalability probe, not as real
enterprise schemas.
"""

from __future__ import annotations

import csv
import statistics
import time
from pathlib import Path

from app.schemas.validation import (
    ColumnDefinition,
    DatabaseSchema,
    ForeignKeyDefinition,
    TableDefinition,
)
from app.sub_agents.schema_pruner import SchemaPruner

from eval.tokens import TokenCount, render_ddl

# A pool of business-flavoured nouns so synthetic tables get distinct,
# matchable names (the pruner keys on table/column tokens).
_NOUNS = [
    "invoice", "payment", "customer", "vendor", "contract", "ticket", "incident",
    "release", "sprint", "epic", "milestone", "attachment", "reminder", "webhook",
    "integration", "dashboard", "report", "automation", "checklist", "template",
    "category", "tag", "priority", "severity", "team", "department", "role",
    "permission", "notification", "subscription", "asset", "device", "location",
    "shipment", "order", "product", "discount", "campaign", "lead", "opportunity",
]


def _table_name(i: int) -> str:
    """Distinct, single-token entity name (realistic schema: no shared stems)."""
    return f"{_NOUNS[i % len(_NOUNS)]}{i}"


def synth_schema(n_tables: int) -> DatabaseSchema:
    """Central `tasks` fact table joined to ``n_tables-1`` dimension tables.

    Dimension tables get distinct single-token names and generic, short column
    names (all < 6 chars, so they do not trigger the pruner's column-token layer)
    -- modelling a realistic schema where each table is a distinct entity rather
    than many tables sharing a naming stem.
    """
    tables = [
        TableDefinition(
            name="tasks",
            columns=[
                ColumnDefinition(name="id", data_type="int"),
                ColumnDefinition(name="title", data_type="varchar"),
                ColumnDefinition(name="priority", data_type="varchar"),
                ColumnDefinition(name="created_at", data_type="datetime"),
            ],
        )
    ]
    fks: list[ForeignKeyDefinition] = []
    for i in range(n_tables - 1):
        name = _table_name(i)
        tables.append(
            TableDefinition(
                name=name,
                columns=[
                    ColumnDefinition(name="id", data_type="int"),
                    ColumnDefinition(name="task_id", data_type="int"),
                    ColumnDefinition(name="label", data_type="varchar"),
                    ColumnDefinition(name="state", data_type="varchar"),
                    ColumnDefinition(name="val", data_type="decimal"),
                    ColumnDefinition(name="ts", data_type="datetime"),
                ],
            )
        )
        fks.append(
            ForeignKeyDefinition(
                source_table=name, source_column="task_id",
                target_table="tasks", target_column="id",
            )
        )
    return DatabaseSchema(tables=tables, foreign_keys=fks)


def _questions(schema: DatabaseSchema) -> list[str]:
    """Questions that reference dimension tables by their exact (distinct) name."""
    dims = [t.name for t in schema.tables if t.name != "tasks"]
    qs = ["show all high priority tasks"]
    if dims:
        qs.append(f"list tasks joined with {dims[0]}")
    if len(dims) > 1:
        qs.append(f"count {dims[1]} per task")
    return qs


def run(sizes: list[int] | None = None) -> list[dict]:
    sizes = sizes or [10, 25, 50, 100, 200, 300]
    rows: list[dict] = []
    for n in sizes:
        schema = synth_schema(n)
        full_tok = (TokenCount.of(render_ddl(schema, None)).bpe or 0)
        reductions: list[float] = []
        latencies: list[float] = []
        for q in _questions(schema):
            pruner = SchemaPruner()  # fresh cache per measurement
            t0 = time.perf_counter()
            ctx = pruner.prune(q, schema)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            pruned_tok = TokenCount.of(render_ddl(schema, set(ctx.selected_tables))).bpe or 0
            reductions.append(1.0 - pruned_tok / full_tok if full_tok else 0.0)
        rows.append(
            {
                "n_tables": n,
                "full_ddl_tokens": full_tok,
                "mean_token_reduction": round(statistics.mean(reductions), 4),
                "mean_prune_latency_ms": round(statistics.mean(latencies), 4),
            }
        )
    return rows


def main() -> None:
    print("Scale study: token reduction & pruning latency vs schema size")
    rows = run()
    print(f"{'tables':>7} {'full_tok':>9} {'reduction':>10} {'prune_ms':>9}")
    for r in rows:
        print(f"{r['n_tables']:>7} {r['full_ddl_tokens']:>9} "
              f"{r['mean_token_reduction']*100:>9.1f}% {r['mean_prune_latency_ms']:>9.3f}")

    results = Path(__file__).parent / "results"
    results.mkdir(exist_ok=True)
    fields = ["n_tables", "full_ddl_tokens", "mean_token_reduction", "mean_prune_latency_ms"]
    with open(results / "exp6_scale.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV: {results / 'exp6_scale.csv'}")


if __name__ == "__main__":
    main()
