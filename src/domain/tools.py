"""Tool catalog for the coding execution environment.

Defines the operations a runner (remote worker or local extension) can perform
in a workspace, which verification tool each command corresponds to, project
command auto-detection, and the danger policy for commands.
"""

from domain.enums import VerificationType

# tool name -> params schema description + whether it mutates state
TOOL_SPECS: dict[str, dict] = {
    "fs.list": {"params": ["path"], "mutates": False},
    "fs.read": {"params": ["path"], "mutates": False},
    "fs.write": {"params": ["path", "content"], "mutates": True},
    "fs.edit": {"params": ["path", "search", "replace"], "mutates": True},
    "fs.delete": {"params": ["path"], "mutates": True},
    "fs.search": {"params": ["pattern", "path"], "mutates": False},
    "fs.search_semantic": {"params": ["query", "top_k"], "mutates": False},
    "git.status": {"params": [], "mutates": False},
    "git.diff": {"params": [], "mutates": False},
    "git.commit": {"params": ["message"], "mutates": True},
    "git.push": {"params": ["remote", "branch"], "mutates": True},
    "github.pr": {"params": ["title", "body", "base", "head"], "mutates": True},
    "command.run": {"params": ["cmd", "cwd", "env"], "mutates": False},
    "command.start": {"params": ["cmd", "cwd", "env"], "mutates": False},
    "command.stop": {"params": ["process_id"], "mutates": False},
    "mcp.list_tools": {"params": ["server"], "mutates": False},
    "mcp.call": {"params": ["server", "tool", "args"], "mutates": False},
    "terminal.start": {"params": ["command", "cwd", "cols", "rows"], "mutates": False},
    "terminal.input": {"params": ["session_id", "data"], "mutates": False},
    "terminal.output": {"params": ["session_id"], "mutates": False},
    "terminal.resize": {"params": ["session_id", "cols", "rows"], "mutates": False},
    "terminal.stop": {"params": ["session_id"], "mutates": False},
}

# verification tool -> workspace command key
VERIFY_TO_COMMAND: dict[str, str] = {
    VerificationType.TESTS.value: "test",
    VerificationType.LINT.value: "lint",
    VerificationType.TYPE_CHECK.value: "type_check",
    VerificationType.BUILD.value: "build",
    VerificationType.VISUAL.value: "visual",
    VerificationType.SECURITY.value: "security",
    VerificationType.BENCHMARK.value: "benchmark",
    VerificationType.RUNTIME.value: "health",   # paired with the "serve" command
    VerificationType.BROWSER.value: "browser",
}

# Tools the agentic loop may call without an approval gate (read-only).
READONLY_TOOLS = {"fs.list", "fs.read", "fs.search", "fs.search_semantic",
                  "git.status", "git.diff", "mcp.list_tools"}

# Additional tools the agentic loop may call (interactive/ecosystem).
AGENT_CALLABLE_TOOLS = READONLY_TOOLS | {
    "command.run", "mcp.call",
}

# command key -> default command patterns by ecosystem
_COMMAND_PATTERNS: dict[str, dict[str, list[str]]] = {
    "python": {
        "test": ["pytest", "python -m pytest", "python -m unittest"],
        "lint": ["ruff check .", "flake8 ."],
        "type_check": ["mypy .", "pyright"],
    },
    "node": {
        "test": ["npm test", "yarn test", "pnpm test", "vitest run"],
        "lint": ["npm run lint", "eslint ."],
        "type_check": ["npx tsc --noEmit"],
        "build": ["npm run build", "yarn build", "pnpm build"],
    },
    "rust": {
        "test": ["cargo test"],
        "lint": ["cargo clippy"],
        "build": ["cargo build"],
    },
    "go": {
        "test": ["go test ./..."],
        "build": ["go build ./..."],
    },
}

# Commands that are always considered dangerous (require explicit approval).
DANGEROUS_PATTERNS: list[str] = [
    "rm -rf", "git push", "git reset --hard", "npm publish", "cargo publish",
    "deploy", "drop table", "drop database", "sudo ", "shutdown", "reboot",
    "curl -X DELETE", "wrangler deploy", "terraform apply", "kubectl delete",
]

_DEFAULT_ALLOWED_PREFIXES: list[str] = [
    "npm", "npx", "yarn", "pnpm", "node", "python", "python3", "pip", "uv",
    "pytest", "ruff", "mypy", "pyright", "flake8", "cargo", "go", "make",
    "git status", "git diff", "git log", "git branch", "git add", "git commit",
    "ls", "dir", "cat", "pwd", "echo", "test", "which", "tsc", "eslint",
]


def detect_ecosystem(repo_files: list[dict]) -> str | None:
    paths = {f.get("path", "") for f in repo_files}
    if any(p.endswith(("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")) for p in paths):
        return "python"
    if any(p.endswith(("package.json", "yarn.lock", "pnpm-lock.yaml", "package-lock.json")) for p in paths):
        return "node"
    if any(p.endswith("Cargo.toml") for p in paths):
        return "rust"
    if any(p.endswith("go.mod") for p in paths):
        return "go"
    return None


def detect_commands(repo_files: list[dict]) -> dict[str, dict]:
    """Guess the project's test/lint/build commands from its files.

    Returns {key: {"cmd": str, "dangerous": bool}} — the detected command is a
    placeholder to be confirmed by the user; nothing runs before it's stored.
    """
    ecosystem = detect_ecosystem(repo_files)
    commands: dict[str, dict] = {}
    if not ecosystem:
        return commands
    for key, patterns in _COMMAND_PATTERNS.get(ecosystem, {}).items():
        for pattern in patterns:
            head = pattern.split()[0]
            present = any(head in f.get("path", "") or f.get("content", "").find(pattern) >= 0
                          for f in repo_files if f.get("content"))
            if present or True:  # first plausible default wins; user can override
                commands[key] = {"cmd": patterns[0], "dangerous": is_dangerous(patterns[0])}
                break
    return commands


def is_dangerous(command: str) -> bool:
    lowered = command.lower().strip()
    return any(d in lowered for d in DANGEROUS_PATTERNS)


def is_allowed(command: str, allowed_commands: list[str]) -> bool:
    if not allowed_commands:
        allowed_commands = _DEFAULT_ALLOWED_PREFIXES
    lowered = command.lower().strip()
    return any(lowered.startswith(a.lower().strip()) for a in allowed_commands)


def command_key_for_verification(verification_type: str) -> str | None:
    return VERIFY_TO_COMMAND.get(verification_type)


def verification_for_command_key(key: str) -> str | None:
    for vt, k in VERIFY_TO_COMMAND.items():
        if k == key:
            return vt
    return None