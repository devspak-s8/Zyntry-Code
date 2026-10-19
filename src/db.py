"""Database access layer.

Two interchangeable backends exposing the same minimal async interface:

- ``D1Database``  — Cloudflare D1 (SQLite) via the Workers ``env.DB`` binding.
- ``SQLiteDatabase`` — local stdlib ``sqlite3`` for uvicorn/local dev and tests.

Queries are plain SQL with positional ``?`` placeholders. The repository layer
(``store.py``) is the only consumer and always passes an explicit column list so
rows can be normalised to plain ``dict`` regardless of backend.
"""

import asyncio
import sqlite3
from typing import Any, Iterable


def _row_to_dict(row: Any, columns: Iterable[str]) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return {c: row.get(c) for c in columns}
    return {c: getattr(row, c, None) for c in columns}


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a plain dict or a JS-style attribute object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def split_sql(sql: str) -> list[str]:
    """Split a SQL script into statements, stripping ``--`` comments (full-line
    and inline). Not for use with ``--`` inside string literals."""
    cleaned = []
    for line in sql.splitlines():
        idx = line.find("--")
        if idx != -1:
            line = line[:idx]
        line = line.strip()
        if line:
            cleaned.append(line)
    return [part.strip() for part in " ".join(cleaned).split(";") if part.strip()]


class Database:
    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        raise NotImplementedError

    async def execute_changes(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Like ``execute`` but returns the number of rows affected (for atomic
        claim/rate-limit patterns)."""
        raise NotImplementedError

    async def query(
        self, sql: str, params: Iterable[Any] = (), columns: Iterable[str] = ()
    ) -> list[dict]:
        raise NotImplementedError

    async def query_one(
        self, sql: str, params: Iterable[Any] = (), columns: Iterable[str] = ()
    ) -> dict | None:
        raise NotImplementedError


class D1Database(Database):
    """Wraps the Cloudflare D1 binding object (``env.DB``)."""

    def __init__(self, d1: Any):
        self._d1 = d1

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        await self.execute_changes(sql, params)

    async def execute_changes(self, sql: str, params: Iterable[Any] = ()) -> int:
        stmt = self._d1.prepare(sql)
        values = tuple(params)
        if values:
            stmt = stmt.bind(*values)
        result = await stmt.run()
        if result is None:
            return 0
        meta = _field(result, "meta", None)
        return int(_field(meta, "changes", 0) or 0)

    async def query(
        self, sql: str, params: Iterable[Any] = (), columns: Iterable[str] = ()
    ) -> list[dict]:
        stmt = self._d1.prepare(sql)
        values = tuple(params)
        if values:
            stmt = stmt.bind(*values)
        result = await stmt.all()
        rows = _field(result, "results", None) or []
        return [_row_to_dict(r, columns) for r in rows if r is not None]

    async def query_one(
        self, sql: str, params: Iterable[Any] = (), columns: Iterable[str] = ()
    ) -> dict | None:
        stmt = self._d1.prepare(sql)
        values = tuple(params)
        if values:
            stmt = stmt.bind(*values)
        row = await stmt.first()
        return _row_to_dict(row, columns)


class SQLiteDatabase(Database):
    """Local stdlib sqlite3 backend (uvicorn dev server and tests)."""

    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = asyncio.Lock()

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        await self.execute_changes(sql, params)

    async def execute_changes(self, sql: str, params: Iterable[Any] = ()) -> int:
        async with self._lock:
            return await asyncio.to_thread(self._execute_changes, sql, tuple(params))

    async def query(
        self, sql: str, params: Iterable[Any] = (), columns: Iterable[str] = ()
    ) -> list[dict]:
        async with self._lock:
            rows = await asyncio.to_thread(self._query, sql, tuple(params))
        return [dict(r) for r in rows]

    async def query_one(
        self, sql: str, params: Iterable[Any] = (), columns: Iterable[str] = ()
    ) -> dict | None:
        async with self._lock:
            rows = await asyncio.to_thread(self._query, sql, tuple(params))
        return dict(rows[0]) if rows else None

    def _execute_changes(self, sql: str, params: tuple) -> int:
        with self._conn:
            cursor = self._conn.execute(sql, params)
            return cursor.rowcount if cursor.rowcount and cursor.rowcount >= 0 else 0

    def _query(self, sql: str, params: tuple) -> list:
        return self._conn.execute(sql, params).fetchall()