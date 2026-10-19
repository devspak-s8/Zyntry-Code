"""Complete the demo repo: eslint flat config + deps, then npm install.

Usage: python _fix_workspace.py <workspace_id>
"""

import json
import sys
import time
import urllib.request

BASE = "http://localhost:8787"
WS_ID = sys.argv[1]

FIXES = {
    "package.json": json.dumps({
        "name": "demo-auth",
        "version": "0.1.0",
        "private": True,
        "type": "module",
        "devDependencies": {
            "typescript": "^5.5.0",
            "eslint": "^9.0.0",
            "@typescript-eslint/parser": "^8.0.0",
            "@typescript-eslint/eslint-plugin": "^8.0.0",
        },
    }, indent=2) + "\n",
    "eslint.config.js": """import tseslint from '@typescript-eslint/eslint-plugin';
import tsparser from '@typescript-eslint/parser';

export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  {
    files: ['src/**/*.ts'],
    languageOptions: { parser: tsparser, ecmaVersion: 'latest', sourceType: 'module' },
    plugins: { '@typescript-eslint': tseslint },
    rules: { '@typescript-eslint/no-unused-vars': 'warn' },
  },
];
""",
}


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=600) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def dispatch_and_wait(payload, label, timeout=300):
    status, resp = call("POST", f"/workspaces/{WS_ID}/tool-requests", payload)
    assert status == 200, resp
    req_id = resp["tool_request"]["id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, listing = call("GET", f"/workspaces/{WS_ID}/tool-requests")
        req = next((r for r in listing["tool_requests"] if r["id"] == req_id), None)
        if req and req["status"] in ("succeeded", "failed", "timed_out", "cancelled"):
            result = req.get("result") or {}
            print(f"[fix] {label} -> {req['status']} exit={result.get('exit_code')} "
                  f"stderr={str(result.get('stderr', ''))[:200]}")
            return req["status"] == "succeeded"
        time.sleep(2)
    print(f"[fix] {label} -> TIMEOUT")
    return False


def main() -> None:
    for path, content in FIXES.items():
        dispatch_and_wait({"tool": "fs.write",
                           "params": {"path": path, "content": content}},
                          f"write {path}", timeout=120)
    ok = dispatch_and_wait({"tool": "command.run",
                            "params": {"cmd": "npm install", "cwd": "."}},
                           "npm install", timeout=600)
    if not ok:
        sys.exit(1)
    print("DEMO_REPO_FIXED")


if __name__ == "__main__":
    main()