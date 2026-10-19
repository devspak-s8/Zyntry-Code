"""Runtime abstraction: Workers environment + D1 database + settings access.

On Cloudflare the FastAPI ``app`` is served through the ``asgi`` adapter, which
places the Workers environment into ``request.scope["env"]``. Locally (uvicorn)
there is no Workers environment, so we fall back to a module-level ``local``
runtime configured by ``local/dev.py``.
"""

import os
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from db import Database, D1Database, SQLiteDatabase


@dataclass
class Runtime:
    env: Any = None
    db: Database | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Read a setting: Workers env var/secret first, then OS env."""
        if self.env is not None:
            value = getattr(self.env, key, None)
            if value is not None and value != "":
                return value
        value = os.environ.get(key)
        return default if value is None else value

    def get_int(self, key: str, default: int) -> int:
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float) -> float:
        try:
            return float(self.get(key, default))
        except (TypeError, ValueError):
            return default

    @property
    def workers_ai(self) -> Any:
        return getattr(self.env, "AI", None) if self.env is not None else None


def runtime_from_env(env: Any) -> Runtime:
    d1 = getattr(env, "DB", None) if env is not None else None
    if d1 is not None:
        return Runtime(env=env, db=D1Database(d1))
    local_db = getattr(env, "db", None) if env is not None else None
    return Runtime(env=env, db=local_db or SQLiteDatabase())


_LOCAL: Runtime | None = None


def set_local_runtime(runtime: Runtime) -> None:
    global _LOCAL
    _LOCAL = runtime


def local_runtime() -> Runtime:
    global _LOCAL
    if _LOCAL is None:
        _LOCAL = Runtime(env=None, db=SQLiteDatabase())
    return _LOCAL


def get_runtime(request: Request) -> Runtime:
    """FastAPI dependency: resolve the runtime for the current request."""
    env = request.scope.get("env")
    if env is not None:
        return runtime_from_env(env)
    return local_runtime()