"""Defense-in-depth policy enforced inside the execution worker."""

import ipaddress
import re
import shlex
import socket
import os
from urllib.parse import urlparse

DEFAULT_ALLOWED_PREFIXES = [
    "python", "python -m", "pytest", "npm", "npm test", "npm run",
    "pnpm", "pnpm test", "pnpm run", "yarn", "yarn test", "yarn run",
    "bun", "bun test", "cargo test", "cargo check", "go test", "go vet",
    "make", "ruff", "mypy", "pyright", "flake8", "git status", "git diff",
    "git log", "git branch", "git add", "git commit", "ls", "dir", "cat",
    "pwd", "echo", "test", "which", "tsc", "eslint",
]
DANGEROUS_PATTERNS = [
    "rm -rf", "git push", "git reset --hard", "npm publish", "cargo publish",
    "git restore", "git clean", "chmod", "chown", "curl ", "wget ",
]
_SHELL_META = re.compile(r"[;&|<>`\r\n]|\$\(")
_SENSITIVE_ENV = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|API[_-]?KEY|AUTH|CREDENTIAL|PRIVATE[_-]?KEY|COOKIE)",
    re.IGNORECASE)


def has_shell_metacharacters(command: str) -> bool:
    single = double = escaped = False
    text = command or ""
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and not single:
            escaped = True
            continue
        if char == "'" and not double:
            single = not single
            continue
        if char == '"' and not single:
            double = not double
            continue
        if not single and not double and (char in ";&|<>\r\n" or ord(char) == 96 or text[index:index + 2] == '$('):
            return True
    return single or double


def parse_command(command: str) -> list[str]:
    if not command or has_shell_metacharacters(command):
        raise ValueError("shell syntax is not permitted")
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError("invalid command syntax") from exc
    if not argv:
        raise ValueError("empty command")
    return argv


def is_dangerous(command: str) -> bool:
    lowered = command.lower().strip()
    return has_shell_metacharacters(command) or any(d in lowered for d in DANGEROUS_PATTERNS)


def is_allowed(command: str, allowed_commands: list[str] | None = None) -> bool:
    prefixes = allowed_commands or DEFAULT_ALLOWED_PREFIXES
    try:
        command_tokens = parse_command(command)
    except ValueError:
        return False
    for allowed in prefixes:
        try:
            prefix_tokens = parse_command(allowed)
        except ValueError:
            continue
        if prefix_tokens and [token.lower() for token in command_tokens[:len(prefix_tokens)]] == [token.lower() for token in prefix_tokens]:
            return True
    return False


def redact(text: str, secrets: list[str]) -> str:
    result = text or ""
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


def safe_child_env(extra: dict | None = None) -> dict[str, str]:
    """Build a subprocess environment without worker credentials.

    The worker process itself has backend and runner credentials. Passing the
    full process environment to repository commands or MCP servers would make
    ``env``/diagnostic commands an easy credential-exfiltration primitive.
    Explicit workspace variables are retained because they are part of the
    configured execution contract, but reserved worker variables are never
    inherited or overridden.
    """
    reserved = {"ZYNTRY_TOKEN", "ZYNTRY_RUNNER_TOKEN", "ZYNTRY_API_TOKEN"}
    child: dict[str, str] = {}
    for name, value in os.environ.items():
        if name in reserved or name.upper().startswith("ZYNTRY_") or _SENSITIVE_ENV.search(name):
            continue
        child[name] = value
    for name, value in (extra or {}).items():
        key = str(name)
        if key in reserved or key.upper().startswith("ZYNTRY_"):
            continue
        child[key] = str(value)
    return child


def validate_public_url(url: str, *, allowed_hosts: set[str] | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("only HTTPS URLs are allowed")
    hostname = parsed.hostname.rstrip(".").lower()
    if allowed_hosts and hostname not in allowed_hosts:
        raise ValueError("URL host is not allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
                raise ValueError("URL resolves to a private or reserved address")
    except socket.gaierror as exc:
        raise ValueError("URL host could not be resolved") from exc
    return url
