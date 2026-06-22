"""Run all paper experiments and emit result tables (CSV + Markdown).

    python -m eval.run_experiments            # from apps/api/

Everything runs offline in mock mode: deterministic and reproducible.
Results are written to ``eval/results/``.
"""

from __future__ import annotations

import asyncio
import csv
import statistics
import time
from collections.abc import Iterator
from pathlib import Path

from app.config import Settings
from app.database.models import Base
from app.database.session import get_db
from app.master import MasterOrchestrator
from app.schemas.validation import (
    QueryRequest,
    SecurityViolation,
    SQLOutput,
    SQLParameter,
)
from app.sub_agents.schema_pruner import SchemaPruner
from app.sub_agents.security_veto import SecurityVetoAgent

from eval.datasets import (
    ATTACK_SUITE,
    DESTRUCTIVE,
    INJECTION,
    QUERY_WORKLOAD,
    RBAC_PII,
)
from eval.schema_full import VIEWER_SENSITIVE_TARGETS, full_project_schema
from eval.tokens import TokenCount, render_ddl

RESULTS = Path(__file__).parent / "results"
RESULTS.mkdir(exist_ok=True)


def _write_csv(name: str, rows: list[dict], fields: list[str]) -> None:
    with open(RESULTS / name, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def offline_settings() -> Settings:
    """Mock-mode settings with no Groq key and no live TiDB (deterministic)."""
    return Settings(mock_mode=True, groq_api_key=None, tidb_url=None)


# --------------------------------------------------------------------------- #
# Experiment 1: Security veto attack suite                                     #
# --------------------------------------------------------------------------- #
def exp1_attack_suite() -> dict:
    agent = SecurityVetoAgent()
    schema = full_project_schema()
    viewer_visible = agent.derive_visible_schema(schema, roles=["viewer"]).visible_schema

    rows: list[dict] = []
    for atk in ATTACK_SUITE:
        # Naive baseline: no veto agent, full schema -> attack succeeds.
        naive_blocked = False
        defended_blocked = False

        if atk.attack_class in (DESTRUCTIVE, INJECTION):
            params = [SQLParameter(name="p", value="x")] if atk.has_parameters else []
            try:
                agent.validate_sql(SQLOutput(query=atk.payload_sql, parameters=params))
            except SecurityViolation:
                defended_blocked = True
        elif atk.attack_class == RBAC_PII:
            table, column = atk.target  # type: ignore[misc]
            vt = viewer_visible.get_table(table)
            if vt is None:
                defended_blocked = True  # whole table hidden
            elif column is not None and column not in {c.name for c in vt.columns}:
                defended_blocked = True  # sensitive column hidden

        rows.append(
            {
                "aid": atk.aid,
                "attack_class": atk.attack_class,
                "prompt": atk.prompt,
                "naive_blocked": naive_blocked,
                "defended_blocked": defended_blocked,
            }
        )

    _write_csv("exp1_attack_suite.csv", rows, list(rows[0].keys()))

    summary = {}
    for cls in (DESTRUCTIVE, INJECTION, RBAC_PII):
        cls_rows = [r for r in rows if r["attack_class"] == cls]
        summary[cls] = {
            "n": len(cls_rows),
            "naive_block_rate": sum(r["naive_blocked"] for r in cls_rows) / len(cls_rows),
            "defended_block_rate": sum(r["defended_blocked"] for r in cls_rows) / len(cls_rows),
        }
    summary["overall"] = {
        "n": len(rows),
        "naive_block_rate": sum(r["naive_blocked"] for r in rows) / len(rows),
        "defended_block_rate": sum(r["defended_blocked"] for r in rows) / len(rows),
    }
    return summary


# --------------------------------------------------------------------------- #
# Experiment 2: RBAC schema-redaction correctness                              #
# --------------------------------------------------------------------------- #
def _hidden_units(full, visible) -> set[tuple[str, str | None]]:
    """(table, col) units present in `full` but absent from `visible`."""
    hidden: set[tuple[str, str | None]] = set()
    visible_tables = {t.name: t for t in visible.tables}
    for table in full.tables:
        if table.name not in visible_tables:
            hidden.add((table.name, None))
            continue
        vcols = {c.name for c in visible_tables[table.name].columns}
        for c in table.columns:
            if c.name not in vcols:
                hidden.add((table.name, c.name))
    return hidden


def exp2_rbac_redaction() -> dict:
    agent = SecurityVetoAgent()
    schema = full_project_schema()
    gold = set(VIEWER_SENSITIVE_TARGETS)

    viewer = agent.derive_visible_schema(schema, roles=["viewer"]).visible_schema
    admin = agent.derive_visible_schema(schema, roles=["admin"]).visible_schema

    viewer_hidden = _hidden_units(schema, viewer)
    admin_hidden = _hidden_units(schema, admin)

    tp = len(viewer_hidden & gold)
    fp = len(viewer_hidden - gold)  # over-redaction
    fn = len(gold - viewer_hidden)  # leaks

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0

    rows = [
        {"role": "viewer", "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall},
        {"role": "admin", "tp": "-", "fp": len(admin_hidden), "fn": "-", "precision": "-", "recall": "-"},
    ]
    _write_csv("exp2_rbac_redaction.csv", rows, list(rows[0].keys()))
    return {
        "viewer_precision": precision,
        "viewer_recall": recall,
        "viewer_leaks": fn,
        "viewer_over_redaction": fp,
        "admin_items_hidden": len(admin_hidden),
        "gold_sensitive_units": len(gold),
    }


# --------------------------------------------------------------------------- #
# Experiment 3: Schema-pruning token reduction + recall                        #
# --------------------------------------------------------------------------- #
def exp3_token_reduction() -> dict:
    schema = full_project_schema()
    pruner = SchemaPruner()
    full_ddl = render_ddl(schema, tables=None)
    full_tok = TokenCount.of(full_ddl)

    rows: list[dict] = []
    bpe_reductions: list[float] = []
    recalls: list[float] = []
    for case in QUERY_WORKLOAD:
        selected = set(pruner.prune(case.question, schema).selected_tables)
        pruned_ddl = render_ddl(schema, tables=selected)
        pruned_tok = TokenCount.of(pruned_ddl)

        full_b = full_tok.bpe or full_tok.whitespace
        pruned_b = pruned_tok.bpe or pruned_tok.whitespace
        red = 1.0 - (pruned_b / full_b) if full_b else 0.0
        recall = 1.0 if case.gold_tables <= selected else len(case.gold_tables & selected) / len(case.gold_tables)
        bpe_reductions.append(red)
        recalls.append(recall)

        rows.append(
            {
                "qid": case.qid,
                "question": case.question,
                "selected_tables": "|".join(sorted(selected)),
                "n_selected": len(selected),
                "full_tokens": full_b,
                "pruned_tokens": pruned_b,
                "token_reduction": round(red, 4),
                "table_recall": round(recall, 4),
            }
        )

    _write_csv("exp3_token_reduction.csv", rows, list(rows[0].keys()))
    return {
        "n_queries": len(rows),
        "n_tables_full": len(schema.tables),
        "full_ddl_tokens": full_tok.bpe or full_tok.whitespace,
        "tokenizer": "cl100k_base" if full_tok.bpe is not None else "whitespace",
        "mean_token_reduction": statistics.mean(bpe_reductions),
        "median_token_reduction": statistics.median(bpe_reductions),
        "mean_table_recall": statistics.mean(recalls),
        "perfect_recall_rate": sum(1 for r in recalls if r == 1.0) / len(recalls),
    }


# --------------------------------------------------------------------------- #
# Experiment 4: Orchestration latency (cache cold vs warm)                     #
# --------------------------------------------------------------------------- #
async def _time_run(orch: MasterOrchestrator, question: str) -> float:
    req = QueryRequest(question=question, roles=["admin"], schema=full_project_schema())
    start = time.perf_counter()
    await orch.run(req)
    return (time.perf_counter() - start) * 1000.0  # ms


async def exp4_latency(repetitions: int = 5) -> dict:
    settings = offline_settings()
    cold: list[float] = []
    warm: list[float] = []
    rows: list[dict] = []

    for _ in range(repetitions):
        for case in QUERY_WORKLOAD:
            orch = MasterOrchestrator(settings=settings)  # fresh -> empty cache
            t_cold = await _time_run(orch, case.question)
            t_warm = await _time_run(orch, case.question)  # same instance -> cache hit
            cold.append(t_cold)
            warm.append(t_warm)
            rows.append({"qid": case.qid, "cold_ms": round(t_cold, 4), "warm_ms": round(t_warm, 4)})

    _write_csv("exp4_latency.csv", rows, list(rows[0].keys()))
    return {
        "samples": len(cold),
        "cold_p50_ms": round(_pct(cold, 0.50), 3),
        "cold_p95_ms": round(_pct(cold, 0.95), 3),
        "cold_mean_ms": round(statistics.mean(cold), 3),
        "warm_p50_ms": round(_pct(warm, 0.50), 3),
        "warm_p95_ms": round(_pct(warm, 0.95), 3),
        "warm_mean_ms": round(statistics.mean(warm), 3),
    }


# --------------------------------------------------------------------------- #
# Experiment 5: ORM-only mutation safety                                       #
# --------------------------------------------------------------------------- #
def exp5_mutation_safety() -> dict:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.api import app
    from app.database import models as dbmodels

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    admin = {"X-User-Email": "admin@corp.com"}

    checks: dict[str, bool] = {}
    try:
        pid = client.post("/api/projects", json={"name": "Eval", "key": "EVAL"}, headers=admin).json()["id"]
        board = client.get(f"/api/projects/{pid}/board", headers=admin).json()
        backlog = board["columns"][0]["status"]["id"]
        done = board["columns"][-1]["status"]["id"]

        # 5a/5d: valid create -> 201 and an audit event is written.
        r_create = client.post(
            f"/api/projects/{pid}/tasks",
            json={"title": "real task", "status_id": backlog, "priority": "high"},
            headers=admin,
        )
        checks["valid_create_201"] = r_create.status_code == 201
        task_id = r_create.json().get("id")

        # 5c: invalid status_id is rejected (status-in-project validation).
        r_bad = client.post(
            f"/api/projects/{pid}/tasks",
            json={"title": "bad", "status_id": 999_999, "priority": "low"},
            headers=admin,
        )
        checks["invalid_status_rejected"] = r_bad.status_code == 404

        # move + archive also audited
        client.post(f"/api/tasks/{task_id}/move", json={"status_id": done}, headers=admin)
        client.post(f"/api/tasks/{task_id}/archive", headers=admin)

        with Session(engine) as s:
            n_events = s.scalar(select(func.count()).select_from(dbmodels.ActivityEvent))
            n_tasks = s.scalar(select(func.count()).select_from(dbmodels.Task))
        checks["audit_events_written"] = (n_events or 0) >= 3  # created + moved + archived
        checks["only_valid_task_persisted"] = n_tasks == 1  # the bad one rolled back

        # 5b: viewer is blocked from mutating (RBAC gate, require_admin).
        client.post(
            f"/api/projects/{pid}/members",
            json={"email": "viewer@corp.com", "role": "viewer"},
            headers=admin,
        )
        r_viewer = client.post(
            f"/api/projects/{pid}/tasks",
            json={"title": "sneaky", "status_id": backlog, "priority": "low"},
            headers={"X-User-Email": "viewer@corp.com"},
        )
        checks["viewer_mutation_blocked"] = r_viewer.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)

    return {
        **{k: bool(v) for k, v in checks.items()},
        "all_passed": all(checks.values()),
        "audit_events": n_events,
    }


# --------------------------------------------------------------------------- #
def main() -> None:
    print("=" * 70)
    print("FluxBoard multi-agent safety -- experiment results (mock mode)")
    print("=" * 70)

    print("\n[Exp 1] Security veto attack suite")
    s1 = exp1_attack_suite()
    for cls, d in s1.items():
        print(f"  {cls:11s}  n={d['n']:<3} naive_block={d['naive_block_rate']:.0%}  defended_block={d['defended_block_rate']:.0%}")

    print("\n[Exp 2] RBAC schema-redaction correctness")
    s2 = exp2_rbac_redaction()
    for k, v in s2.items():
        print(f"  {k}: {v}")

    print("\n[Exp 3] Schema-pruning token reduction + recall")
    s3 = exp3_token_reduction()
    for k, v in s3.items():
        print(f"  {k}: {v}")

    print("\n[Exp 4] Orchestration latency (cold vs warm cache)")
    s4 = asyncio.run(exp4_latency())
    for k, v in s4.items():
        print(f"  {k}: {v}")

    print("\n[Exp 5] ORM-only mutation safety")
    s5 = exp5_mutation_safety()
    for k, v in s5.items():
        print(f"  {k}: {v}")

    print(f"\nCSV results written to: {RESULTS}")


if __name__ == "__main__":
    main()
