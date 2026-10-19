"""Interactive terminal sessions for the worker.

On POSIX a real PTY is allocated (``pty.openpty``), so the child sees a
controlling terminal — prompts, colors, interactive REPLs work. On Windows a
pipe-based fallback is used (line-buffered, no pty semantics). Output is
captured into a per-session buffer; ``read_output`` returns everything since
the last read position, so the agent can poll interactively.
"""

import asyncio
import os
import signal
import time
import uuid

_SESSIONS: dict[str, dict] = {}


async def _reader_loop(session: dict) -> None:
    try:
        while True:
            data = await asyncio.to_thread(os.read, session["fd"], 4096)
            if not data:
                break
            session["buffer"] += data.decode("utf-8", errors="replace")
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


async def start_session(*, cwd: str, command: str | None = None,
                        cols: int = 120, rows: int = 40, env: dict | None = None) -> dict:
    """Start an interactive terminal session. Returns {session_id, pid, pty: bool}."""
    session_id = uuid.uuid4().hex[:12]
    merged_env = dict(os.environ)
    if env:
        merged_env.update({str(k): str(v) for k, v in env.items()})

    shell = command or ("cmd" if os.name == "nt" else "bash")
    if os.name == "nt":
        proc = await asyncio.create_subprocess_shell(
            shell, cwd=cwd, env=merged_env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)
        reader_fd = None
        session = {"id": session_id, "proc": proc, "fd": None, "buffer": "",
                   "exited": False, "pty": False, "read_pos": 0}
        _SESSIONS[session_id] = session
        asyncio.create_task(_pipe_reader(session))
        return {"session_id": session_id, "pid": proc.pid, "pty": False}

    import pty

    master, slave = pty.openpty()
    proc = await asyncio.create_subprocess_exec(
        shell, cwd=cwd, env=merged_env, stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True)
    os.close(slave)
    session = {"id": session_id, "proc": proc, "fd": master, "buffer": "",
               "exited": False, "pty": True, "read_pos": 0}
    _SESSIONS[session_id] = session
    asyncio.create_task(_reader_loop(session))
    try:
        import fcntl
        import struct
        fcntl.ioctl(master, 0x5410, struct.pack("HHHH", rows, cols, 0, 0))  # TIOCSWINSZ
    except (ImportError, OSError):
        pass
    return {"session_id": session_id, "pid": proc.pid, "pty": True}


async def _pipe_reader(session: dict) -> None:
    proc = session["proc"]
    try:
        while True:
            data = await proc.stdout.readline() if proc.stdout else b""
            if not data:
                break
            session["buffer"] += data.decode("utf-8", errors="replace")
    except (ValueError, OSError):
        pass
    finally:
        session["exited"] = True


def _get(session_id: str) -> dict:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"unknown terminal session: {session_id}")
    return session


async def write_input(session_id: str, data: str) -> dict:
    session = _get(session_id)
    proc = session["proc"]
    if proc.stdin is None or proc.returncode is not None:
        raise ValueError("session is not running")
    if session.get("fd") is not None:
        os.write(session["fd"], data.encode())
    else:
        proc.stdin.write(data.encode())
        await proc.stdin.drain()
    return {"written": len(data)}


async def read_output(session_id: str) -> dict:
    session = _get(session_id)
    output = session["buffer"][session["read_pos"]:]
    session["read_pos"] = len(session["buffer"])
    return {"output": output, "exited": bool(session["exited"])}


async def resize(session_id: str, cols: int, rows: int) -> dict:
    session = _get(session_id)
    if session.get("fd") is not None:
        try:
            import fcntl
            import struct
            fcntl.ioctl(session["fd"], 0x5410, struct.pack("HHHH", rows, cols, 0, 0))
        except (ImportError, OSError):
            pass
    return {"resized": True}


async def stop_session(session_id: str) -> dict:
    session = _SESSIONS.pop(session_id, None)
    if session is None:
        return {"error": f"unknown terminal session: {session_id}"}
    _kill_proc(session["proc"])
    if session.get("fd") is not None:
        try:
            os.close(session["fd"])
        except OSError:
            pass
    return {"stopped": True, "session_id": session_id}