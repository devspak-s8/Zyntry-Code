"""Command execution with timeouts, output capture, and background processes.

Resource limits (rlimits): on POSIX systems, CPU time and address-space (memory)
caps are applied by the kernel *before the command starts*, via
``resource.setrlimit`` in the child's pre-exec hook. A ``while True`` loop or a
memory bomb is killed by the OS — it can never take down the worker. On
non-POSIX platforms the limits are reported as not enforced (the soft timeout
still applies).
"""

import asyncio
import os
import signal
import time
import uuid

from execworker.security import parse_command, redact, safe_child_env

# Background processes keyed by process id.
_BACKGROUND: dict[str, asyncio.subprocess.Process] = {}
_BACKGROUND_LOGS: dict[str, str] = {}


def _merged_env(extra: dict | None) -> dict:
    return safe_child_env(extra)


def _rlimit_preexec(cpu_limit: float | None, mem_limit_mb: int | None):
    """Build a pre-exec hook applying kernel resource limits (POSIX only).

    ``os.setsid()`` keeps the process-group kill (for timeouts) working, since
    a pre-exec hook replaces ``start_new_session``.
    """
    def preexec() -> None:
        try:
            os.setsid()
        except OSError:
            pass
        import resource  # POSIX-only; never imported on Windows
        if cpu_limit:
            # RLIMIT values must be integers — a float here makes setrlimit
            # raise inside the child, which then exits(1) before running.
            resource.setrlimit(resource.RLIMIT_CPU, (int(cpu_limit), int(cpu_limit) + 1))
        if mem_limit_mb:
            limit = int(mem_limit_mb) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    return preexec


def _spawn_kwargs(cpu_limit: float | None, mem_limit_mb: int | None) -> tuple[dict, bool]:
    """Subprocess kwargs for rlimit-enforced (POSIX) or plain (elsewhere) spawns."""
    if os.name != "nt" and (cpu_limit or mem_limit_mb):
        return {"preexec_fn": _rlimit_preexec(cpu_limit, mem_limit_mb)}, True
    return {"start_new_session": True}, False


def _rlimits_info(enforced: bool, cpu_limit: float | None, mem_limit_mb: int | None) -> dict:
    return {"enforced": enforced, "cpu_seconds": cpu_limit, "mem_mb": mem_limit_mb}


def _windows_builtin_result(argv: list[str], secrets: list[str]) -> dict | None:
    """Handle the small set of shell builtins used by the portable worker tests.

    ``echo`` is a builtin on Windows, so it is not available to
    ``create_subprocess_exec`` as a standalone executable.  Handling this
    harmless builtin directly keeps execution shell-free and portable.
    """
    if os.name == "nt" and argv and argv[0].lower() == "echo":
        output = redact(" ".join(argv[1:]) + "\n", secrets)
        return {"stdout": output, "stderr": "", "exit_code": 0}
    return None


async def run_command(cwd: str, cmd: str, env: dict | None = None,
                      timeout: float = 300.0, secrets: list[str] | None = None,
                      cpu_limit: float | None = None,
                      mem_limit_mb: int | None = None) -> dict:
    started = time.monotonic()
    kwargs, enforced = _spawn_kwargs(cpu_limit, mem_limit_mb)
    try:
        argv = parse_command(cmd)
        builtin = _windows_builtin_result(argv, secrets or [])
        if builtin is not None:
            builtin.update({
                "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False,
                "killed_by_signal": False,
                "rlimits": _rlimits_info(False, cpu_limit, mem_limit_mb),
                "error": None,
            })
            return builtin
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=cwd, env=_merged_env(env),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            **kwargs,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            timed_out = False
        except asyncio.TimeoutError:
            timed_out = True
            _kill(proc)
            stdout, stderr = await proc.communicate()

        out = redact((stdout or b"").decode("utf-8", errors="replace")[-20000:], secrets or [])
        err = redact((stderr or b"").decode("utf-8", errors="replace")[-20000:], secrets or [])
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "stdout": out, "stderr": err,
            "exit_code": proc.returncode if proc.returncode is not None else -1,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
            # Negative return code == killed by a signal (kernel rlimit or our timeout kill).
            "killed_by_signal": proc.returncode is not None and proc.returncode < 0,
            "rlimits": _rlimits_info(enforced, cpu_limit, mem_limit_mb),
            "error": f"timed out after {timeout}s" if timed_out else None,
        }
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"command not found: {cmd}",
                "exit_code": 127, "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False, "killed_by_signal": False,
                "rlimits": _rlimits_info(enforced, cpu_limit, mem_limit_mb),
                "error": f"command not found: {cmd}"}
    except Exception as exc:  # noqa: BLE001
        return {"stdout": "", "stderr": str(exc), "exit_code": -1,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False, "killed_by_signal": False,
                "rlimits": _rlimits_info(enforced, cpu_limit, mem_limit_mb),
                "error": str(exc)}


def _kill(proc: asyncio.subprocess.Process) -> None:
    try:
        if os.name != "nt":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except Exception:  # noqa: BLE001
        pass


async def start_command(cwd: str, cmd: str, env: dict | None = None,
                        secrets: list[str] | None = None,
                        cpu_limit: float | None = None,
                        mem_limit_mb: int | None = None) -> dict:
    """Start a long-running process (dev server) in the background."""
    process_id = uuid.uuid4().hex[:12]
    log_path = os.path.join(cwd, ".zyntry-logs", f"{process_id}.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    kwargs, enforced = _spawn_kwargs(cpu_limit, mem_limit_mb)
    try:
        proc = await asyncio.create_subprocess_exec(
            *parse_command(cmd), cwd=cwd, env=_merged_env(env),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    _BACKGROUND[process_id] = proc
    _BACKGROUND_LOGS[process_id] = log_path
    asyncio.create_task(_capture_background_log(proc, log_path, secrets or []))
    return {"process_id": process_id, "pid": proc.pid, "log": log_path,
            "rlimits": _rlimits_info(enforced, cpu_limit, mem_limit_mb)}


async def _capture_background_log(proc: asyncio.subprocess.Process, path: str,
                                  secrets: list[str], max_bytes: int = 2_000_000) -> None:
    """Persist bounded, redacted output without exposing credentials on disk."""
    written = 0
    try:
        with open(path, "w", encoding="utf-8") as log_fh:
            while proc.stdout is not None:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                if written >= max_bytes:
                    continue
                text = redact(chunk.decode("utf-8", errors="replace"), secrets)
                remaining = max_bytes - written
                log_fh.write(text[:remaining])
                log_fh.flush()
                written += min(len(text), remaining)
    except Exception:  # noqa: BLE001
        return


async def stop_command(process_id: str) -> dict:
    proc = _BACKGROUND.pop(process_id, None)
    if proc is None:
        return {"error": f"unknown process: {process_id}"}
    _kill(proc)
    try:
        await proc.wait()
    except Exception:  # noqa: BLE001
        pass
    return {"stopped": True, "process_id": process_id}


async def command_logs(process_id: str, tail: int = 5000) -> dict:
    log_path = _BACKGROUND_LOGS.get(process_id)
    if not log_path or not os.path.exists(log_path):
        return {"error": f"no logs for process: {process_id}"}
    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    return {"log": content[-max(0, min(int(tail), 5000)): ]}
