"""Fake MCP stdio server used by the MCP client tests (not collected by pytest)."""

import json
import sys


def _send(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except ValueError:
            continue
        method = req.get("method", "")
        if method.startswith("notifications/"):
            continue  # MCP notifications have no response
        req_id = req.get("id", 1)
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": req_id,
                   "result": {"protocolVersion": "2025-03-26",
                              "capabilities": {"tools": {}},
                              "serverInfo": {"name": "fake-mcp", "version": "1.0"}}})
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
                {"name": "echo", "description": "echo text back",
                 "inputSchema": {"type": "object",
                                 "properties": {"text": {"type": "string"}}}},
            ]}})
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name", "")
            if tool_name != "echo":
                _send({"jsonrpc": "2.0", "id": req_id,
                       "error": {"code": -32601, "message": f"tool not found: {tool_name}"}})
                continue
            args = params.get("arguments", {})
            _send({"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": f"echoed:{args.get('text', '')}"}]}})
        else:
            _send({"jsonrpc": "2.0", "id": req_id,
                   "error": {"code": -32601, "message": f"unknown method: {method}"}})


if __name__ == "__main__":
    main()