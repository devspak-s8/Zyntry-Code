"""Real workspace demo setup: seed a demo TS repo, ingest it, create the
workspace, and pre-apply the base files via the runner bridge.

Usage: python _seed_workspace.py <task_id> [backend_url]
"""

import json
import sys
import time
import urllib.request

BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8787"
TASK_ID = sys.argv[1]

REPO_FILES = {
    "package.json": '{\n  "name": "demo-auth",\n  "version": "0.1.0",\n  "private": true,\n  "devDependencies": {\n    "typescript": "^5.5.0"\n  }\n}\n',
    "tsconfig.json": '{\n  "compilerOptions": {\n    "target": "ES2022",\n    "module": "ES2022",\n    "moduleResolution": "bundler",\n    "strict": true,\n    "outDir": "dist"\n  },\n  "include": ["src"]\n}\n',
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
    # 1. Ingest the demo repo snapshot into the task.
    files = [{"path": p, "language": "typescript" if p.endswith((".ts", ".tsx")) else "json",
              "size": len(c), "content": c} for p, c in REPO_FILES.items()]
    status, resp = call("POST", f"/tasks/{TASK_ID}/repo", {"files": files})
    print(f"[1] ingest repo -> {status} {resp.get('files_ingested', resp)}")
    assert status == 200

    # 2. Create the workspace bound to the task.
    status, ws = call("POST", "/workspaces", {
        "task_id": TASK_ID, "provider": "remote",
        "commands": {"type_check": {"cmd": "npx tsc --noEmit"},
                     "lint": {"cmd": "npx eslint src"}},
        "timeout_seconds": 300,
    })
    print(f"[2] create workspace -> {status} id={ws.get('id')}")
    assert status == 200
    ws_id = ws["id"]

    # 3. Seed base files through the runner bridge (fs.write tool requests).
    for path, content in REPO_FILES.items():
        status, req = call("POST", f"/workspaces/{ws_id}/tool-requests", {
            "tool": "fs.write",
            "params": {"path": path, "content": content},
        })
        assert status == 200
        print(f"[3] seeded {path} -> {req['tool_request']['status']}")

    # 4. Wait until the runner applies all seeds.
    deadline = time.time() + 60
    while time.time() < deadline:
        status, listing = call("GET", f"/workspaces/{ws_id}/tool-requests")
        reqs = listing.get("tool_requests", [])
        if reqs and all(r["status"] in ("succeeded", "failed", "cancelled") for r in reqs):
            print(f"[4] seeds applied: {len(reqs)} requests terminal")
            break
        time.sleep(1.5)
    else:
        print("[4] WARNING: seeds not terminal within 60s — is the worker running?")
        sys.exit(1)

    print(f"\nWORKSPACE_READY {ws_id}")


if __name__ == "__main__":
    main()