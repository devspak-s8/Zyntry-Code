"""Probe: what does gpt-5 actually return for the implement stage protocol?"""

import json
import os
import httpx

KEY = os.environ.get("OPENAI_API_KEY")
assert KEY, "OPENAI_API_KEY required"

TOOL_SYSTEM = (
    "You are Zyntry Code, an adaptive AI engineering agent with access to a real "
    "workspace. You can call tools to inspect the repository before answering. "
    "Respond in JSON ONLY:\n"
    '- To use a tool: {"tool": "<name>", "params": {<args>}}\n'
    '- To finish: {"final": "<your deliverable for the stage>"}\n'
    "Available tools: fs.list, fs.read, fs.search, git.status, git.diff, command.run.\n"
    "Inspect first, then answer. When you have what you need, respond with {\"final\": ...} "
    "containing your stage deliverable exactly as requested by the stage instructions."
    " If your stage requires code, the final must include the complete code in fenced blocks "
    "(```typescript:src/auth/session.ts)."
)

TASK = (
    "# Task\nFix the token refresh concurrency race condition in src/auth/session.ts\n\n"
    "# Repository files\n- src/auth/session.ts\n- src/auth/tokens.ts\n\n"
    "# Stage\nImplement the change. Output the resulting code.\n\n"
    "[TOOL RESULT for fs.read]\n"
    '{"status": "succeeded", "content": "import { TokenPair, refreshToken } from \'./tokens\';\n\nexport class TokenSessionManager {\n  private accessToken: string | null = null;\n  private expiresAt = 0;\n\n  async getToken(): Promise<string> {\n    if (this.accessToken && Date.now() < this.expiresAt) {\n      return this.accessToken;\n    }\n    const pair: TokenPair = await refreshToken();\n    this.accessToken = pair.token;\n    this.expiresAt = Date.now() + pair.expiresIn * 1000;\n    return pair.token;\n  }\n}"}'
)

resp = httpx.post(
    "https://api.openai.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    json={
        "model": "gpt-5",
        "messages": [
            {"role": "system", "content": TOOL_SYSTEM},
            {"role": "user", "content": TASK},
        ],
    },
    timeout=180,
)
data = resp.json()
print("status:", resp.status_code)
text = data["choices"][0]["message"]["content"] if resp.status_code == 200 else json.dumps(data)[:400]
print("----- output -----")
print(text[:3000])
print("----- ends -----")