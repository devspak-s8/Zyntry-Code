"""Tests for the remote worker's executors (fs, commands, git) in real temp dirs."""

import os
import subprocess

import pytest

from execworker import commandops, fsops, gitops, security


def subprocess_run(*args, **kwargs):
    return subprocess.run(*args, capture_output=True, text=True, **kwargs)


@pytest.fixture
def tmp_root(tmp_path):
    return str(tmp_path)


# ---- filesystem -------------------------------------------------------------

def test_fs_write_read_edit_delete_roundtrip(tmp_root):
    result = fsops.fs_write(tmp_root, "src/app.py", "def a():\n    return 1\n")
    assert "files" in result
    assert result["files"][0]["op"] == "create"

    read = fsops.fs_read(tmp_root, "src/app.py")
    assert read["content"].startswith("def a")

    edit = fsops.fs_edit(tmp_root, "src/app.py", "return 1", "return 2")
    assert "files" in edit
    assert "return 2" in fsops.fs_read(tmp_root, "src/app.py")["content"]

    deleted = fsops.fs_delete(tmp_root, "src/app.py")
    assert deleted["files"][0]["op"] == "delete"
    assert "error" in fsops.fs_read(tmp_root, "src/app.py")


def test_fs_edit_rejects_absent_and_ambiguous(tmp_root):
    fsops.fs_write(tmp_root, "a.py", "x x")
    assert "error" in fsops.fs_edit(tmp_root, "a.py", "missing", "y")       # not found
    assert "error" in fsops.fs_edit(tmp_root, "a.py", "x", "y")             # ambiguous


def test_fs_path_confined_to_root(tmp_root):
    outside = os.path.join(os.path.dirname(tmp_root), "outside.txt")
    assert "error" in fsops.fs_read(tmp_root, outside)
    assert "error" in fsops.fs_read(tmp_root, "../outside.txt")


def test_fs_search(tmp_root):
    fsops.fs_write(tmp_root, "src/a.py", "def alpha():\n    pass\n")
    fsops.fs_write(tmp_root, "src/b.py", "def beta():\n    pass\n")
    result = fsops.fs_search(tmp_root, "alpha", ".")
    assert len(result["matches"]) == 1
    assert result["matches"][0]["path"] == os.path.join("src", "a.py")


# ---- commands ---------------------------------------------------------------

async def test_run_command_captures_output():
    result = await commandops.run_command(".", "echo hello", timeout=30)
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


async def test_run_command_failure_exit_code():
    result = await commandops.run_command(".", "python -c \"import sys; sys.exit(3)\"", timeout=30)
    assert result["exit_code"] == 3


async def test_run_command_timeout_kills_process():
    result = await commandops.run_command(".", "python -c \"import time; time.sleep(30)\"", timeout=1.0)
    assert result["timed_out"] is True


async def test_command_secret_redaction():
    result = await commandops.run_command(
        ".", "echo the-token-is-abc123", timeout=30, secrets=["abc123"])
    assert "abc123" not in result["stdout"]
    assert "[REDACTED]" in result["stdout"]


async def test_start_stop_background(tmp_root):
    started = await commandops.start_command(tmp_root, "python -m http.server 0")
    assert "process_id" in started
    stopped = await commandops.stop_command(started["process_id"])
    assert stopped["stopped"] is True


# ---- resource limits (POSIX-only, kernel-enforced) ---------------------------

_RLIMIT_POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="rlimits are POSIX-only")


@_RLIMIT_POSIX_ONLY
async def test_rlimit_cpu_bomb_is_killed_by_kernel():
    """A `while True` loop is killed by RLIMIT_CPU before it can burn the host."""
    result = await commandops.run_command(
        ".", "python -c \"while True: pass\"", timeout=60, cpu_limit=1.0)
    assert result["rlimits"]["enforced"] is True
    assert result["exit_code"] != 0
    assert result["killed_by_signal"] is True
    assert not result["timed_out"]     # the kernel killed it, not our timeout


@_RLIMIT_POSIX_ONLY
async def test_rlimit_memory_bomb_is_killed_by_kernel():
    """A memory bomb is stopped by RLIMIT_AS before it can exhaust the host."""
    result = await commandops.run_command(
        ".", "python -c \"a=[]\nwhile True:\n a.append(bytearray(8*1024*1024))\"",
        timeout=60, mem_limit_mb=128)
    assert result["rlimits"]["enforced"] is True
    assert result["exit_code"] != 0
    assert not result["timed_out"]


async def test_rlimits_reported_and_skipped_off_posix():
    """Without limits, commands run normally and the result reports enforcement."""
    result = await commandops.run_command(".", "echo ok", timeout=30)
    assert result["exit_code"] == 0
    assert "rlimits" in result
    if os.name == "nt":
        assert result["rlimits"]["enforced"] is False


# ---- git --------------------------------------------------------------------

def test_git_prepare_diff_commit(tmp_root):
    ws_dir = os.path.join(tmp_root, "ws")
    prepared = gitops.prepare_workspace(tmp_root, "ws", None, None)
    assert prepared["repo_initialized"]
    assert prepared["base_commit"]

    fsops.fs_write(ws_dir, "src/app.py", "def app():\n    return 1\n")
    diff = gitops.git_diff(ws_dir)
    assert any(f["path"] == "src/app.py" and f["op"] == "create" for f in diff["files"])

    status = gitops.git_status(ws_dir)
    assert any("src/app.py" in e["path"] for e in status["entries"])

    commit = gitops.git_commit(ws_dir, "add app")
    assert commit["committed"] is True
    assert commit["head"]

    # After commit, the working tree is clean.
    assert gitops.git_diff(ws_dir)["files"] == []


def test_git_push_to_bare_remote(tmp_root):
    remote_dir = os.path.join(tmp_root, "remote.git")
    subprocess_run(["git", "init", "--bare", "-q", remote_dir], check=True)

    prepared = gitops.prepare_workspace(tmp_root, "ws", None, None)
    workdir = prepared["workdir"]
    fsops.fs_write(workdir, "src/app.py", "def app():\n    return 1\n")
    assert gitops.git_commit(workdir, "add app")["committed"] is True

    pushed = gitops.git_push(workdir, remote=remote_dir, branch="main")
    assert pushed["pushed"] is True
    # The branch now exists in the bare remote.
    refs = subprocess_run(["git", "--git-dir", remote_dir, "branch", "--format=%(refname:short)"])
    assert "main" in refs.stdout


def test_git_push_embeds_token_in_url_only(tmp_root):
    # Token is applied to the push URL and must never appear in errors/reporting.
    not_a_repo = os.path.join(tmp_root, "empty")
    os.makedirs(not_a_repo, exist_ok=True)
    result = gitops.git_push(not_a_repo, remote="https://github.com/o/r.git",
                             branch="main", token="sekret-token")
    assert result["pushed"] is False
    assert "sekret-token" not in result["error"]


# ---- security ---------------------------------------------------------------

def test_worker_security_policy():
    assert security.is_dangerous("rm -rf .")
    assert security.is_allowed("npm test")
    assert not security.is_allowed("rm -rf .")
    assert security.redact("key=supersecret end", ["supersecret"]) == "key=[REDACTED] end"