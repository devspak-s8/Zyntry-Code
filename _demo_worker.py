"""Live demo: backend + real worker over HTTP (no LLM keys needed).

1. Start the backend:  uvicorn local.dev:app --port 8787
2. Run:               python _demo_worker.py

Creates a workspace, dispatches an allowed command and a dangerous command,
runs the actual worker binary against the backend, and shows the results —
real command execution, the approval gate, and the report loop.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
PROJECT = os.path.dirname(os.path.abspath(__file__))


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def main() -> None:
    # 1. Workspace.
    status, ws = call("POST", "/workspaces", {"provider": "remote", "timeout_seconds": 60})
    assert status == 200, ws
    ws_id = ws["id"]
    print(f"[1] workspace created: {ws_id}")

    # 2. Allowed command -> queued.
    status, allowed = call("POST", f"/workspaces/{ws_id}/tool-requests",
                           {"command": 'python -c "print(\'hello from workspace\')"'})
    print(f"[2] allowed command dispatch -> {allowed['tool_request']['status']}")
    assert allowed["tool_request"]["status"] == "queued"

    # 3. Dangerous command -> held for approval.
    status, dangerous = call("POST", f"/workspaces/{ws_id}/tool-requests",
                             {"command": "git push origin main"})
    print(f"[3] dangerous command dispatch -> {dangerous['tool_request']['status']}")
    assert dangerous["tool_request"]["status"] == "awaiting_approval"

    # 4. Run the real worker (once).
    tmp = tempfile.mkdtemp(prefix="zyntry-ws-", dir=os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp", "opencode"))
    env = dict(os.environ, PYTHONPATH=PROJECT)
    result = subprocess.run(
        [sys.executable, "-m", "execworker.main", "--backend", BASE, "--once",
         "--dir", tmp, "--verbose"],
        cwd=PROJECT, env=env, capture_output=True, text=True, timeout=120)
    print(f"[4] worker exit code: {result.returncode}")
    if result.stdout.strip():
        print(result.stdout.strip())

    # 5. Results.
    _, pending = call("GET", f"/workspaces/{ws_id}/tool-requests")
    for req in pending["tool_requests"]:
        if req["id"] == allowed["tool_request"]["id"]:
            res = req.get("result") or {}
            print(f"[5] {req['tool']} {req['params'].get('cmd')[:40]} -> {req['status']}"
                  f" exit={res.get('exit_code')} stdout={res.get('stdout', '').strip()!r}")
            assert req["status"] == "succeeded", req
            assert res.get("exit_code") == 0

    dangerous_status = [r for r in pending["tool_requests"]
                        if r["id"] == dangerous["tool_request"]["id"]][0]["status"]
    print(f"[6] dangerous command still: {dangerous_status}")
    assert dangerous_status == "awaiting_approval"

    print("\nDEMO OK — worker executed a real command on this machine via the backend bridge.")


if __name__ == "__main__":
    main()