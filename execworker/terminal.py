"""Interactive terminal sessions for the worker.

On POSIX a real PTY is allocated (``pty.openpty``), so the child sees a
controlling terminal — prompts, colors, interactive REPLs work. On Windows a
pipe-based fallback is used (line-buffered, no pty semantics). Output is
captured into a per-session buffer; ``read_output`` returns everything since
the last read position, so the agent can poll interactively.
"""

import asyncio
import atexit
import os
import signal
import time
import uuid

from execworker.security import parse_command, safe_child_env

_SESSIONS: dict[str, dict] = {}
_MAX_BUFFER = 1_000_000


def _cleanup_all_sessions() -> None:
    """Kill every live session at interpreter exit so a leaked session can
    never block process shutdown (the PTY reader thread would otherwise keep
    the executor alive)."""
    for session in list(_SESSIONS.values()):
        try:
            _kill_proc(session["proc"])
        except Exception:  # noqa: BLE001
            pass
        fd = session.get("fd")
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
    _SESSIONS.clear()


atexit.register(_cleanup_all_sessions)


async def _reader_loop(session: dict) -> None:
    try:
        while True:
            data = await asyncio.to_thread(os.read, session["fd"], 4096)
            if not data:
                break
            session["buffer"] = (session["buffer"] + data.decode("utf-8", errors="replace"))[-_MAX_BUFFER:]
    except (OSError, ValueError):
        pass
    finally:
        session["exited"] = True


def _kill_proc(proc) -> None:
    try:
        if os.name != "nt":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except Exception:  # noqa: BLE001
        pass


async def _start_pipe_session(session_id: str, argv: list[str], cwd: str,
                              merged_env: dict, owner: str | None) -> dict:
    """Pipe-backed session (Windows, or POSIX fallback when the PTY child
    exits immediately)."""
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=cwd, env=merged_env,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)
    session = {"id": session_id, "owner": owner, "proc": proc, "fd": None,
               "buffer": "", "exited": False, "pty": False, "read_pos": 0,
               "created_at": time.time()}
    _SESSIONS[session_id] = session
    asyncio.create_task(_pipe_reader(session))
    return {"session_id": session_id, "pid": proc.pid, "pty": False}


async def start_session(*, cwd: str, command: str | None = None,
                        cols: int = 120, rows: int = 40, env: dict | None = None,
                        owner: str | None = None) -> dict:
    """Start an interactive terminal session. Returns {session_id, pid, pty: bool}."""
    session_id = uuid.uuid4().hex[:12]
    merged_env = safe_child_env(env)

    argv = parse_command(command) if command else (["cmd"] if os.name == "nt" else ["bash"])
    if os.name == "nt":
        return await _start_pipe_session(session_id, argv, cwd, merged_env, owner)

    import pty

    master, slave = pty.openpty()
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=cwd, env=merged_env, stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True)
    os.close(slave)
    session = {"id": session_id, "owner": owner, "proc": proc, "fd": master,
               "buffer": "", "exited": False, "pty": True, "read_pos": 0,
               "created_at": time.time()}
    _SESSIONS[session_id] = session
    asyncio.create_task(_reader_loop(session))
    try:
        import fcntl
        import struct
        fcntl.ioctl(master, 0x5410, struct.pack("HHHH", rows, cols, 0, 0))  # TIOCSWINSZ
    except (ImportError, OSError):
        pass

    # Some CI runners cannot give the child a working PTY (it exits instantly).
    # Fall back to pipes so sessions still work everywhere.
    await asyncio.sleep(0.25)
    if proc.returncode is not None:
        _SESSIONS.pop(session_id, None)
        try:
            os.close(master)
        except OSError:
            pass
        return await _start_pipe_session(session_id, argv, cwd, merged_env, owner)

    return {"session_id": session_id, "pid": proc.pid, "pty": True}


async def _pipe_reader(session: dict) -> None:
    proc = session["proc"]
    try:
        while True:
            data = await proc.stdout.readline() if proc.stdout else b""
            if not data:
                break
            session["buffer"] = (session["buffer"] + data.decode("utf-8", errors="replace"))[-_MAX_BUFFER:]
    except (ValueError, OSError):
        pass
    finally:
        session["exited"] = True


def _get(session_id: str, owner: str | None = None) -> dict:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"unknown terminal session: {session_id}")
    if owner is not None and session.get("owner") != owner:
        raise ValueError("terminal session does not belong to this workspace")
    if time.time() - session.get("created_at", time.time()) > 3600:
        _SESSIONS.pop(session_id, None)
        _kill_proc(session["proc"])
        raise ValueError("terminal session expired")
    return session


async def write_input(session_id: str, data: str, owner: str | None = None) -> dict:
    if len(data) > 64 * 1024:
        raise ValueError("terminal input is too large")
    session = _get(session_id, owner)
    proc = session["proc"]
    if proc.stdin is None or proc.returncode is not None:
        raise ValueError("session is not running")
    if session.get("fd") is not None:
        os.write(session["fd"], data.encode())
    else:
        proc.stdin.write(data.encode())
        await proc.stdin.drain()
    return {"written": len(data)}


async def read_output(session_id: str, owner: str | None = None) -> dict:
    session = _get(session_id, owner)
    output = session["buffer"][session["read_pos"]:]
    session["read_pos"] = len(session["buffer"])
    return {"output": output, "exited": bool(session["exited"])}


async def resize(session_id: str, cols: int, rows: int, owner: str | None = None) -> dict:
    if not (1 <= cols <= 500 and 1 <= rows <= 200):
        raise ValueError("terminal dimensions are out of range")
    session = _get(session_id, owner)
    if session.get("fd") is not None:
        try:
            import fcntl
            import struct
            fcntl.ioctl(session["fd"], 0x5410, struct.pack("HHHH", rows, cols, 0, 0))
        except (ImportError, OSError):
            pass
    return {"resized": True}


async def stop_session(session_id: str, owner: str | None = None) -> dict:
    if session_id not in _SESSIONS:
        return {"error": f"unknown terminal session: {session_id}"}
    try:
        session = _get(session_id, owner)
    except ValueError as exc:
        return {"error": str(exc)}
    _SESSIONS.pop(session_id, None)
    if session is None:
        return {"error": f"unknown terminal session: {session_id}"}
    _kill_proc(session["proc"])
    if session.get("fd") is not None:
        try:
            os.close(session["fd"])
        except OSError:
            pass
    return {"stopped": True, "session_id": session_id}
