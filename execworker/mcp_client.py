"""Minimal MCP (Model Context Protocol) client for the worker.

Supports both transports:
- ``stdio``  — spawn a server command (npx/python/...), speak newline-delimited
  JSON-RPC over stdin/stdout;
- ``http``   — Streamable HTTP transport (JSON-RPC POST, SSE responses).

One initialize handshake per call keeps sessions short-lived and stateless
(acceptable for tool-call workloads; a long-lived session can be added later).
"""

import asyncio
import json
import os
import sys

import httpx

_PROTOCOL_VERSION = "2025-03-26"


class McpError(Exception):
    pass


def _request(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    payload: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def _parse_response(line: str) -> dict:
    data = json.loads(line)
    if "error" in data and data["error"]:
        raise McpError(str(data["error"]))
    return data.get("result") or {}


async def _stdio_rpc(server: dict, method: str, params: dict | None) -> dict:
    command = server.get("command") or "python"
    args = server.get("args") or []
    if server.get("command") == "python":
        args = ["-m"] + args if not args else args
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (server.get("env") or {}).items()})

    proc = await asyncio.create_subprocess_exec(
        command, *args, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=env)

    try:
        writer = proc.stdin
        reader = proc.stdout
        assert writer is not None and reader is not None

        async def call(method: str, params: dict | None) -> dict:
            payload = _request(method, params, request_id=1)
            writer.write((json.dumps(payload) + "\n").encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=60.0)
            if not line:
                raise McpError("MCP server closed stdout")
            return _parse_response(line.decode())

        await call("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "zyntry-execworker", "version": "1.0"},
        })
        writer.write((json.dumps(_request("notifications/initialized", request_id=0)) + "\n").encode())
        await writer.drain()
        return await call(method, params)
    finally:
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            try:
                events.append(json.loads(payload))
            except ValueError:
                continue
    return events


async def _http_rpc(server: dict, method: str, params: dict | None) -> dict:
    url = server.get("url")
    if not url:
        raise McpError("http MCP server requires a url")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": _PROTOCOL_VERSION,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            init_resp = await client.post(url, json=_request("initialize", {
                "protocolVersion": _PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "zyntry-execworker", "version": "1.0"}}),
                headers=headers)
            session_id = init_resp.headers.get("mcp-session-id")
            if session_id:
                headers["mcp-session-id"] = session_id
            await client.post(url, json=_request("notifications/initialized", request_id=0),
                              headers=headers)
            resp = await client.post(url, json=_request(method, params, request_id=2),
                                     headers=headers)
        if resp.status_code >= 400:
            raise McpError(f"mcp http error {resp.status_code}: {resp.text[:300]}")
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            events = _parse_sse_events(resp.text)
            for event in events:
                if "result" in event:
                    return event["result"]
                if "error" in event and event.get("error"):
                    raise McpError(str(event["error"]))
            raise McpError("no result in MCP SSE response")
        data = resp.json()
        if "error" in data and data.get("error"):
            raise McpError(str(data["error"]))
        return data.get("result") or {}
    except httpx.HTTPError as exc:
        raise McpError(f"mcp http transport failed: {exc}") from exc


async def mcp_call(server: dict, method: str, params: dict | None = None) -> dict:
    """Call an MCP method on a configured server. Raises McpError on failure."""
    if (server.get("transport") or "stdio") == "http":
        return await _http_rpc(server, method, params)
    return await _stdio_rpc(server, method, params)


async def list_tools(server: dict) -> list[dict]:
    result = await mcp_call(server, "tools/list")
    return result.get("tools") or []


async def call_tool(server: dict, tool: str, args: dict | None = None) -> dict:
    result = await mcp_call(server, "tools/call", {
        "name": tool, "arguments": args or {}})
    content = result.get("content") or []
    text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
    return {
        "output": "\n".join(text_parts),
        "isError": bool(result.get("isError", False)),
        "structured": result,
    }