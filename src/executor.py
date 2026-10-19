"""Execution engine: coordinates a multi-stage plan end-to-end.

Per stage: route model -> prompt -> run -> verify (deterministic + repo
reports) -> escalate on failure. Independent stages within a dependency level
run concurrently. A cost budget is enforced across the whole execution.

Runs synchronously within the request, or inside a Cloudflare Durable Workflow
(see ``src/worker.py``) for long-running production tasks.
"""

import asyncio
import time
from typing import Any, Callable

from domain import artifacts as artifacts_domain
from domain import escalation, routing, verification, tools as tools_domain
from domain.catalog import ModelSpec
from domain.enums import AttemptStatus, ExecutionStatus, RiskLevel, StageKind, StageStatus, TaskStatus
from metrics import metrics
from providers import build_provider, provider_order, available_providers
from providers.base import LLMResult
from runtime import Runtime
import store
import tools_service
from util import json_dumps, now_iso, truncate

EventCallback = Callable[[dict], Any]

SYSTEM_PROMPT = (
    "You are Zyntry Code, an adaptive AI engineering agent. You complete one "
    "focused stage of a larger engineering task. Work precisely, follow the "
    "stage instructions, and return only the requested deliverable. When asked "
    "for code, output code directly with fenced blocks; name each file as "
    "```language:path/to/file``` so changes can be tracked. "
    "Your FINAL answer must contain the actual code itself in fenced blocks — "
    "never just a description of the change. If the stage requires code and "
    "your final answer contains no code, the stage fails."
)

STAGE_INSTRUCTIONS = {
    StageKind.UNDERSTAND: "Investigate the repository and summarize the relevant structure, files, dependencies, and conventions needed for this task.",
    StageKind.ANALYZE: "Analyze the requirements, constraints, dependencies, and risks. Identify what is affected and any pitfalls.",
    StageKind.PLAN: "Produce a concrete, ordered implementation plan, including any API and database contracts needed.",
    StageKind.IMPLEMENT: "Implement the change. Output the resulting code.",
    StageKind.IMPLEMENT_BACKEND: "Implement the backend changes. Output the resulting code.",
    StageKind.IMPLEMENT_FRONTEND: "Implement the frontend changes. Output the resulting code.",
    StageKind.DATABASE: "Design the data model and any schema/migration changes. Output the SQL/DDL.",
    StageKind.TEST: "Generate tests covering the change. Output the test code.",
    StageKind.REVIEW: "Review the change for correctness, maintainability, and edge cases. List findings and a verdict.",
    StageKind.SECURITY_REVIEW: "Perform a focused security review. List findings, severity, and required fixes.",
    StageKind.VERIFY: "Verify the final result against the original requirements and summarize the evidence.",
    StageKind.INTEGRATE: "Integrate the pieces, resolve conflicts, and reconcile contracts. Output the integrated result.",
    StageKind.DOCUMENT: "Document the change for future maintainers.",
}

# Environment checks that a repo-side runner can report back on.
_ENV_TOOLS = {"tests", "type_check", "lint", "build", "visual", "contract", "security", "migration", "benchmark"}


COMPACT_THRESHOLD = 8000
COMPACT_MAX_CHARS = 1200


async def _compact_prior_outputs(ctx: "_RunContext", stage: dict,
                                 prior_outputs: dict[str, str], model: ModelSpec,
                                 provider) -> dict[str, str]:
    """Replace bulky prior-stage outputs with an LLM digest when they exceed
    ``COMPACT_THRESHOLD`` characters, keeping token cost flat as stages grow."""
    deps = [d for d in (stage.get("dependencies") or []) if d in prior_outputs]
    if not deps:
        return {}
    total = sum(len(prior_outputs[d]) for d in deps)
    if total <= COMPACT_THRESHOLD:
        return {d: prior_outputs[d] for d in deps}
    cached = ctx.compact_cache.get(stage["id"])
    if cached is not None:
        return cached

    joined = "\n\n".join(f"### {d[:8]}\n{truncate(prior_outputs[d], 2000)}" for d in deps)
    result = await provider.complete(
        model.id,
        f"Compress these engineering stage outputs into a dense technical digest "
        f"of at most {COMPACT_MAX_CHARS} characters, preserving decisions, contracts, "
        f"file paths, APIs, and failures:\n\n{joined}",
        system="You are a context compressor for a coding agent.",
        temperature=0.0, max_tokens=800)
    if result.error or not result.text:
        return {d: truncate(prior_outputs[d], 1500) for d in deps}
    metrics.incr("context_compactions_total")
    compacted = {d: result.text[:COMPACT_MAX_CHARS] for d in deps}
    ctx.compact_cache[stage["id"]] = compacted
    return compacted


def _stage_instruction(kind: str) -> str:
    try:
        return STAGE_INSTRUCTIONS[StageKind(kind)]
    except ValueError:
        return STAGE_INSTRUCTIONS[StageKind.IMPLEMENT]


def _budget_max_tokens(ctx: "_RunContext", model: ModelSpec) -> int | None:
    """Cap output tokens so the projected output cost can't exceed the remaining budget."""
    if ctx.budget is None or model.cost_out <= 0:
        return None
    remaining = ctx.budget - ctx.spend
    if remaining <= 0:
        return 64
    affordable = int(remaining / model.cost_out * 1_000_000)
    return max(64, min(affordable, 16384))


def _tool_callable(model: ModelSpec) -> bool:
    return "reason" in {str(c) for c in model.capabilities}


def topo_levels(stages: list[dict]) -> list[list[dict]]:
    """Group stages into dependency levels; stages within a level can run in parallel."""
    by_id = {s["id"]: s for s in stages}
    remaining: set[str] = set(by_id)
    levels: list[list[dict]] = []

    while remaining:
        ready = [
            by_id[i] for i in sorted(remaining, key=lambda i: by_id[i]["position"])
            if all((d not in remaining) for d in (by_id[i].get("dependencies") or []))
        ]
        if not ready:
            # Dependency cycle (or unknown deps): process the rest in one level
            # rather than hanging; each stage will still execute.
            ready = sorted((by_id[i] for i in remaining), key=lambda s: s["position"])
        levels.append(ready)
        for s in ready:
            remaining.discard(s["id"])
    return levels


def _build_prompt(task: dict, stage: dict, prior_outputs: dict[str, str],
                  repo_files: list[dict], failure_context: str | None = None) -> str:
    instruction = stage.get("description") or _stage_instruction(stage["kind"])
    parts = [f"# Task\n{task['prompt']}"]
    if task.get("repo"):
        parts.append(f"# Repository\n{task['repo']}")

    # Repository context: full snippets for the understand stage, path index otherwise.
    if repo_files:
        if stage["kind"] == StageKind.UNDERSTAND.value:
            snippet_lines = [f"- {f['path']} ({f.get('language') or 'unknown'}, {f.get('size', 0)} bytes)" for f in repo_files[:60]]
            parts.append("# Repository files\n" + "\n".join(snippet_lines))
            sample = [f"### {f['path']}\n```\n{truncate(f.get('content') or '', 1500)}\n```"
                      for f in repo_files[:10] if f.get("content")]
            if sample:
                parts.append("# File samples\n" + "\n\n".join(sample))
        else:
            parts.append("# Repository files\n" + "\n".join(f"- {f['path']}" for f in repo_files[:50]))

    deps = stage.get("dependencies") or []
    if deps:
        context_lines = []
        for d in deps:
            if d in prior_outputs:
                context_lines.append(f"### Stage output ({d[:8]})\n{truncate(prior_outputs[d], 1500)}")
        if context_lines:
            parts.append("# Context from previous stages\n" + "\n\n".join(context_lines))
    parts.append(f"# Stage\n{instruction}")
    if failure_context:
        parts.append(failure_context)
    return "\n\n".join(parts)


async def execute_task(runtime: Runtime, task_id: str, *, on_event: EventCallback | None = None,
                       verify_wait_seconds: int = 0) -> dict:
    db = runtime.db
    task = await store.get_task(db, task_id)
    if task is None:
        raise ValueError("task not found")
    if task["status"] == TaskStatus.AWAITING_APPROVAL.value:
        raise PermissionError("task requires approval before execution")

    plan = await store.get_plan_for_task(db, task_id)
    if plan is None:
        raise ValueError("task has no plan; plan it first")

    stages = [store.stage_dict(s) for s in await store.get_stages(db, plan["id"])]
    repo_files = await store.get_repo_files(db, task_id)
    ws_row = await store.get_workspace_for_task(db, task_id)
    workspace = store.workspace_dict(ws_row) if ws_row else None
    execution_id = await store.create_execution(db, task_id, plan["id"])
    await store.update_task(db, task_id, status=TaskStatus.EXECUTING.value)
    if workspace:
        await store.update_workspace(db, workspace["id"], status="running")
        await store.add_event(db, execution_id, task_id, None, "workspace_attached",
                              f"Workspace attached: provider={workspace['provider']} runner={workspace.get('runner_id') or 'unattached'}",
                              {"workspace_id": workspace["id"]})

    avail = available_providers(runtime)
    order = provider_order(runtime)
    if not avail:
        await store.add_event(db, execution_id, task_id, None, "warning",
                              "No model providers are configured; stages will fail until keys are set.")

    constraints = store.task_dict(task).get("constraints") or {}
    max_attempts = int(constraints.get("max_attempts_per_stage") or runtime.get_int("MAX_ATTEMPTS_PER_STAGE", 2))
    budget_value = constraints.get("budget_usd") or runtime.get_float("DEFAULT_BUDGET_USD", 5.0)
    budget = float(budget_value) if budget_value else None
    if verify_wait_seconds <= 0:
        verify_wait_seconds = int(constraints.get("verify_wait_seconds") or 0)

    started = time.perf_counter()

    ctx = _RunContext(runtime=runtime, task=task, execution_id=execution_id,
                      available_providers=avail, provider_order=order,
                      max_attempts=max_attempts, budget=budget,
                      repo_files=repo_files, verify_wait_seconds=verify_wait_seconds,
                      workspace=workspace, on_event=on_event)
    await ctx.emit("execution_started", f"Executing {len(stages)} stages",
                   {"plan_id": plan["id"], "plan_source": plan.get("source")})

    failed_stages: set[str] = set()
    outputs: dict[str, str] = {}

    for level in topo_levels(stages):
        if ctx.budget_exceeded:
            for s in level:
                await store.update_stage(db, s["id"], status=StageStatus.SKIPPED.value)
                await ctx.emit("stage_skipped", "Skipped: execution budget exceeded", stage_id=s["id"])
            continue

        ready = []
        for s in level:
            deps = s.get("dependencies") or []
            if any(d in failed_stages for d in deps):
                await store.update_stage(db, s["id"], status=StageStatus.BLOCKED.value)
                await ctx.emit("stage_blocked", "Blocked: a dependency failed", stage_id=s["id"])
                failed_stages.add(s["id"])
            else:
                ready.append(s)

        if ready:
            results = await asyncio.gather(*[_run_stage(ctx, s, outputs) for s in ready])
            for s, (ok, out) in zip(ready, results):
                if ok:
                    outputs[s["id"]] = out
                else:
                    failed_stages.add(s["id"])

    await store.update_execution(db, execution_id, attempt_count=ctx.attempt_count,
                                 escalation_count=ctx.escalation_count,
                                 total_cost=round(ctx.spend, 6), total_tokens=ctx.total_tokens)

    success = not ctx.budget_exceeded and len(failed_stages) == 0
    final_status = ExecutionStatus.COMPLETED.value if success else ExecutionStatus.FAILED.value
    task_status = TaskStatus.COMPLETED.value if success else TaskStatus.FAILED.value
    await store.update_execution(db, execution_id, status=final_status, finished_at=now_iso())
    await store.update_task(db, task_id, status=task_status)

    metrics.observe("execution_duration_seconds", time.perf_counter() - started)
    metrics.incr(f"execution_status_{final_status}")

    if ctx.budget_exceeded:
        await ctx.emit("budget_exceeded",
                       f"Execution stopped: estimated cost exceeded budget of ${budget:,.4f}",
                       {"budget_usd": budget, "spent_usd": round(ctx.spend, 6)})
    else:
        await ctx.emit("execution_completed" if success else "execution_failed",
                       f"Execution {final_status}", {"failed_stages": sorted(failed_stages)})

    from reporter import build_summary
    return await build_summary(runtime, execution_id)


class _RunContext:
    def __init__(self, *, runtime: Runtime, task: dict, execution_id: str,
                 available_providers: set[str], provider_order: list[str],
                 max_attempts: int, budget: float | None, repo_files: list[dict],
                 verify_wait_seconds: int, workspace: dict | None, on_event: EventCallback | None):
        self.runtime = runtime
        self.db = runtime.db
        self.task = task
        self.execution_id = execution_id
        self.available_providers = available_providers
        self.provider_order = provider_order
        self.max_attempts = max_attempts
        self.budget = budget
        self.repo_files = repo_files
        self.verify_wait_seconds = verify_wait_seconds
        self.workspace = workspace
        self.workspace_timeout = workspace.get("timeout_seconds", 0) if workspace else 0
        self.on_event = on_event
        self.attempt_count = 0
        self.escalation_count = 0
        self.spend = 0.0
        self.total_tokens = 0
        self.budget_exceeded = False
        self.compact_cache: dict[str, dict] = {}
        self._providers: dict[str, Any] = {}

    def provider_for(self, name: str):
        if name not in self._providers:
            self._providers[name] = build_provider(name, self.runtime)
        return self._providers[name]

    async def emit(self, type_: str, message: str, data: dict | None = None,
                   stage_id: str | None = None) -> None:
        await store.add_event(self.db, self.execution_id, self.task["id"], stage_id,
                              type_, message, data)
        if self.on_event:
            try:
                result = self.on_event({
                    "type": type_, "message": message, "data": data or {},
                    "stage_id": stage_id, "execution_id": self.execution_id,
                    "created_at": now_iso(),
                })
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001 - event delivery must never break execution
                pass


async def _run_stage(ctx: _RunContext, stage: dict, prior_outputs: dict[str, str]) -> tuple[bool, str]:
    db = ctx.db
    task_id = ctx.task["id"]
    risk = ctx.task.get("risk_level") or RiskLevel.MEDIUM.value
    kind = stage["kind"]
    required_caps = {c.value for c in routing.required_capabilities(kind)}

    await store.update_stage(db, stage["id"], status=StageStatus.RUNNING.value)
    await ctx.emit("stage_started", f"Stage: {stage['title']}", {"kind": kind}, stage_id=stage["id"])

    stats = await store.get_routing_stats(db, kind, risk)
    selected, candidates, reasoning = routing.select_model(
        kind, risk, ctx.available_providers, ctx.provider_order, stats=stats)
    if selected is None:
        metrics.incr("routing_no_eligible_model")
        await store.update_stage(db, stage["id"], status=StageStatus.FAILED.value)
        await ctx.emit("stage_failed",
                       "No eligible model: configure a provider with the required capabilities",
                       {"required": reasoning["required_capabilities"]}, stage_id=stage["id"])
        return False, ""

    metrics.incr("routing_decisions_total")
    await store.update_stage(db, stage["id"], assigned_model=selected.id,
                             model_reasoning=json_dumps(reasoning))

    model: ModelSpec = selected
    provider = ctx.provider_for(model.provider)
    # Compact bulky prior-stage context before prompting (token cost stays flat).
    prior_ctx = await _compact_prior_outputs(ctx, stage, prior_outputs, model, provider)
    prompt = _build_prompt(ctx.task, stage, prior_ctx, ctx.repo_files)

    for attempt_number in range(1, ctx.max_attempts + 1):
        # Budget guard: refuse to start an attempt whose projected cost would
        # exceed the remaining budget.
        projected = escalation.attempt_cost(model, escalation.estimate_tokens(prompt), 4096)
        if ctx.budget is not None and ctx.spend + projected > ctx.budget:
            ctx.budget_exceeded = True
            metrics.incr("budget_exceeded_total")
            await store.update_stage(db, stage["id"], status=StageStatus.SKIPPED.value)
            await ctx.emit("stage_skipped", "Skipped: execution budget would be exceeded",
                           {"projected_usd": round(projected, 6), "spent_usd": round(ctx.spend, 6),
                            "budget_usd": ctx.budget}, stage_id=stage["id"])
            return False, ""

        attempt_id = await store.create_attempt(
            db, execution_id=ctx.execution_id, stage_id=stage["id"],
            attempt_number=attempt_number, model_id=model.id, provider=model.provider,
            input_prompt=prompt)
        ctx.attempt_count += 1

        started = time.perf_counter()

        # Hard budget cap: limit output tokens so an attempt can't blow the budget.
        max_tokens = _budget_max_tokens(ctx, model)

        # Agentic tool-use loop when a workspace is attached: the model can
        # inspect the real repository before producing its deliverable.
        agentic_rounds = int((store.task_dict(ctx.task).get("constraints") or {}).get("agentic_rounds") or 0)
        if ctx.workspace is not None and agentic_rounds == 0:
            agentic_rounds = 10

        if ctx.workspace is not None and agentic_rounds > 0 and _tool_callable(model):
            from agent import run_agent_loop
            agent_prompt = prompt
            final_text, tool_usage, agent_error = await run_agent_loop(
                ctx.db, ctx.workspace, ctx.emit, ctx.execution_id,
                stage, attempt_id, ctx.runtime, provider, model, agent_prompt,
                max_rounds=agentic_rounds)
            result = LLMResult(text=final_text, model=model.id, provider=model.provider,
                               tokens_in=escalation.estimate_tokens(agent_prompt),
                               tokens_out=escalation.estimate_tokens(final_text),
                               error=agent_error)
            await store.update_attempt(
                db, attempt_id,
                input_prompt=json_dumps({"prompt": prompt[:1000],
                                         "agent_rounds": len(tool_usage)})[:3000])
        else:
            result = await provider.complete(
                model.id, prompt,
                system=SYSTEM_PROMPT,
                temperature=0.2 if attempt_number == 1 else 0.1,
                max_tokens=max_tokens)
        latency_ms = int((time.perf_counter() - started) * 1000)

        if result.error:
            metrics.incr("provider_errors_total")
            await store.update_attempt(db, attempt_id, status=AttemptStatus.FAILED.value,
                                       error=result.error, latency_ms=latency_ms, finished_at=now_iso())
            await store.upsert_routing_stats(db, stage_kind=kind, risk_level=risk,
                                             model_id=model.id, provider=model.provider,
                                             success=False, latency_ms=latency_ms)
            await ctx.emit("attempt_failed", f"Attempt {attempt_number} failed: {result.error}",
                           {"model": model.id}, stage_id=stage["id"])
            # Cross-provider fallback first (same tier, different provider),
            # then escalate to a stronger model on the next attempt.
            fallback = escalation.fallback_candidates(model, required_caps, ctx.available_providers)
            if fallback:
                fallback_model = fallback[0]
                fallback_result = await ctx.provider_for(fallback_model.provider).complete(
                    fallback_model.id, prompt, system=SYSTEM_PROMPT,
                    temperature=0.2, max_tokens=max_tokens)
                if not fallback_result.error:
                    metrics.incr("provider_fallback_total")
                    await ctx.emit("provider_fallback",
                                   f"Fell back to {fallback_model.id} after {model.provider} error",
                                   {"from": model.id, "to": fallback_model.id}, stage_id=stage["id"])
                    model = fallback_model
                    result = fallback_result
                else:
                    result.error = f"{result.error}; fallback {fallback_model.id}: {fallback_result.error}"
            if result.error and attempt_number < ctx.max_attempts:
                model, _ = escalation.next_model(model, required_caps, ctx.available_providers)
                prompt = _next_prompt(ctx.task, stage, prior_ctx, ctx.repo_files,
                                      [result.error], result.text)
                continue
            if result.error:
                await store.update_stage(db, stage["id"], status=StageStatus.FAILED.value)
                await ctx.emit("stage_failed", f"Stage failed after {attempt_number} attempt(s)",
                               {"model": model.id}, stage_id=stage["id"])
                return False, ""

        tokens_in = result.tokens_in or escalation.estimate_tokens(prompt)
        tokens_out = result.tokens_out or escalation.estimate_tokens(result.text)
        cost = escalation.attempt_cost(model, tokens_in, tokens_out)
        ctx.total_tokens += tokens_in + tokens_out
        ctx.spend += cost

        outcome = verification.verify_stage(kind, stage.get("verification_types") or [], result.text)

        # Execution-environment verification: apply artifacts + run the stage's
        # checks in the workspace, then merge the real results.
        if ctx.workspace is not None and outcome.status != "failed":
            await _dispatch_workspace_ops(ctx, stage, attempt_id, result.text)
            await tools_service.await_tool_results(
                db, ctx.execution_id, timeout_seconds=ctx.workspace_timeout or 60.0)
            reports = await store.get_verification_reports(db, stage["id"], attempt_id=attempt_id)
            outcome = verification.merge_reports(outcome, reports)
            gated = await _stage_approval_gated(db, ctx.execution_id, stage["id"])
            if gated and outcome.status == "passed":
                outcome.status = "limited"
                outcome.limitations.append(
                    f"verification command(s) awaiting approval: {', '.join(gated)}")
        else:
            # No workspace: merge extension-posted reports (and optionally wait).
            reports = await store.get_verification_reports(db, stage["id"], attempt_id=attempt_id)
            if ctx.verify_wait_seconds and outcome.env_tools:
                await _wait_for_reports(ctx, stage["id"], attempt_id, outcome)
                reports = await store.get_verification_reports(db, stage["id"], attempt_id=attempt_id)
            outcome = verification.merge_reports(outcome, reports)

        if outcome.status == "failed":
            metrics.incr("verification_failed_total")
            await store.update_attempt(
                db, attempt_id, status=AttemptStatus.FAILED.value, output=result.text,
                verification_status=outcome.status, verification_output=json_dumps(outcome.as_dict()),
                tokens_in=tokens_in, tokens_out=tokens_out, cost=cost,
                latency_ms=latency_ms, finished_at=now_iso())
            await store.upsert_routing_stats(db, stage_kind=kind, risk_level=risk,
                                             model_id=model.id, provider=model.provider,
                                             success=False, latency_ms=latency_ms)
            await ctx.emit("verification_failed", f"Attempt {attempt_number} failed verification",
                           {"model": model.id, "failures": outcome.failures}, stage_id=stage["id"])
            if attempt_number < ctx.max_attempts:
                model, escalated = escalation.next_model(model, required_caps, ctx.available_providers)
                if escalated:
                    ctx.escalation_count += 1
                    metrics.incr("escalations_total")
                prompt = _next_prompt(ctx.task, stage, prior_ctx, ctx.repo_files,
                                      outcome.failures, result.text)
                continue
            await store.update_stage(db, stage["id"], status=StageStatus.FAILED.value)
            await ctx.emit("stage_failed",
                           f"Stage failed verification after {attempt_number} attempt(s)",
                           {"failures": outcome.failures}, stage_id=stage["id"])
            return False, ""

        # passed or limited -> success (limited is recorded, never claimed as verified).
        await store.update_attempt(
            db, attempt_id, status=AttemptStatus.SUCCEEDED.value, output=result.text,
            verification_status=outcome.status, verification_output=json_dumps(outcome.as_dict()),
            tokens_in=tokens_in, tokens_out=tokens_out, cost=cost,
            latency_ms=latency_ms, finished_at=now_iso())
        await store.upsert_routing_stats(db, stage_kind=kind, risk_level=risk,
                                         model_id=model.id, provider=model.provider,
                                         success=True, latency_ms=latency_ms)

        # Record file artifacts the model named in its output.
        for art in artifacts_domain.parse_artifacts(result.text):
            await store.create_artifact(db, execution_id=ctx.execution_id, stage_id=stage["id"],
                                        path=art["path"], language=art["language"],
                                        source="auto", content=art["content"])

        if outcome.limitations:
            await ctx.emit("verification_limited", "Stage completed with unverified checks",
                           {"limitations": outcome.limitations}, stage_id=stage["id"])
        await store.update_stage(db, stage["id"], status=StageStatus.SUCCEEDED.value)
        await ctx.emit("stage_succeeded", f"Stage succeeded with {model.id}",
                       {"model": model.id, "attempt": attempt_number,
                        "verification": outcome.status, "limitations": outcome.limitations},
                       stage_id=stage["id"])
        return True, result.text

    await store.update_stage(db, stage["id"], status=StageStatus.FAILED.value)
    return False, ""


async def _wait_for_reports(ctx: _RunContext, stage_id: str, attempt_id: str,
                            outcome: verification.VerificationOutcome) -> None:
    """Poll briefly for repo-side verification reports (workflow executions)."""
    deadline = time.monotonic() + ctx.verify_wait_seconds
    while time.monotonic() < deadline:
        await asyncio.sleep(1.0)
        reports = await store.get_verification_reports(ctx.db, stage_id, attempt_id=attempt_id)
        covered = {r["tool"] for r in reports}
        if all(t in covered for t in outcome.env_tools):
            return


async def _dispatch_workspace_ops(ctx: _RunContext, stage: dict, attempt_id: str, output: str) -> None:
    """Send the execution adapter its work for this stage:

    1. apply every parsed artifact (fs.write);
    2. run the stage's mapped verification commands (command.run -> reports).

    Artifacts are discovered in three ways, in order:
    - fenced blocks with file paths (```language:path),
    - OpenAI applypatch-style edits (*** Update File: path),
    - a stage-target fallback: repo paths named in the task/stage context
      receive the extracted code when the model omitted file markers.
    """
    db = ctx.db
    ws = ctx.workspace
    artifacts = artifacts_domain.parse_artifacts(output)
    source = "fence"
    if not artifacts:
        artifacts = artifacts_domain.parse_patches(output)
        source = "patch"
    if not artifacts:
        code = _extract_code_text(output)
        if code:
            targets = artifacts_domain.resolve_target_paths(
                ctx.repo_files, f"{ctx.task['prompt']} {stage.get('description') or ''}")
            if targets:
                artifacts = [{"path": targets[0], "language": None, "content": code}]
                source = "target"

    for art in artifacts:
        await tools_service.dispatch_apply_artifact(
            db, workspace_id=ws["id"], execution_id=ctx.execution_id, stage_id=stage["id"],
            attempt_id=attempt_id, path=art["path"], content=art["content"])

    if not artifacts:
        await ctx.emit("stage_warning",
                       "No file artifacts were detected in the stage output; "
                       "the workspace may not have been modified",
                       {"stage": stage["id"]}, stage_id=stage["id"])
    else:
        await ctx.emit("workspace_ops_dispatched",
                       f"Applied {len(artifacts)} artifact(s) (source: {source})",
                       {"stage": stage["id"], "source": source}, stage_id=stage["id"])

    commands = ws.get("commands") or {}
    for vt in stage.get("verification_types") or []:
        if vt == "runtime":
            # serve -> probe -> stop: verify the app actually runs and responds.
            serve = (commands.get("serve") or {}).get("cmd")
            health = (commands.get("health") or {}).get("cmd")
            if not serve or not health:
                continue  # surfaces as a verification limitation
            start_id = await store.create_tool_request(
                db, workspace_id=ws["id"], execution_id=ctx.execution_id,
                stage_id=stage["id"], attempt_id=attempt_id,
                tool="command.start", params={"cmd": serve}, status="queued")
            await tools_service.dispatch_verification_command(
                db, workspace_id=ws["id"], execution_id=ctx.execution_id,
                stage_id=stage["id"], attempt_id=attempt_id,
                command_key="health", command=health, verify_as="runtime",
                dangerous=False)
            await store.create_tool_request(
                db, workspace_id=ws["id"], execution_id=ctx.execution_id,
                stage_id=stage["id"], attempt_id=attempt_id,
                tool="command.stop", params={"from_request": start_id},
                status="queued")
            continue
        key = tools_domain.command_key_for_verification(vt)
        if not key or key not in commands:
            continue
        spec = commands[key] or {}
        cmd = spec.get("cmd")
        if not cmd:
            continue
        await tools_service.dispatch_verification_command(
            db, workspace_id=ws["id"], execution_id=ctx.execution_id, stage_id=stage["id"],
            attempt_id=attempt_id, command_key=key, command=cmd, verify_as=vt,
            dangerous=bool(spec.get("dangerous")))
    await ctx.emit("workspace_ops_dispatched", "Dispatched workspace operations",
                   {"stage": stage["id"]}, stage_id=stage["id"])


def _extract_code_text(text: str) -> str:
    """Best-effort code extraction: fenced content, or the text itself."""
    if not text:
        return ""
    import re as _re
    fenced = _re.findall(r"```[^\n]*\n(.*?)```", text, _re.DOTALL)
    if fenced:
        return "\n\n".join(fenced).strip()
    return text.strip()


async def _stage_approval_gated(db, execution_id: str, stage_id: str) -> list[str]:
    """Return the commands for a stage that are stuck awaiting approval."""
    rows = await db.query(
        "SELECT * FROM tool_requests WHERE execution_id = ? AND stage_id = ? AND status = 'awaiting_approval'",
        (execution_id, stage_id),
        ("id", "execution_id", "stage_id", "workspace_id", "tool", "params", "verify_as",
         "dangerous", "status", "result", "created_at", "dispatched_at", "finished_at",
         "attempt_id"))
    commands = []
    for r in rows:
        req = store.tool_request_dict(r)
        commands.append((req.get("params") or {}).get("cmd") or req["tool"])
    return commands


def _next_prompt(task: dict, stage: dict, prior_outputs: dict[str, str], repo_files: list[dict],
                 failure_reasons: list[str], prior_output: str | None) -> str:
    return _build_prompt(
        task, stage, prior_outputs, repo_files,
        failure_context=escalation.build_failure_context(failure_reasons, prior_output),
    )