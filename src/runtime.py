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
    # Per-request credential overrides (e.g. a caller's own provider key sent
    # via headers). Never persisted; checked before env vars in ``get``.
    overrides: dict[str, Any] | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Read a setting: request overrides, then Workers env var, then OS env."""
        if self.overrides:
            value = self.overrides.get(key)
            if value:
                return value
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

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

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
    if request.scope.get("env") is not None:
        runtime = runtime_from_env(request.scope["env"])
    else:
        runtime = local_runtime()
    overrides = request.scope.get("runtime_overrides")
    if overrides:
        runtime.overrides = dict(overrides)
    return runtime