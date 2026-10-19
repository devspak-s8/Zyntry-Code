"""Small shared utilities."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any


def uuid_str() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, default=str)


def json_loads(value: str | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def truncate(text: str | None, limit: int = 4000) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."