"""Task assessment: deterministic risk / complexity / kind classification.

Runs at intake before planning and routing. Deliberately rule-based so it is
fast, free, and deterministic — the LLM is reserved for the actual work.
"""

from domain.enums import RiskLevel, Complexity, TaskKind


CRITICAL_KEYWORDS = [
    "payment", "payments", "billing", "checkout", "refund", "invoice", "charge",
    "webhook", "pci", "card", "production", "pii", "gdpr", "encryption",
    "encrypt", "credential", "secret", "password", "token", "session",
    "authentication", "authorization", "permission", "migration", "infrastructure",
    "terraform", "kubernetes", "deploy", "admin", "sudo",
]

HIGH_KEYWORDS = [
    "auth", "login", "security", "database", "schema", "access control", "role",
    "audit", "api key", "sensitive", "multi-tenant", "organization",
]

MEDIUM_KEYWORDS = [
    "refactor", "async", "concurrency", "cache", "performance", "api", "endpoint",
    "service", "integration", "notification", "queue", "model",
]

LOW_COMPLEXITY_KEYWORDS = [
    "typo", "spelling", "label", "color", "colour", "css", "margin", "padding",
    "text", "copy", "button", "icon", "style", "format", "rename",
]

HIGH_COMPLEXITY_KEYWORDS = [
    "build", "system", "pipeline", "microservice", "distributed", "end-to-end",
    "e2e", "full", "complete", "from scratch", "architecture", "redesign",
    "refactor", "migration", "notification", "multi-tenant", "enterprise",
    "platform",
]


def _risk(prompt: str) -> RiskLevel:
    if any(k in prompt for k in CRITICAL_KEYWORDS):
        return RiskLevel.CRITICAL
    if any(k in prompt for k in HIGH_KEYWORDS):
        return RiskLevel.HIGH
    if any(k in prompt for k in MEDIUM_KEYWORDS):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _complexity(prompt: str) -> Complexity:
    if any(k in prompt for k in HIGH_COMPLEXITY_KEYWORDS):
        return Complexity.HIGH
    if any(k in prompt for k in LOW_COMPLEXITY_KEYWORDS):
        return Complexity.LOW
    return Complexity.MEDIUM


def _task_kind(prompt: str) -> TaskKind:
    if any(k in prompt for k in ["notification", "full-stack", "full stack",
                                 "end-to-end", "e2e", "complete system", "pipeline", "platform"]):
        return TaskKind.FULL_STACK
    if any(k in prompt for k in ["frontend", "ui", "css", "component", "react",
                                 "vue", "html", "layout", "responsive", "navigation", "webview"]):
        return TaskKind.FRONTEND
    if any(k in prompt for k in ["database", "schema", "migration", "sql", "persistence", "migrate"]):
        return TaskKind.DATABASE
    if any(k in prompt for k in ["auth", "login", "security", "permission",
                                 "authorization", "authentication", "access control", "role"]):
        return TaskKind.SECURITY
    if any(k in prompt for k in ["test", "testing", "coverage", "unit test", "integration test"]):
        return TaskKind.TESTING
    if any(k in prompt for k in ["refactor", "restructure", "reorganize"]):
        return TaskKind.REFACTOR
    if any(k in prompt for k in ["api", "backend", "endpoint", "server", "rest", "graphql", "service"]):
        return TaskKind.BACKEND
    return TaskKind.OTHER


def assess(prompt: str) -> dict:
    """Return a classification dict with string values."""
    p = (prompt or "").lower()
    return {
        "risk_level": _risk(p).value,
        "complexity": _complexity(p).value,
        "task_kind": _task_kind(p).value,
    }