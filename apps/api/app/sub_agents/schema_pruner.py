from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.validation import DatabaseSchema, SchemaContext

COMMON_COLUMN_TERMS = {"status", "created", "updated", "created_at", "updated_at", "id"}

ENTITY_MAP: dict[str, list[str]] = {
    "development revenue": ["tasks", "projects"],
    "completed tasks": ["tasks"],
    "done work": ["tasks"],
    "project": ["projects"],
    "assignee": ["users"],
    "team member": ["users"],
    "comment": ["comments"],
    "bình luận": ["comments"],
    "nhãn": ["labels", "task_labels"],
    "label": ["labels", "task_labels"],
    "trạng thái": ["statuses"],
    "status": ["statuses"],
    "cột": ["statuses"],
}


class TTLCache(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...

    def invalidate(self, key: str) -> None: ...


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class InProcessTTLCache:
    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._store: MutableMapping[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or self.default_ttl_seconds
        self._store[key] = CacheEntry(value=value, expires_at=time.monotonic() + ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)


class RedisTTLCache:
    def __init__(self, redis_url: str, default_ttl_seconds: int = 300) -> None:
        self.redis_url = redis_url
        self.default_ttl_seconds = default_ttl_seconds

    def get(self, key: str) -> Any | None:
        raise RuntimeError("RedisTTLCache requires a real serializer/client in integration mode")

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        raise RuntimeError("RedisTTLCache requires a real serializer/client in integration mode")

    def invalidate(self, key: str) -> None:
        raise RuntimeError("RedisTTLCache requires a real serializer/client in integration mode")


class RedisClusterTTLCache(RedisTTLCache):
    pass


class SchemaPruner:
    def __init__(
        self,
        cache: TTLCache | None = None,
        entity_map: dict[str, list[str]] | None = None,
        ignored_terms: set[str] | None = None,
    ) -> None:
        self.cache = cache or InProcessTTLCache()
        self.entity_map = entity_map or ENTITY_MAP
        self.ignored_terms = ignored_terms or COMMON_COLUMN_TERMS

    def prune(self, question: str, schema: DatabaseSchema) -> SchemaContext:
        cache_key = f"schema-prune:{question.lower()}:{','.join(sorted(schema.table_names()))}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        query_tokens = _tokens(question)
        entity_matches: dict[str, list[str]] = {}

        physical = self._physical_table_matches(query_tokens, schema)
        if physical:
            entity_matches["physical"] = sorted(physical)

        mapped = self._business_entity_matches(question)
        mapped &= schema.table_names()
        if mapped:
            entity_matches["business"] = sorted(mapped)

        column = self._column_token_matches(query_tokens, schema)
        if column:
            entity_matches["columns"] = sorted(column)

        seed_tables = physical | mapped | column
        if not seed_tables:
            seed_tables = {schema.tables[0].name} if schema.tables else set()

        selected_tables = self._expand_join_paths(seed_tables, schema)
        selected_columns = {
            table.name: [column.name for column in table.columns]
            for table in schema.tables
            if table.name in selected_tables
        }
        join_paths = self._join_paths(seed_tables, selected_tables, schema)
        reduction_ratio = 1.0 - (len(selected_tables) / max(len(schema.tables), 1))

        context = SchemaContext(
            selected_tables=sorted(selected_tables),
            selected_columns=selected_columns,
            join_paths=join_paths,
            entity_matches=entity_matches,
            token_budget_reduction_ratio=max(0.0, reduction_ratio),
        )
        self.cache.set(cache_key, context)
        return context

    def _physical_table_matches(self, query_tokens: set[str], schema: DatabaseSchema) -> set[str]:
        matches: set[str] = set()
        for table in schema.tables:
            forms = {table.name.lower(), _singular(table.name.lower()), f"{table.name.lower()}s"}
            if forms & query_tokens:
                matches.add(table.name)
        return matches

    def _business_entity_matches(self, question: str) -> set[str]:
        normalized = question.lower()
        matches: set[str] = set()
        for phrase, tables in self.entity_map.items():
            if phrase in normalized:
                matches.update(tables)
        return matches

    def _column_token_matches(self, query_tokens: set[str], schema: DatabaseSchema) -> set[str]:
        matches: set[str] = set()
        meaningful_tokens = {token for token in query_tokens if len(token) >= 6}
        for table in schema.tables:
            for column in table.columns:
                normalized_column = column.name.lower()
                if normalized_column in self.ignored_terms:
                    continue
                column_tokens = _tokens(normalized_column.replace("_", " "))
                if meaningful_tokens & column_tokens:
                    matches.add(table.name)
        return matches

    def _expand_join_paths(self, seeds: set[str], schema: DatabaseSchema) -> set[str]:
        if len(seeds) <= 1:
            return set(seeds)
        adjacency = _adjacency(schema)
        selected = set(seeds)
        seed_list = list(seeds)
        for source in seed_list:
            for target in seed_list:
                if source == target:
                    continue
                path = _shortest_path(source, target, adjacency)
                selected.update(path)
        return selected

    def _join_paths(
        self, seeds: set[str], selected_tables: set[str], schema: DatabaseSchema
    ) -> list[list[str]]:
        adjacency = _adjacency(schema)
        paths: list[list[str]] = []
        seed_list = list(seeds)
        for index, source in enumerate(seed_list):
            for target in seed_list[index + 1 :]:
                path = _shortest_path(source, target, adjacency)
                if path and set(path) <= selected_tables:
                    paths.append(path)
        return paths


def _tokens(text: str) -> set[str]:
    return {
        "".join(char for char in token.lower() if char.isalnum() or char == "_")
        for token in text.split()
    } - {""}


def _singular(value: str) -> str:
    return value[:-1] if value.endswith("s") else value


def _adjacency(schema: DatabaseSchema) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for foreign_key in schema.foreign_keys:
        graph[foreign_key.source_table].add(foreign_key.target_table)
        graph[foreign_key.target_table].add(foreign_key.source_table)
    return graph


def _shortest_path(source: str, target: str, adjacency: dict[str, set[str]]) -> list[str]:
    queue: deque[tuple[str, list[str]]] = deque([(source, [source])])
    seen = {source}
    while queue:
        current, path = queue.popleft()
        if current == target:
            return path
        for neighbor in adjacency[current]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, [*path, neighbor]))
    return []
