"""Git operations: checkout, branch isolation, diffs, commits."""

import os
import subprocess
import uuid

from execworker.security import validate_public_url

_ALLOWED_GIT_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}
_SENSITIVE_NAMES = {".env", ".env.local", ".env.production", ".dev.vars", "id_rsa", "id_ed25519"}


def _valid_ref(value: str | None) -> bool:
    return bool(value) and len(value) <= 256 and value[0] not in "-." and ".." not in value \
        and all(char.isalnum() or char in "._/-" for char in value)


def _run_git(cwd: str, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def prepare_workspace(workspaces_dir: str, workspace_id: str, repo_url: str | None,
                      branch: str | None) -> dict:
    """Create the workspace directory; clone the repo if given.

    Returns {workdir, base_commit, branch, repo_initialized}.
    """
    workdir = os.path.join(workspaces_dir, workspace_id)
    os.makedirs(workdir, exist_ok=True)

    if repo_url:
        validate_public_url(repo_url, allowed_hosts=_ALLOWED_GIT_HOSTS)
        if not os.path.exists(os.path.join(workdir, ".git")):
            if branch and not _valid_ref(branch):
                raise ValueError("invalid git branch")
            branch_arg = ["-b", branch] if branch else []
            _run_git(workspaces_dir, "clone", *branch_arg, repo_url, workspace_id, check=True)
            if branch and not branch_arg:
                _run_git(workdir, "checkout", branch, check=True)
        # Isolate work on a fresh branch.
        task_branch = f"zyntry/{uuid.uuid4().hex[:8]}"
        current = _run_git(workdir, "rev-parse", "--abbrev-ref", "HEAD")
        base_branch = current.stdout.strip() or (branch or "main")
        _run_git(workdir, "checkout", "-b", task_branch, check=True)
        base_commit = current_commit(workdir)
        return {"workdir": workdir, "base_commit": base_commit,
                "branch": task_branch, "repo_initialized": True}

    if not os.path.exists(os.path.join(workdir, ".git")):
        _run_git(workdir, "init", "-q", check=True)
        _run_git(workdir, "config", "user.email", "zyntry@local", check=True)
        _run_git(workdir, "config", "user.name", "Zyntry Code", check=True)
        # Initial empty commit gives us a HEAD to diff against.
        _run_git(workdir, "commit", "--allow-empty", "-m", "initial (zyntry)", check=True)
    return {"workdir": workdir, "base_commit": current_commit(workdir),
            "branch": "main", "repo_initialized": True}


def current_commit(workdir: str) -> str | None:
    result = _run_git(workdir, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def git_status(workdir: str) -> dict:
    result = _run_git(workdir, "status", "--porcelain", "--untracked-files=all")
    entries = []
    for line in result.stdout.splitlines():
        if len(line) >= 3:
            entries.append({"status": line[:2].strip(), "path": line[3:]})
    return {"entries": entries}


def git_diff(workdir: str) -> dict:
    """Diff the working tree against HEAD; return structured file changes."""
    status = _run_git(workdir, "status", "--porcelain", "--untracked-files=all")
    changes: list[dict] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        state, path = line[:2].strip(), line[3:]
        if " -> " in path:
            # rename: record the new path as a modify
            path = path.split(" -> ", 1)[1]
            op = "modify"
        elif path.endswith("/"):
            continue  # directory entry (untracked dirs are expanded by --untracked-files=all)
        elif state == "??":
            op, before, after = "create", None, _read(workdir, path)
        elif "D" in state:
            op, before, after = "delete", _show(workdir, path), None
        else:
            op, before, after = "modify", _show(workdir, path), _read(workdir, path)
        changes.append({"path": path, "op": op, "before": before, "after": after})
    patch = _run_git(workdir, "diff", "--stat")
    return {"files": changes, "summary": patch.stdout.strip()}


def _read(workdir: str, path: str) -> str | None:
    try:
        target = os.path.realpath(os.path.join(workdir, path))
        root = os.path.realpath(workdir)
        if not (target == root or target.startswith(root + os.sep)):
            return None
        name = os.path.basename(path).lower()
        if name in _SENSITIVE_NAMES or name.endswith((".pem", ".key", ".p12", ".pfx")):
            return "[REDACTED SENSITIVE FILE]"
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _show(workdir: str, path: str) -> str | None:
    normalized = path.replace("\\", "/")
    parts = {part.lower() for part in normalized.split("/")}
    name = parts and normalized.rsplit("/", 1)[-1].lower()
    if (parts & {".git", ".ssh", ".aws", ".gnupg"}
            or name in _SENSITIVE_NAMES
            or name.endswith((".pem", ".key", ".p12", ".pfx"))):
        return "[REDACTED SENSITIVE FILE]"
    result = _run_git(workdir, "show", f"HEAD:{path}")
    return result.stdout if result.returncode == 0 else None


def git_commit(workdir: str, message: str) -> dict:
    _run_git(workdir, "add", "-A", "--", ":(exclude).zyntry-logs", ":(exclude)**/.zyntry-logs/**")
    result = _run_git(workdir, "commit", "-m", message)
    if result.returncode != 0 and "nothing to commit" not in result.stdout + result.stderr:
        return {"committed": False, "error": result.stderr.strip()}
    return {"committed": True, "head": current_commit(workdir)}


def git_push(workdir: str, remote: str | None = None, branch: str | None = None,
             token: str | None = None) -> dict:
    """Push the current branch. ``token`` (if given) is applied to the push URL
    and never persisted to git config or output."""
    branch = branch or _current_branch(workdir)
    if not _valid_ref(branch):
        return {"pushed": False, "error": "not on a branch"}
    args = ["push"]
    if remote:
        url = remote
        if url.startswith(("https://", "http://")):
            validate_public_url(url, allowed_hosts=_ALLOWED_GIT_HOSTS)
        if token and not url.startswith("https://"):
            return {"pushed": False, "error": "credentialed pushes require an approved HTTPS remote"}
        if token:
            scheme, rest = url.split("://", 1)
            url = f"{scheme}://x-access-token:{token}@{rest}"
        args += [url, f"HEAD:{branch}"]
    else:
        args += ["origin", branch]
    env = dict(os.environ)
    try:
        result = subprocess.run(["git", *args], cwd=workdir, capture_output=True, text=True, env=env)
    except OSError as exc:
        return {"pushed": False, "error": str(exc)}
    if result.returncode != 0:
        # The token is embedded in the push URL; git may echo it. Never leak it.
        error = (result.stderr or result.stdout or "").strip()
        if token:
            error = error.replace(token, "[REDACTED]")
        return {"pushed": False, "error": error}
    return {"pushed": True, "branch": branch}


def _current_branch(workdir: str) -> str | None:
    result = _run_git(workdir, "rev-parse", "--abbrev-ref", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def current_commit_branch(workdir: str) -> str | None:
    return _current_branch(workdir)
