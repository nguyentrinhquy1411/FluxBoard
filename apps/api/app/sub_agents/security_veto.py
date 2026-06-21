from __future__ import annotations

import re

from app.schemas.validation import (
    ColumnDefinition,
    DatabaseSchema,
    SecurityResult,
    SecurityViolation,
    SQLOutput,
    TableDefinition,
)

MUTATION_PATTERN = re.compile(r"\b(DELETE|UPDATE|DROP|ALTER|INSERT|TRUNCATE|MERGE|CREATE)\b", re.I)


class SecurityVetoAgent:
    def derive_visible_schema(self, schema: DatabaseSchema, roles: list[str]) -> SecurityResult:
        role_set = set(roles)
        visible_tables: list[TableDefinition] = []
        violations: list[str] = []
        visible_table_names: set[str] = set()

        for table in schema.tables:
            if not table.allowed_for(role_set):
                violations.append(f"table hidden by RBAC: {table.name}")
                continue
            visible_columns: list[ColumnDefinition] = []
            for column in table.columns:
                if column.sensitive and not column.allowed_for(role_set):
                    violations.append(f"sensitive column hidden: {table.name}.{column.name}")
                    continue
                if not column.allowed_for(role_set):
                    violations.append(f"column hidden by RBAC: {table.name}.{column.name}")
                    continue
                visible_columns.append(column)
            visible_tables.append(table.model_copy(update={"columns": visible_columns}))
            visible_table_names.add(table.name)

        visible_foreign_keys = [
            foreign_key
            for foreign_key in schema.foreign_keys
            if foreign_key.source_table in visible_table_names
            and foreign_key.target_table in visible_table_names
        ]
        return SecurityResult(
            allowed=True,
            reason="schema pruned for user roles",
            visible_schema=DatabaseSchema(tables=visible_tables, foreign_keys=visible_foreign_keys),
            violations=violations,
        )

    def validate_sql(self, sql: SQLOutput) -> SecurityResult:
        normalized = sql.query.strip()
        violations: list[str] = []
        if not normalized.lower().startswith("select"):
            violations.append("only SELECT statements are allowed")
        if MUTATION_PATTERN.search(normalized):
            violations.append("mutation command detected")
        if self._contains_literal_user_value(normalized) and not sql.parameters:
            violations.append("query appears to contain literals without parameters")

        allowed = not violations
        result = SecurityResult(
            allowed=allowed,
            reason="allowed" if allowed else "security veto",
            violations=violations,
        )
        if not allowed:
            raise SecurityViolation("; ".join(violations))
        return result

    def _contains_literal_user_value(self, query: str) -> bool:
        return bool(re.search(r"=\s*'[^']+'|=\s*\"[^\"]+\"", query))
