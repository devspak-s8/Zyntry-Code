"""Planning service: assesses, LLM-plans, and persists a task's execution plan.

Planning is LLM-only: a plan-capable model produces the plan as strictly
validated JSON (with a 3-attempt refinement loop). If no provider is
configured, no plan-capable model is available, the provider errors, or the
model never produces valid JSON, intake fails loudly — there is no
deterministic template fallback.
The repo snapshot (ingested via ``POST /tasks/{id}/repo``) informs the plan.
"""

import re

from domain import assessment, routing
from domain.catalog import ModelSpec
from domain.enums import RiskLevel, StageKind, TaskStatus, VerificationType
from metrics import metrics
from runtime import Runtime
from util import truncate, uuid_str
import store

_VALID_KINDS = {k.value for k in StageKind}
_VALID_TOOLS = {v.value for v in VerificationType}
_MAX_STAGES = 12

_PLANNER_SYSTEM = (
    "You are the planning component of Zyntry Code, an adaptive engineering agent. "
    "Given a task (and optionally repository context), produce an execution plan as JSON. "
    "Respond with ONLY a JSON object, no markdown fences, no commentary. "
    "The object must have exactly this shape:\n"
    '{"summary": "short plan summary", "stages": ['
    '{"kind": "<stage_kind>", "title": "short title", "description": "what this stage does", '
    '"dependencies": [<zero-based indices of earlier stages>], "verification": ["<verification_type>"]}'
    "]}\n"
    f"Allowed stage kinds: {', '.join(sorted(_VALID_KINDS))}. "
    f"Allowed verification types: {', '.join(sorted(_VALID_TOOLS))} (use [] for none). "
    "Stages must form an acyclic dependency graph; indices must reference earlier stages. "
    f"Use at most {_MAX_STAGES} stages. Typical shapes: understand -> analyze -> plan -> "
    "implement -> test -> review -> verify (backend), or understand -> plan -> implement_frontend -> "
    "test -> verify (frontend), etc. Choose kinds appropriate to the task."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_plan_json(text: str) -> dict | None:
    """Strictly parse/validate an LLM-produced plan. Returns None on any problem."""
    if not text:
        return None
    match = _JSON_RE.search(text.strip())
    if not match:
        return None
    import json
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    stages = data.get("stages")
    if not isinstance(stages, list) or not stages or len(stages) > _MAX_STAGES:
        return None

    normalized = []
    for i, s in enumerate(stages):
        if not isinstance(s, dict):
            return None
        kind = s.get("kind")
        if kind not in _VALID_KINDS:
            return None
        title = s.get("title") or kind
        deps = s.get("dependencies") or []
        if not isinstance(deps, list):
            return None
        clean_deps = []
        for d in deps:
            if isinstance(d, int) and 0 <= d < i:
                clean_deps.append(d)
            elif isinstance(d, str) and d.isdigit() and 0 <= int(d) < i:
                clean_deps.append(int(d))
            else:
                return None  # invalid dependency reference
        tools = s.get("verification") or []
        if not isinstance(tools, list):
            return None
        tools = [t for t in tools if t in _VALID_TOOLS]
        normalized.append({
            "kind": kind,
            "title": str(title)[:120],
            "description": str(s.get("description") or "")[:2000],
            "dependencies": clean_deps,
            "verification_types": tools,
        })
    return {"summary": str(data.get("summary") or "")[:500], "stages": normalized}


async def _llm_plan(runtime: Runtime, prompt: str, risk: str, repo_files: list[dict]) -> dict:
    """LLM-driven planning with refinement; raises RuntimeError on failure.

    The model proposes the plan as strict JSON; if validation fails, the
    validation error is fed back and the model tries again (up to 3 attempts).
    Every failure mode raises with a specific reason — planning is LLM-only,
    so there is nothing to fall back to.
    """
    from providers import available_providers, build_provider, provider_order

    avail = available_providers(runtime)
    if not avail:
        raise RuntimeError(
            "LLM planning requires at least one configured provider "
            "(OPENAI_API_KEY, ANTHROPIC_API_KEY, or Workers AI), but none are "
            "available. Planning is LLM-only; set provider keys and retry.")

    selected, _, _ = routing.select_model(
        StageKind.PLAN.value, risk, avail, provider_order(runtime))
    if selected is None:
        raise RuntimeError(
            "No plan-capable model is available from the configured providers. "
            "Planning is LLM-only; configure a provider with planning capability.")

    provider = build_provider(selected.provider, runtime)

    context = ""
    if repo_files:
        context = "# Repository context\n" + "\n".join(
            f"- {f['path']} ({f.get('language') or '?'}, {f.get('size', 0)} bytes)" for f in repo_files[:80])
        sample = [f"### {f['path']}\n{truncate(f.get('content') or '', 1200)}" for f in repo_files[:6] if f.get("content")]
        if sample:
            context += "\n\n# Key files\n" + "\n\n".join(sample)

    user_prompt = f"# Task\n{prompt}\n\n{context}".strip()

    for attempt in range(3):
        if attempt > 0:
            user_prompt += (
                "\n\n# Your previous attempt did not match the required schema.\n"
                f"Previous attempt (first 1000 chars):\n{truncate(previous_text, 1000)}\n"
                "Fix the response so it is EXACTLY a JSON object matching the schema "
                "described in the system message. Do not wrap it in markdown fences."
            )
        try:
            result = await provider.complete(
                selected.id, user_prompt, system=_PLANNER_SYSTEM, temperature=0.1, max_tokens=4000)
        except Exception as exc:  # provider/network failure
            metrics.incr("planner_llm_error")
            raise RuntimeError(
                f"LLM planning failed: the provider raised an error ({exc}). "
                "Planning is LLM-only; fix the provider configuration and retry.") from exc
        if result.error:
            metrics.incr("planner_llm_error")
            raise RuntimeError(
                f"LLM planning failed: the provider returned an error ({result.error}). "
                "Planning is LLM-only; fix the provider configuration and retry.")
        previous_text = result.text
        parsed = parse_plan_json(result.text)
        if parsed is not None:
            metrics.incr("planner_source_llm")
            if attempt > 0:
                metrics.incr("planner_refinement_total")
            return parsed
        metrics.incr("planner_parse_fallback")

    raise RuntimeError(
        "LLM planning failed: the model's response did not match the required JSON "
        "schema after 3 refinement attempts. Planning is LLM-only; no plan was "
        "created for this task.")


async def create_and_plan(runtime: Runtime, *, prompt: str, repo: str | None,
                          constraints: dict | None, max_attempts_per_stage: int | None,
                          budget_usd: float | None) -> dict:
    db = runtime.db
    assessment_result = assessment.assess(prompt)
    risk = assessment_result["risk_level"]
    complexity = assessment_result["complexity"]
    task_kind = assessment_result["task_kind"]

    merged_constraints = dict(constraints or {})
    if max_attempts_per_stage is not None:
        merged_constraints.setdefault("max_attempts_per_stage", max_attempts_per_stage)
    if budget_usd is not None:
        merged_constraints.setdefault("budget_usd", budget_usd)

    needs_approval = risk in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
    status = TaskStatus.AWAITING_APPROVAL.value if needs_approval else TaskStatus.PLANNED.value

    task_id = await store.create_task(
        db, prompt=prompt, repo=repo, status=status, risk_level=risk,
        complexity=complexity, task_kind=task_kind, constraints=merged_constraints,
    )

    repo_files = await store.get_repo_files(db, task_id)

    # Planning is LLM-only: _llm_plan raises on failure (no providers, no
    # plan-capable model, provider error, or invalid JSON after refinement).
    # The API maps this to a 503 — loud failure, never a silent template.
    llm_plan = await _llm_plan(runtime, prompt, risk, repo_files)
    source = "llm"
    summary = llm_plan["summary"] or truncate(prompt, 200)
    draft_stages = llm_plan["stages"]
    metrics.incr("plans_source_llm")

    plan_id = await store.create_plan(db, task_id, summary, source=source)

    id_by_index: dict[int, str] = {}
    for i, stage in enumerate(draft_stages):
        stage_id = uuid_str()
        id_by_index[i] = stage_id
        deps = [id_by_index[d] for d in stage.get("dependencies", [])]
        await store.create_stage(
            db, plan_id, stage_id=stage_id, kind=stage["kind"], title=stage["title"],
            description=stage.get("description") or "",
            dependencies=deps,
            verification_types=stage.get("verification_types", []),
            risk_level=risk, position=i,
        )

    stages = [store.stage_dict(s) for s in await store.get_stages(db, plan_id)]

    return {
        "task": store.task_dict(await store.get_task(db, task_id)),
        "plan": {"id": plan_id, "summary": summary, "source": source, "stages": stages},
        "assessment": assessment_result,
        "requires_approval": needs_approval,
    }