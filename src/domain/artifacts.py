"""Artifact handling: parsing files/patches out of model output.

Recognizes the common fenced-block convention where a language tag includes a
file path:  ```python:src/app.py
"""

import re

_FENCE_RE = re.compile(
    r"```([\w+#.-]+):([^\s`]+)\s*\n(.*?)```",
    re.DOTALL,
)


def parse_artifacts(text: str | None, max_artifacts: int = 50) -> list[dict]:
    """Extract file artifacts from model output.

    Returns a list of {path, language, content} dicts. Only fenced blocks that
    name a file path are treated as artifacts.
    """
    artifacts: list[dict] = []
    if not text:
        return artifacts
    for match in _FENCE_RE.finditer(text):
        language = match.group(1)
        path = match.group(2).strip()
        content = match.group(3).rstrip()
        if not path or not content:
            continue
        artifacts.append({"path": path, "language": language, "content": content})
        if len(artifacts) >= max_artifacts:
            break
    return artifacts


_PATCH_FILE_RE = re.compile(r"^\*\*\*\s*(?:Update|Add|Create)\s+File:\s*(\S+)\s*$", re.MULTILINE)
_PATCH_END_RE = re.compile(r"^\*\*\*", re.MULTILINE)


def parse_patches(text: str | None, max_patches: int = 20) -> list[dict]:
    """Extract OpenAI ``applypatch`` style edits::

        *** Begin Patch
        *** Update File: src/auth/session.ts
        @@
        -old line
        +new line
        *** End Patch

    The ``+`` lines (and un-prefixed context) become the new file content.
    """
    if not text:
        return []
    patches: list[dict] = []
    matches = list(_PATCH_FILE_RE.finditer(text))
    for i, match in enumerate(matches):
        path = match.group(1)
        block_start = match.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[block_start:block_end]
        lines = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("@@") or stripped == "":
                continue
            if stripped.startswith("***"):
                break
            if stripped.startswith("+") and not stripped.startswith("+++"):
                lines.append(line[1:])
            elif stripped.startswith("-"):
                continue
            else:
                lines.append(line)
        content = "\n".join(lines).rstrip() + "\n"
        if content.strip():
            patches.append({"path": path, "language": guess_language(path),
                            "content": content})
        if len(patches) >= max_patches:
            break
    return patches


def guess_language(path: str) -> str | None:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "ts": "typescript", "tsx": "typescript", "js": "javascript", "jsx": "javascript",
        "py": "python", "go": "go", "rs": "rust", "json": "json", "css": "css",
        "html": "html", "sql": "sql", "md": "markdown", "sh": "shell", "yml": "yaml",
        "yaml": "yaml", "toml": "toml",
    }.get(ext)


def resolve_target_paths(repo_files: list[dict], context: str) -> list[str]:
    """Repo paths mentioned in the task/stage context (longest match first)."""
    paths = [f.get("path", "") for f in repo_files if f.get("path")]
    hits = [p for p in paths if p and p in (context or "")]
    hits.sort(key=len, reverse=True)
    return hits[:5]