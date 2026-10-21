"""Agentic tool-use loop.

When a workspace is attached, the stage's model becomes an *agent*: it can
inspect the real repository (fs.list/read/search, git.status/diff) and run
allowed commands before producing its final deliverable. Each tool call is
dispatched through the runner bridge, and the real result is fed back into the
conversation, so the model reasons over actual code — not a snapshot.

Safety: only read-only tools are ungated; ``command.run`` goes through the
approval policy, and file writes remain the executor's artifact flow.
"""

import asyncio
import json
import re
import time
from typing import Any

from domain import tools as tools_domain
from metrics import metrics
import store
import tools_service

TOOL_SYSTEM = (
    "You are Zyntry Code, an adaptive AI engineering agent with access to a real "
    "workspace. You can call tools to inspect the repository before answering. "
    "Respond in JSON ONLY:\n"
    '- To use a tool: {"tool": "<name>", "params": {<args>}}\n'
    '- To finish: {"final": "<your deliverable for the stage>"}\n'
    "Available tools:\n"
    "- fs.list {path} — list directory entries\n"
    "- fs.read {path} — read a file\n"
    "- fs.search {pattern, path} — regex search across files\n"
    "- fs.search_semantic {query, top_k} — semantic search over the indexed repo\n"
    "- git.status {} — working tree status\n"
    "- git.diff {} — diff against HEAD\n"
    "- mcp.list_tools {server} — list tools exposed by a configured MCP server\n"
    "- mcp.call {server, tool, args} — call a tool on a configured MCP server\n"
    "- command.run {cmd} — run a command (subject to the approval policy)\n"
    "Inspect first, then answer. Use at most a handful of tool calls. When you "
    "have what you need, respond with {\"final\": ...} containing your stage "
    "deliverable exactly as requested by the stage instructions."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
MAX_TOOL_ROUNDS = 8


def parse_agent_reply(text: str) -> dict | None:
    """Parse the model's JSON reply into {tool, params} or {final, ...}."""
    if not text:
        return None
    match = _JSON_RE.search(text.strip())
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if "final" in data:
        return {"final": str(data["final"])}
    if "tool" in data and isinstance(data.get("params", {}), dict):
        return {"tool": str(data["tool"]), "params": data["params"]}
    return None


async def run_agent_loop(db, workspace, emit, execution_id, stage, attempt_id,
                         runtime, provider, model: Any, prompt: str, max_rounds: int = 6,
                         per_round_timeout: float = 60.0) -> tuple[str, list[dict], str | None]:
    """Run the tool-use loop for one stage attempt.

    ``emit`` is an optional async ``(type_, message, data, stage_id)`` callback
    used for progress events; ``workspace`` may be None (tools disabled — the
    loop then degrades to a single model call).

    Returns ``(final_text, tool_usage, error)`` where tool_usage is a list of
    {tool, params, status} records for the audit trail.
    """
    history: list[dict] = [{"role": "user", "content": prompt}]
    usage: list[dict] = []

    if workspace is None:
        reply = await provider.complete(model.id, prompt, system=TOOL_SYSTEM, temperature=0.1)
        return (reply.text or prompt, usage, reply.error)

    ws = workspace
    last_call: tuple | None = None
    for _round in range(max_rounds):
        is_last = _round == max_rounds - 1
        content = _history_text(history)
        if is_last:
            content += (
                "\n\nYou have almost used your entire tool-call budget. "
                "Do not call any more tools. Respond NOW with "
                "{\"final\": ...} containing your stage deliverable. If the stage "
                "requires code, the final must include the complete code in fenced "
                "blocks (```language:path/to/file).")
        reply = await provider.complete(
            model.id, content,
            system=TOOL_SYSTEM, temperature=0.1)
        if reply.error:
            return prompt, usage, reply.error

        parsed = parse_agent_reply(reply.text)
        if parsed is None:
            # Providers that do not implement the JSON tool protocol may still
            # return a valid plain-text stage answer.  Preserve that answer and
            # let the normal artifact/verification pipeline handle it instead
            # of turning a protocol mismatch into a failed execution.
            if not usage:
                return reply.text, usage, None
            if is_last:
                return reply.text, usage, "agent produced unparseable output"
            history.append({"role": "user", "content":
                            "Your response was not valid JSON. Respond with exactly "
                            "{\"final\": ...} or {\"tool\": ..., \"params\": ...} — "
                            "escape newlines inside strings with \\n."})
            continue
        if "final" in parsed:
            final = parsed["final"]
            return final, usage, None

        call_key = (parsed.get("tool"), json.dumps(parsed.get("params"), sort_keys=True))
        if call_key == last_call:
            # Same tool call twice in a row: the model is looping. Force finalize.
            history.append({"role": "user", "content":
                            "You just made that exact tool call and already received its "
                            "result. Do NOT repeat tool calls. Respond now with "
                            "{\"final\": ...} containing your stage deliverable."})
            continue
        last_call = call_key
        if is_last:
            # Still a tool call on the final round: fail this attempt so the
            # retry/escalation loop can take over with the failure evidence.
            return reply.text, usage, "agent did not produce a final answer after exhausting tool rounds"
        if parsed["tool"] not in tools_domain.TOOL_SPECS:
            history.append({"role": "user", "content": f"Unknown tool {parsed['tool']!r}. "
                            "Use one of: fs.list, fs.read, fs.search, git.status, git.diff, command.run."})
            continue

        tool = parsed["tool"]
        params = parsed["params"]
        if tool not in tools_domain.AGENT_CALLABLE_TOOLS:
            history.append({"role": "user", "content": f"Tool {tool!r} is not available for inspection. "
                            "Use one of: fs.list, fs.read, fs.search, git.status, git.diff, "
                            "mcp.list_tools, mcp.call, terminal.*, command.run."})
            continue

        # MCP tools may only target servers configured on this workspace.
        if tool.startswith("mcp."):
            server_name = str(params.get("server", ""))
            configured = {s.get("name") for s in (ws.get("mcp_servers") or [])}
            if server_name not in configured:
                history.append({"role": "user", "content":
                                f"MCP server {server_name!r} is not configured. "
                                f"Configured servers: {sorted(configured)}"})
                continue

        metrics.incr("agent_tool_calls_total")
        # Semantic repo search resolves inline on the backend (it owns the
        # index + embedding providers) — no runner round-trip.
        if tool == "fs.search_semantic":
            try:
                from semantic import search_query
                results = await search_query(
                    runtime, ws["id"], str(params.get("query", "")),
                    top_k=int(params.get("top_k", 5)))
                result_text = {"status": "succeeded", "results": results}
            except Exception as exc:  # noqa: BLE001
                result_text = {"status": "failed", "error": str(exc)}
            usage.append({"tool": tool, "params": params, "status": result_text["status"]})
            history.append({"role": "user", "content": _format_tool_result(tool, result_text)})
            if emit:
                try:
                    result = emit("agent_tool_call", f"Agent called {tool}",
                                  {"tool": tool, "inline": True}, (stage or {}).get("id"))
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:  # noqa: BLE001
                    pass
            continue

        if tool in tools_domain.READONLY_TOOLS:
            request_id = await tools_service.dispatch_readonly_tool(
                db, workspace_id=ws["id"], execution_id=execution_id,
                stage_id=(stage or {}).get("id"), attempt_id=attempt_id, tool=tool, params=params)
        else:  # commands / mcp / terminals -> security policy or trusted dispatch
            req = await tools_service.dispatch_agent_tool(
                db, workspace_id=ws["id"], execution_id=execution_id,
                stage_id=(stage or {}).get("id"), attempt_id=attempt_id,
                tool=tool, params=params,
                allowed_commands=ws.get("allowed_commands") or [])
            request_id = req["id"]

        result_text = await _wait_for_result(db, request_id, per_round_timeout)
        usage.append({"tool": tool, "params": params, "status": result_text["status"]})
        history.append({"role": "user", "content": _format_tool_result(tool, result_text)})
        if emit:
            try:
                result = emit("agent_tool_call", f"Agent called {tool}", {"tool": tool},
                              (stage or {}).get("id"))
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001
                pass

    # Max rounds reached: force a final answer instead of failing.
    metrics.incr("agent_rounds_exhausted_total")
    final_reply = await provider.complete(
        model.id,
        _history_text(history) + "\n\nYou have used your entire tool-call budget. "
        "Respond NOW with {\"final\": ...} containing your stage deliverable. "
        "Do not call any more tools. If your stage requires code, the final "
        "must include the complete code in fenced blocks (```language:path/to/file).",
        system=TOOL_SYSTEM, temperature=0.1)
    if final_reply.error:
        return prompt, usage, final_reply.error
    parsed = parse_agent_reply(final_reply.text)
    if parsed and "tool" in parsed:
        return final_reply.text, usage, \
            "agent did not produce a final answer after exhausting tool rounds"
    final = parsed["final"] if parsed and "final" in parsed else final_reply.text
    return final, usage, None


def _history_text(history: list[dict]) -> str:
    return "\n\n".join(turn["content"] for turn in history)


def _format_tool_result(tool: str, result: dict) -> str:
    payload = json.dumps(result, default=str)[:3000]
    return f"[TOOL RESULT for {tool}]\n{payload}"


async def _wait_for_result(db, request_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        req = store.tool_request_dict(await store.get_tool_request(db, request_id))
        if req and req["status"] in ("succeeded", "failed", "timed_out", "cancelled", "awaiting_approval"):
            result = req.get("result") or {}
            result.setdefault("status", req["status"])
            return result
        await asyncio.sleep(0.5)
    return {"status": "timed_out", "error": "tool result wait timed out"}
