"""Adaptive verification.

Selects which checks apply to a stage and (where possible) runs them
deterministically. Checks that require a real repo sandbox (tests, lint, build,
visual, ...) are reported as limitations instead of being silently skipped —
per the product principle that an unavailable check must be reported, never
pretended to have passed.
"""

import ast
import re
from dataclasses import dataclass, field

from domain.enums import StageKind, VerificationType


# Checks the backend can actually run deterministically.
DETERMINISTIC_CHECKS = {VerificationType.SCHEMA, VerificationType.SYNTAX}

# Checks that require the developer's repository (run by the VS Code extension
# or a sandbox), not by this backend.
ENVIRONMENT_CHECKS = {
    VerificationType.TESTS, VerificationType.TYPE_CHECK, VerificationType.LINT,
    VerificationType.BUILD, VerificationType.VISUAL, VerificationType.CONTRACT,
    VerificationType.SECURITY, VerificationType.MIGRATION, VerificationType.BENCHMARK,
    VerificationType.RUNTIME, VerificationType.BROWSER,
}

VERIFICATION_BY_KIND: dict[StageKind, list[str]] = {
    StageKind.UNDERSTAND: [],
    StageKind.ANALYZE: [VerificationType.SCHEMA.value],
    StageKind.PLAN: [VerificationType.SCHEMA.value],
    StageKind.IMPLEMENT: [VerificationType.SYNTAX.value, VerificationType.TESTS.value],
    StageKind.IMPLEMENT_BACKEND: [VerificationType.SYNTAX.value, VerificationType.TESTS.value],
    StageKind.IMPLEMENT_FRONTEND: [VerificationType.SYNTAX.value, VerificationType.VISUAL.value, VerificationType.TESTS.value],
    StageKind.DATABASE: [VerificationType.MIGRATION.value, VerificationType.TESTS.value],
    StageKind.TEST: [VerificationType.SYNTAX.value, VerificationType.TESTS.value],
    StageKind.REVIEW: [],
    StageKind.SECURITY_REVIEW: [VerificationType.SECURITY.value],
    StageKind.VERIFY: [VerificationType.CONTRACT.value, VerificationType.TESTS.value],
    StageKind.INTEGRATE: [VerificationType.CONTRACT.value, VerificationType.TESTS.value],
    StageKind.DOCUMENT: [],
}


@dataclass
class VerificationOutcome:
    status: str                     # passed | failed | limited
    checks: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    env_tools: list[str] = field(default_factory=list)   # environment checks this stage requires

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "checks": self.checks,
            "limitations": self.limitations,
            "failures": self.failures,
            "env_tools": self.env_tools,
        }


_CODE_HINT_RE = re.compile(
    r"(```|^\s*(def |class |import |from |const |function |let |var |export |interface |type |SELECT |INSERT |CREATE TABLE ))",
    re.MULTILINE,
)

_FENCE_CONTENT_RE = re.compile(
    r"```(?:[A-Za-z0-9+#.-]+)?(?::[^\s`]+)?\s*\n(.*?)```",
    re.DOTALL,
)


def _extract_code(text: str) -> str:
    fenced = _FENCE_CONTENT_RE.findall(text or "")
    if fenced:
        return "\n\n".join(fenced)
    return text


PYTHON_LANGS = {"python", "py"}


def _declared_language(text: str) -> str | None:
    """Language from the first fenced block header (```lang:path or ```lang)."""
    match = re.search(r"```([A-Za-z0-9+#.-]+)(?::[^\s`]+)?\s*\n", text or "")
    if not match:
        return None
    return match.group(1).lower()


def _looks_like_python(code: str) -> bool:
    """Conservative Python sniffing: TS/JS `import { x } from` must NOT match."""
    if re.search(r"^\s*(def |class |async def |from \S+ import )", code, re.MULTILINE):
        return True
    if re.search(r"^\s*import [A-Za-z_][\w.]*\s*$", code, re.MULTILINE):
        return True
    return False


def contains_code(text: str) -> bool:
    return bool(_CODE_HINT_RE.search(text or ""))


def contains_python(text: str) -> bool:
    code = _extract_code(text or "")
    return bool(re.search(r"^\s*(def |class |import |from |async def )", code, re.MULTILINE))


def verify_stage(kind: str, verification_types: list[str], output: str) -> VerificationOutcome:
    kind = kind if isinstance(kind, StageKind) else StageKind(kind)
    text = (output or "").strip()
    checks: list[dict] = []
    failures: list[str] = []
    limitations: list[str] = []

    # 1. Non-empty output is a baseline requirement for every stage.
    if not text:
        failures.append("empty output")
    else:
        checks.append({"type": "non_empty", "status": "passed"})

    # 2. Structure check for analysis/planning stages.
    if kind in (StageKind.PLAN, StageKind.ANALYZE, StageKind.UNDERSTAND) and text:
        checks.append({"type": "structure", "status": "passed", "note": "non-empty structured output"})

    # 3. Code-producing stages must actually produce code.
    code_stages = {StageKind.IMPLEMENT, StageKind.IMPLEMENT_BACKEND, StageKind.IMPLEMENT_FRONTEND,
                   StageKind.DATABASE, StageKind.TEST, StageKind.INTEGRATE}
    if kind in code_stages and text and not contains_code(text):
        failures.append("no code produced (expected code for this stage)")

    # 4. Deterministic syntax check: parse Python ONLY for Python code. Never
    #    misfire on TypeScript/JS (which share `import` syntax with Python).
    if VerificationType.SYNTAX.value in verification_types:
        declared = _declared_language(text)
        if declared in PYTHON_LANGS or (declared is None and _looks_like_python(text)):
            code = _extract_code(text)
            try:
                ast.parse(code)
                checks.append({"type": "syntax", "status": "passed", "language": "python"})
            except SyntaxError as exc:
                failures.append(f"python syntax error: {exc.msg} (line {exc.lineno})")
                checks.append({"type": "syntax", "status": "failed", "note": str(exc)})
        else:
            checks.append({"type": "syntax", "status": "skipped",
                           "note": f"language not python ({declared or 'unknown'})"})

    # 5. Environment-required checks -> reported as limitations.
    missing = [c for c in verification_types if c in {e.value for e in ENVIRONMENT_CHECKS}]
    if missing:
        limitations.append(f"requires repo sandbox (not available in backend): {', '.join(missing)}")

    if failures:
        status = "failed"
    elif limitations:
        status = "limited"
    else:
        status = "passed"

    return VerificationOutcome(status=status, checks=checks, limitations=limitations,
                               failures=failures, env_tools=missing)


def merge_reports(outcome: VerificationOutcome, reports: list[dict]) -> VerificationOutcome:
    """Fold verification reports posted by the repo-side runner (VS Code extension)
    into the deterministic outcome.

    - A failed report fails the stage (and can therefore trigger escalation).
    - Passed reports clear the corresponding "requires repo sandbox" limitations.
    - Uncovered environment checks stay reported as limitations (never claimed passed).
    """
    if not reports:
        return outcome

    by_tool: dict[str, dict] = {}
    for r in reports:
        by_tool.setdefault(r["tool"], r)

    failed = [by_tool[t] for t in by_tool if by_tool[t]["status"] == "failed"]
    if failed:
        outcome.status = "failed"
        for r in failed:
            detail = (r.get("output") or "").strip()[:300]
            outcome.failures.append(f"{r['tool']}: {detail}" if detail else f"{r['tool']}: failed")
        outcome.checks.append({"type": "repo_report", "status": "failed",
                               "tools": sorted(by_tool.keys())})
        return outcome

    passed = {t for t in by_tool if by_tool[t]["status"] == "passed"}
    outcome.checks.append({"type": "repo_report", "status": "passed",
                           "tools": sorted(passed)})

    # Only clear limitations that the passed reports actually cover.
    still_missing = [t for t in outcome.env_tools if t not in passed]
    if still_missing:
        outcome.limitations = [
            l for l in outcome.limitations
            if not l.startswith("requires repo sandbox")
        ] + [f"requires repo sandbox (not available in backend): {', '.join(still_missing)}"]
    else:
        outcome.limitations = [l for l in outcome.limitations
                               if not l.startswith("requires repo sandbox")]

    if not outcome.limitations and outcome.status == "limited":
        outcome.status = "passed"
    return outcome