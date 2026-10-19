"""Enumerations for the Zyntry Code domain model."""

from enum import Enum


class _Str(str, Enum):
    """A string enum whose members compare equal to their values."""

    def __str__(self) -> str:
        return self.value


class TaskStatus(_Str):
    PENDING = "pending"
    PLANNING = "planning"
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"


class StageStatus(_Str):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class AttemptStatus(_Str):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExecutionStatus(_Str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(_Str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Complexity(_Str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskKind(_Str):
    FRONTEND = "frontend"
    BACKEND = "backend"
    FULL_STACK = "full_stack"
    DATABASE = "database"
    SECURITY = "security"
    TESTING = "testing"
    REFACTOR = "refactor"
    OTHER = "other"


class StageKind(_Str):
    UNDERSTAND = "understand"
    ANALYZE = "analyze"
    PLAN = "plan"
    IMPLEMENT = "implement"
    IMPLEMENT_BACKEND = "implement_backend"
    IMPLEMENT_FRONTEND = "implement_frontend"
    DATABASE = "database"
    TEST = "test"
    REVIEW = "review"
    SECURITY_REVIEW = "security_review"
    VERIFY = "verify"
    INTEGRATE = "integrate"
    DOCUMENT = "document"


class VerificationType(_Str):
    SCHEMA = "schema"
    SYNTAX = "syntax"
    TESTS = "tests"
    TYPE_CHECK = "type_check"
    LINT = "lint"
    BUILD = "build"
    VISUAL = "visual"
    CONTRACT = "contract"
    SECURITY = "security"
    MIGRATION = "migration"
    BENCHMARK = "benchmark"
    RUNTIME = "runtime"
    BROWSER = "browser"


class Capability(_Str):
    CODE = "code"
    REASON = "reason"
    PLAN = "plan"
    REVIEW = "review"
    SECURITY = "security"
    LONG_CONTEXT = "long_context"
    VISION = "vision"