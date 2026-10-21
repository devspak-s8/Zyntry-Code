"""Local runtime helpers for running the app with uvicorn (no Workers runtime).

Builds a ``Runtime`` backed by a local SQLite database and OS environment
variables (loaded from ``.env`` if present). Workers AI is not available
locally, so provider availability falls back to OpenAI/Anthropic keys.
"""

import os

from db import SQLiteDatabase
from runtime import Runtime, set_local_runtime


def _load_dotenv() -> None:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


class _LocalEnv:
    """Minimal env-like object; has no DB/AI attributes (falls back to local)."""

    _local = True


def configure() -> Runtime:
    _load_dotenv()
    # Local uvicorn is ephemeral by design. Persistence lives on the Cloudflare
    # runtime: D1 (the ``DB`` binding) stores tasks/sessions durably, and the
    # same migrations in ../migrations are applied by pywrangler. Override with
    # LOCAL_DB_PATH if a scratch file database is ever needed for debugging.
    db_path = os.environ.get("LOCAL_DB_PATH", ":memory:")
    runtime = Runtime(env=_LocalEnv(), db=SQLiteDatabase(db_path))
    set_local_runtime(runtime)
    return runtime


async def init_db(runtime: Runtime) -> None:
    """Apply the schema to the local database (idempotent).

    Local dev replays every migration on each boot (in-memory DB). D1 applies
    each migration exactly once via ``migrations_dir`` on the Cloudflare side;
    the duplicate-column guard below keeps legacy ``ALTER`` statements safe for
    both paths.
    """
    import glob
    import sqlite3

    from db import split_sql

    here = os.path.dirname(__file__)
    migrations = sorted(glob.glob(os.path.join(here, "..", "migrations", "*.sql")))
    for path in migrations:
        with open(path, "r", encoding="utf-8") as fh:
            sql = fh.read()
        for statement in split_sql(sql):
            try:
                await runtime.db.execute(statement)
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise