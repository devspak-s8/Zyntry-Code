"""Full real demo: token-refresh race fix, end-to-end with a real workspace.

Creates the task, seeds + fixes a real demo TS repo in the workspace (via the
worker), runs lint/type-check commands, executes the plan, and reports files.

Usage: python _run_demo.py [backend_url]
"""

import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"

REPO_FILES = {
    "package.json": '{\n  "name": "demo-auth",\n  "version": "0.1.0",\n  "private": true,\n  "type": "module",\n  "devDependencies": {\n    "typescript": "^5.5.0",\n    "eslint": "^9.0.0",\n    "@typescript-eslint/parser": "^8.0.0",\n    "@typescript-eslint/eslint-plugin": "^8.0.0"\n  }\n}\n',
    "tsconfig.json": '{\n  "compilerOptions": {\n    "target": "ES2022",\n    "module": "ES2022",\n    "moduleResolution": "bundler",\n    "strict": true,\n    "outDir": "dist"\n  },\n  "include": ["src"]\n}\n',
    "eslint.config.js": "import tseslint from '@typescript-eslint/eslint-plugin';\nimport tsparser from '@typescript-eslint/parser';\n\nexport default [\n  { ignores: ['dist/**', 'node_modules/**'] },\n  {\n    files: ['src/**/*.ts'],\n    languageOptions: { parser: tsparser, ecmaVersion: 'latest', sourceType: 'module' },\n    plugins: { '@typescript-eslint': tseslint },\n    rules: { '@typescript-eslint/no-unused-vars': 'warn' },\n  },\n];\n",
    "src/auth/tokens.ts": """export interface TokenPair {
  token: string;
  expiresIn: number;
}

export async function refreshToken(): Promise<TokenPair> {
  const res = await fetch('/api/auth/refresh', { method: 'POST' });
  if (!res.ok) throw new Error(`refresh failed: ${res.status}`);
  return res.json();
}
""",
    "src/auth/session.ts": """import { TokenPair, refreshToken } from './tokens';

/**
 * Session manager with a token-refresh RACE CONDITION:
 * concurrent getToken() calls each trigger an independent refresh,
 * stampeding the refresh endpoint and possibly invalidating tokens.
 */
export class TokenSessionManager {
  private accessToken: string | null = null;
  private expiresAt = 0;

  async getToken(): Promise<string> {
    if (this.accessToken && Date.now() < this.expiresAt) {
      return this.accessToken;
    }
    const pair: TokenPair = await refreshToken();
    this.accessToken = pair.token;
    this.expiresAt = Date.now() + pair.expiresIn * 1000;
    return pair.token;
  }
}
""",
}


def call(method, path, body=None, timeout=90):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def dispatch(ws_id, payload, timeout=120):
    status, resp = call("POST", f"/workspaces/{ws_id}/tool-requests", payload)
    assert status == 200, resp
    req_id = resp["tool_request"]["id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, listing = call("GET", f"/workspaces/{ws_id}/tool-requests")
        req = next((r for r in listing["tool_requests"] if r["id"] == req_id), None)
        if req and req["status"] in ("succeeded", "failed", "timed_out", "cancelled"):
            result = req.get("result") or {}
            return req["status"], result
        time.sleep(2)
    return "timed_out", {}


def main() -> None:
    # 0. Spawn the worker for the duration of the demo (owns its lifetime).
    import os
    import subprocess
    import sys as _sys

    workspaces_root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp",
                                   "opencode", "zyntry-workspaces")
    os.makedirs(workspaces_root, exist_ok=True)
    worker_env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.abspath(__file__)))
    worker = subprocess.Popen(
        [_sys.executable, "-m", "execworker.main", "--backend", BASE,
         "--dir", workspaces_root, "--name", "demo-worker"],
        env=worker_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop_worker():
        worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()

    try:
        _run(task_id_holder := {})
    finally:
        stop_worker()


def _run(task_id_holder: dict) -> None:
    # 1. Task (critical risk -> approval gate).
    status, created = call("POST", "/tasks", {
        "prompt": "Fix the token refresh concurrency race condition in src/auth/session.ts",
        "max_attempts_per_stage": 2, "budget_usd": 1.0}, timeout=180)
    assert status == 200 and "task" in created, created
    task_id = created["task"]["id"]
    print(f"[1] task {task_id} risk={created['task']['risk_level']} requires_approval={created['requires_approval']}")

    # 2. Ingest repo snapshot.
    files = [{"path": p, "language": "typescript" if p.endswith(".ts") else "json",
              "size": len(c), "content": c} for p, c in REPO_FILES.items()]
    status, resp = call("POST", f"/tasks/{task_id}/repo", {"files": files})
    print(f"[2] repo ingested -> {resp.get('files_ingested')} files")

    # 3. Workspace bound to the task.
    status, ws = call("POST", "/workspaces", {
        "task_id": task_id, "provider": "remote",
        "commands": {"type_check": {"cmd": "npx tsc --noEmit"},
                     "lint": {"cmd": "npx eslint src"}},
        "timeout_seconds": 300})
    assert status == 200, ws
    ws_id = ws["id"]
    print(f"[3] workspace {ws_id}")

    # 4. Seed base files via the runner.
    for path, content in REPO_FILES.items():
        st, result = dispatch(ws_id, {"tool": "fs.write",
                                      "params": {"path": path, "content": content}}, timeout=90)
        assert st == "succeeded", f"seed {path}: {st}"
    print("[4] seeded 5 files")

    # 5. Install deps (real command on the worker host).
    st, result = dispatch(ws_id, {"tool": "command.run",
                                  "params": {"cmd": "npm install", "cwd": "."}}, timeout=600)
    print(f"[5] npm install -> {st} exit={result.get('exit_code')}")

    # 6. Approve (critical risk).
    status, _ = call("POST", f"/tasks/{task_id}/approve",
                     {"approved": True, "auto_execute": False})
    print("[6] approved")

    # 7. Execute the plan for real.
    print("[7] executing (this runs real models + workspace checks)…")
    status, summary = call("POST", f"/tasks/{task_id}/execute", timeout=1800)
    print(f"    execution: {summary.get('execution', {}).get('status')}")
    for s in summary.get("stages", []):
        print(f"    - {s['kind']} -> {s['status']} | {s['assigned_model']}")
    print(f"    attempts: {summary.get('attempts')} escalation: {summary.get('escalation', {}).get('occurred')}")
    print(f"    cost: ${summary.get('cost', {}).get('estimated_usd')} tokens: {summary.get('cost', {}).get('total_tokens')}")
    print(f"    limitations: {summary.get('verification', {}).get('limitations')}")
    print(f"    artifacts: {[a['path'] for a in summary.get('artifacts', [])]}")
    print(f"    files_changed: {summary.get('files_changed')}")

    # 8. Show recorded workspace changes.
    exec_id = summary.get("execution", {}).get("id")
    _, changes = call("GET", f"/executions/{exec_id}/changes")
    print("\n[8] workspace changes recorded:")
    for c in changes.get("changes", []):
        print(f"    {c['op']:7} {c['path']}")

    # 9. Verify files on the worker host.
    import glob
    ws_dir = None
    import os
    workspaces_root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "opencode", "zyntry-workspaces")
    for candidate in glob.glob(os.path.join(workspaces_root, ws_id, "**", "*"), recursive=True):
        if os.path.isfile(candidate):
            print(f"[9] file on disk: {candidate.replace(workspaces_root + os.sep, '')}")

    print("\nDEMO COMPLETE")


if __name__ == "__main__":
    main()