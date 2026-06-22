"""DDL rendering and token accounting for the token-reduction experiment.

We render the schema as compact ``CREATE TABLE``-style DDL (the same shape the
orchestrator feeds the LLM in ``master.py::_compile_sql``) and count tokens
with the ``cl100k_base`` BPE tokenizer when available. A whitespace-token and
character count are always reported as tokenizer-independent backups so the
result does not hinge on any single vendor's tokenizer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.validation import DatabaseSchema

try:  # pragma: no cover - exercised implicitly by the runner
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover
    _ENC = None


def bpe_tokens(text: str) -> int | None:
    if _ENC is None:
        return None
    return len(_ENC.encode(text))


def ws_tokens(text: str) -> int:
    return len(text.split())


def render_ddl(schema: DatabaseSchema, tables: set[str] | None = None) -> str:
    """Render (a subset of) the schema as compact DDL.

    ``tables=None`` renders the full schema; otherwise only the named tables.
    Foreign keys touching the rendered tables are appended as hint lines,
    matching what the SQL compiler actually sends to the model.
    """
    lines: list[str] = []
    selected = set(t.name for t in schema.tables) if tables is None else set(tables)
    for table in schema.tables:
        if table.name not in selected:
            continue
        cols = ", ".join(f"{c.name} {c.data_type}" for c in table.columns)
        lines.append(f"CREATE TABLE {table.name} ({cols});")
    fk_hints = [
        f"  -- FK {fk.source_table}.{fk.source_column} -> {fk.target_table}.{fk.target_column}"
        for fk in schema.foreign_keys
        if fk.source_table in selected and fk.target_table in selected
    ]
    return "\n".join(lines + fk_hints)


@dataclass
class TokenCount:
    bpe: int | None
    whitespace: int
    chars: int

    @classmethod
    def of(cls, text: str) -> TokenCount:
        return cls(bpe=bpe_tokens(text), whitespace=ws_tokens(text), chars=len(text))


def reduction(full: int, pruned: int) -> float:
    if full <= 0:
        return 0.0
    return 1.0 - (pruned / full)
