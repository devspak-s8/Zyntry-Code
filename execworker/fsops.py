"""Filesystem operations inside the workspace root (path-confined)."""

import os
import re

MAX_FILE_BYTES = 512 * 1024
MAX_SEARCH_BYTES = 10 * 1024 * 1024


def _resolve(root: str, path: str) -> str:
    """Resolve a workspace-relative path, refusing escapes outside the root."""
    root_real = os.path.realpath(root)
    if os.path.isabs(path):
        candidate = os.path.realpath(path)
    else:
        candidate = os.path.realpath(os.path.join(root, path))
    if not (candidate == root_real or candidate.startswith(root_real + os.sep)):
        raise ValueError(f"path escapes workspace: {path}")
    return candidate


def fs_list(root: str, path: str = ".") -> dict:
    try:
        target = _resolve(root, path or ".")
        entries = []
        for name in sorted(os.listdir(target)):
            full = os.path.join(target, name)
            entries.append({"name": name,
                            "type": "dir" if os.path.isdir(full) else "file",
                            "size": os.path.getsize(full) if os.path.isfile(full) else None})
        return {"entries": entries}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def fs_read(root: str, path: str) -> dict:
    try:
        target = _resolve(root, path)
        if os.path.getsize(target) > MAX_FILE_BYTES:
            return {"error": "file exceeds the maximum readable size"}
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        return {"content": content, "size": len(content)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def fs_write(root: str, path: str, content: str) -> dict:
    try:
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            return {"error": "file exceeds the maximum writable size"}
        target = _resolve(root, path)
        if os.path.exists(target) and os.path.getsize(target) > MAX_FILE_BYTES:
            return {"error": "file exceeds the maximum editable size"}
        before = None
        op = "modify"
        if os.path.exists(target):
            with open(target, "r", encoding="utf-8", errors="replace") as fh:
                before = fh.read()
        else:
            op = "create"
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        return {"files": [{"path": path, "op": op, "before": before, "after": content}]}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def fs_edit(root: str, path: str, search: str, replace: str) -> dict:
    """Line-based replace; fails if the search text is absent or ambiguous."""
    try:
        target = _resolve(root, path)
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            before = fh.read()
        if len(before.encode("utf-8")) > MAX_FILE_BYTES:
            return {"error": "file exceeds the maximum editable size"}
        occurrences = before.count(search)
        if occurrences == 0:
            return {"error": f"search text not found in {path}"}
        if occurrences > 1:
            return {"error": f"search text ambiguous in {path} ({occurrences} occurrences)"}
        after = before.replace(search, replace)
        if len(after.encode("utf-8")) > MAX_FILE_BYTES:
            return {"error": "edited file exceeds the maximum writable size"}
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(after)
        return {"files": [{"path": path, "op": "modify", "before": before, "after": after}]}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def fs_delete(root: str, path: str) -> dict:
    try:
        target = _resolve(root, path)
        if not os.path.exists(target):
            return {"error": f"file not found: {path}"}
        if os.path.getsize(target) > MAX_FILE_BYTES:
            return {"error": "file exceeds the maximum deletable size"}
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            before = fh.read()
        os.remove(target)
        return {"files": [{"path": path, "op": "delete", "before": before, "after": None}]}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def fs_search(root: str, pattern: str, path: str = ".") -> dict:
    try:
        if len(pattern) > 256:
            return {"error": "search pattern is too long"}
        if re.search(r"\([^)]*[+*][^)]*\)[+*]", pattern):
            return {"error": "search pattern is too complex"}
        target = _resolve(root, path or ".")
        regex = re.compile(pattern)
        matches = []
        scanned = 0
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".venv", "__pycache__", ".zyntry-logs")]
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(full)
                    scanned += size
                    if scanned > MAX_SEARCH_BYTES or size > MAX_FILE_BYTES:
                        continue
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        for lineno, line in enumerate(fh, start=1):
                            if regex.search(line):
                                matches.append({"path": os.path.relpath(full, root),
                                                "line": lineno, "text": line.strip()[:200]})
                                if len(matches) >= 200:
                                    return {"matches": matches, "truncated": True}
                except OSError:
                    continue
        return {"matches": matches}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
