"""Worker-side command security: allowlist, danger classification, redaction."""

DANGEROUS_PATTERNS = [
    "rm -rf", "git push", "git reset --hard", "npm publish", "cargo publish",
    "deploy", "drop table", "drop database", "sudo ", "shutdown", "reboot",
    "curl -X DELETE", "wrangler deploy", "terraform apply", "kubectl delete",
]

DEFAULT_ALLOWED_PREFIXES = [
    "npm", "npx", "yarn", "pnpm", "node", "python", "python3", "pip", "uv",
    "pytest", "ruff", "mypy", "pyright", "flake8", "cargo", "go", "make",
    "git status", "git diff", "git log", "git branch", "git add", "git commit",
    "ls", "dir", "cat", "pwd", "echo", "test", "which", "tsc", "eslint",
]


def is_dangerous(command: str) -> bool:
    lowered = command.lower().strip()
    return any(d in lowered for d in DANGEROUS_PATTERNS)


def is_allowed(command: str, allowed_commands: list[str] | None = None) -> bool:
    prefixes = allowed_commands or DEFAULT_ALLOWED_PREFIXES
    lowered = command.lower().strip()
    return any(lowered.startswith(p.lower().strip()) for p in prefixes)


def redact(text: str, secrets: list[str]) -> str:
    """Mask secret values so credentials never reach logs or stored results."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text