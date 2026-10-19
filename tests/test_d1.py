"""Tests for D1Database adapter using a fake D1 binding object.

The Workers runtime exposes D1 rows as JS-style objects with attribute access;
this fake replicates that shape so the adapter logic is verified without
Cloudflare tooling.
"""

import pytest

from db import D1Database, SQLiteDatabase


class FakeRow:
    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name):
        return self._data.get(name)


class FakeStatement:
    def __init__(self, rows: list[dict]):
        self._rows = [FakeRow(r) for r in rows]
        self._params = ()

    def bind(self, *params):
        self._params = params
        return self

    async def run(self):
        return {"success": True, "meta": {"changes": 1}}

    async def all(self):
        return {"results": self._rows, "success": True}

    async def first(self):
        return self._rows[0] if self._rows else None


class FakeD1:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.executed: list[str] = []

    def prepare(self, sql: str) -> FakeStatement:
        self.executed.append(sql)
        return FakeStatement(self.rows)


@pytest.fixture
def d1db():
    return D1Database(FakeD1([{"id": "a", "name": "alpha"}, {"id": "b", "name": "beta"}]))


async def test_d1_query_returns_normalized_dicts(d1db):
    rows = await d1db.query("SELECT id, name FROM t", columns=("id", "name"))
    assert rows == [{"id": "a", "name": "alpha"}, {"id": "b", "name": "beta"}]


async def test_d1_query_one(d1db):
    row = await d1db.query_one("SELECT id, name FROM t LIMIT 1", columns=("id", "name"))
    assert row == {"id": "a", "name": "alpha"}


async def test_d1_query_empty(d1db):
    empty = D1Database(FakeD1([]))
    assert await empty.query("SELECT 1", columns=("x",)) == []
    assert await empty.query_one("SELECT 1", columns=("x",)) is None


async def test_d1_execute_binds_params(d1db):
    await d1db.execute("INSERT INTO t VALUES (?, ?)", ("x", "y"))
    assert "INSERT INTO t VALUES (?, ?)" in d1db._d1.executed


async def test_d1_dict_rows_also_supported():
    # If the runtime hands back plain dicts, normalization must still work.
    class DictRowsD1(FakeD1):
        def prepare(self, sql):
            stmt = FakeStatement([])
            stmt._rows = [{"id": "z"}]
            return stmt

    db = D1Database(DictRowsD1())
    rows = await db.query("SELECT id FROM t", columns=("id",))
    assert rows == [{"id": "z"}]


async def test_sqlite_backend_parity():
    db = SQLiteDatabase(":memory:")
    await db.execute("CREATE TABLE t (id TEXT PRIMARY KEY, name TEXT)")
    await db.execute("INSERT INTO t VALUES (?, ?)", ("a", "alpha"))
    rows = await db.query("SELECT id, name FROM t", columns=("id", "name"))
    assert rows == [{"id": "a", "name": "alpha"}]