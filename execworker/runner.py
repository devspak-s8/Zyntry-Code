"""Runner bridge: claim workspaces, execute tool requests, post results."""

import asyncio
import logging
import os

import httpx

from execworker import commandops, delivery, fsops, gitops, mcp_client, security, terminal

logger = logging.getLogger("zyntry-worker")


class Runner:
    def __init__(self, *, backend_url: str, token: str | None, worker_id: str,
                 name: str, workspaces_dir: str, heartbeat_seconds: int = 30,
                 poll_seconds: int = 5, cpu_limit: float | None = None,
                 mem_limit_mb: int | None = None):
        self.backend = backend_url.rstrip("/")
        self.token = token
        self.worker_id = worker_id
        self.name = name
        self.workspaces_dir = workspaces_dir
        self.heartbeat_seconds = heartbeat_seconds
        self.poll_seconds = poll_seconds
        # Kernel-enforced resource caps for every command this worker runs
        # (POSIX only; ignored elsewhere). None/0 disables.
        self.cpu_limit = cpu_limit or None
        self.mem_limit_mb = mem_limit_mb or None
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._ws_cache: dict[str, dict] = {}
        self._running = True
        self._started_by_request: dict[str, str] = {}

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.backend, headers=self._headers, timeout=60.0)

    async def register(self) -> None:
        async with await self._client() as client:
            await client.post("/workers/register",
                              json={"id": self.worker_id, "name": self.name,
                                    "capabilities": ["fs", "command", "git"]})
        logger.info("registered as worker %s", self.worker_id)

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                async with await self._client() as client:
                    await client.post(f"/workers/{self.worker_id}/heartbeat")
            except Exception as exc:  # noqa: BLE001
                logger.warning("heartbeat failed: %s", exc)
            await asyncio.sleep(self.heartbeat_seconds)

    async def _get_pending_workspace(self) -> dict | None:
        async with await self._client() as client:
            resp = await client.get("/workspaces", params={"pending": "true", "provider": "remote"})
            resp.raise_for_status()
            workspaces = resp.json().get("workspaces", [])
        for ws in workspaces:
            if ws.get("runner_id") in (None, self.worker_id):
                return ws
        return None

    async def _next_request(self, workspace_id: str) -> dict | None:
        async with await self._client() as client:
            resp = await client.get(f"/workspaces/{workspace_id}/tool-requests/next",
                                    headers={"x-runner-id": self.worker_id})
            resp.raise_for_status()
            return resp.json().get("tool_request")

    async def _post_result(self, workspace_id: str, request_id: str, status: str, result: dict) -> None:
        async with await self._client() as client:
            await client.post(f"/workspaces/{workspace_id}/tool-requests/{request_id}/result",
                              json={"status": status, "result": result})

    async def _post_state(self, workspace_id: str, fields: dict) -> None:
        async with await self._client() as client:
            await client.post(f"/workspaces/{workspace_id}/state", json=fields)

    async def run_once(self) -> int:
        """Process available tool requests once; returns the number executed."""
        ws = await self._get_pending_workspace()
        if ws is None:
            return 0
        counter = [0]
        await self._serve_workspace(ws, counter)
        return counter[0]

    async def _serve_workspace(self, ws: dict, executed_ref: list[int]) -> None:
        workspace_id = ws["id"]
        workdir = ws.get("workdir") or os.path.join(self.workspaces_dir, workspace_id)
        repo_url = ws.get("repo_url")
        branch = ws.get("branch")

        try:
            prepared = gitops.prepare_workspace(self.workspaces_dir, workspace_id, repo_url, branch)
            workdir = prepared["workdir"]
            await self._post_state(workspace_id, {
                "status": "ready", "workdir": workdir,
                "base_commit": prepared.get("base_commit"), "error": None})
        except Exception as exc:  # noqa: BLE001
            await self._post_state(workspace_id, {"status": "failed", "error": str(exc)})
            return

        while self._running:
            try:
                req = await self._next_request(workspace_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("poll failed for %s: %s", workspace_id, exc)
                break
            if req is None:
                break
            try:
                status, result = await self._execute(req, ws, workdir)
                executed_ref[0] += 1
            except Exception as exc:  # noqa: BLE001
                status, result = "failed", {"error": str(exc)}
            await self._post_result(workspace_id, req["id"], status, result)

        if ws.get("auto_commit"):
            try:
                commit = gitops.git_commit(workdir, "zyntry-code: apply task changes")
                if commit.get("committed"):
                    await self._post_state(workspace_id, {"head_commit": commit.get("head")})
            except Exception as exc:  # noqa: BLE001
                logger.warning("auto-commit failed: %s", exc)

    async def _execute(self, req: dict, ws: dict, workdir: str) -> tuple[str, dict]:
        tool = req["tool"]
        params = req.get("params") or {}
        secrets = list((ws.get("env") or {}).values())
        allowed = ws.get("allowed_commands") or None

        if tool == "fs.list":
            result = fsops.fs_list(workdir, params.get("path", "."))
            return ("succeeded" if "error" not in result else "failed"), result

        if tool == "fs.read":
            result = fsops.fs_read(workdir, params["path"])
            return ("succeeded" if "error" not in result else "failed"), result

        if tool == "fs.write":
            result = fsops.fs_write(workdir, params["path"], params.get("content", ""))
            return ("succeeded" if "files" in result else "failed"), result

        if tool == "fs.edit":
            result = fsops.fs_edit(workdir, params["path"], params.get("search", ""),
                                   params.get("replace", ""))
            return ("succeeded" if "files" in result else "failed"), result

        if tool == "fs.delete":
            result = fsops.fs_delete(workdir, params["path"])
            return ("succeeded" if "files" in result else "failed"), result

        if tool == "fs.search":
            result = fsops.fs_search(workdir, params.get("pattern", ""), params.get("path", "."))
            return ("succeeded" if "error" not in result else "failed"), result

        if tool == "git.status":
            return "succeeded", gitops.git_status(workdir)

        if tool == "git.diff":
            return "succeeded", gitops.git_diff(workdir)

        if tool == "git.commit":
            result = gitops.git_commit(workdir, params.get("message", "zyntry-code changes"))
            return ("succeeded" if result.get("committed") else "failed"), result

        if tool == "git.push":
            result = gitops.git_push(workdir, remote=params.get("remote"),
                                     branch=params.get("branch"),
                                     token=params.get("token"))
            return ("succeeded" if result.get("pushed") else "failed"), result

        if tool == "github.pr":
            result = await delivery.create_pull_request(
                repo_url=ws.get("repo_url"), token=params.get("token"),
                title=params.get("title", "Zyntry Code changes"),
                body=params.get("body", ""),
                base=params.get("base", ws.get("branch") or "main"),
                head=params.get("head", gitops.current_commit_branch(workdir)))
            return ("succeeded" if result.get("created") else "failed"), result

        if tool == "command.run":
            cmd = params.get("cmd", "")
            if not security.is_allowed(cmd, allowed):
                return "failed", {"error": f"command not in allowlist: {cmd}"}
            if security.is_dangerous(cmd) and not req.get("dangerous"):
                return "failed", {"error": f"dangerous command requires approval: {cmd}"}
            result = await commandops.run_command(
                workdir, cmd, env=ws.get("env"), timeout=ws.get("timeout_seconds", 300),
                secrets=secrets, cpu_limit=self.cpu_limit, mem_limit_mb=self.mem_limit_mb)
            ok = int(result.get("exit_code") or 0) == 0 and not result.get("timed_out")
            if result.get("timed_out"):
                return "timed_out", result
            return ("succeeded" if ok else "failed"), result

        if tool == "command.start":
            result = await commandops.start_command(workdir, params.get("cmd", ""),
                                                    env=ws.get("env"), secrets=secrets,
                                                    cpu_limit=self.cpu_limit,
                                                    mem_limit_mb=self.mem_limit_mb)
            if "process_id" in result:
                self._started_by_request[req["id"]] = result["process_id"]
            return ("succeeded" if "process_id" in result else "failed"), result

        if tool == "command.stop":
            process_id = params.get("process_id")
            if not process_id and params.get("from_request"):
                process_id = self._started_by_request.get(params["from_request"])
            result = await commandops.stop_command(process_id or "")
            return ("succeeded" if "stopped" in result else "failed"), result

        # ---- MCP ecosystem tools ------------------------------------------
        if tool in ("mcp.list_tools", "mcp.call"):
            servers = {s.get("name"): s for s in (ws.get("mcp_servers") or [])}
            server_cfg = servers.get(params.get("server", ""))
            if server_cfg is None:
                return "failed", {"error": f"MCP server {params.get('server')!r} is not configured"}
            try:
                if tool == "mcp.list_tools":
                    tools = await mcp_client.list_tools(server_cfg)
                    return "succeeded", {"tools": [t.get("name") for t in tools]}
                result = await mcp_client.call_tool(
                    server_cfg, str(params.get("tool", "")), params.get("args") or {})
                return ("succeeded" if not result.get("isError") else "failed"), result
            except mcp_client.McpError as exc:
                return "failed", {"error": str(exc)}

        # ---- interactive terminal sessions ---------------------------------
        if tool == "terminal.start":
            result = await terminal.start_session(
                cwd=workdir, command=params.get("command"),
                cols=int(params.get("cols", 120)), rows=int(params.get("rows", 40)),
                env=ws.get("env"))
            return ("succeeded" if "session_id" in result else "failed"), result

        if tool == "terminal.input":
            try:
                result = await terminal.write_input(params.get("session_id", ""), params.get("data", ""))
                return "succeeded", result
            except ValueError as exc:
                return "failed", {"error": str(exc)}

        if tool == "terminal.output":
            try:
                return "succeeded", await terminal.read_output(params.get("session_id", ""))
            except ValueError as exc:
                return "failed", {"error": str(exc)}

        if tool == "terminal.resize":
            try:
                result = await terminal.resize(params.get("session_id", ""),
                                               int(params.get("cols", 120)),
                                               int(params.get("rows", 40)))
                return "succeeded", result
            except ValueError as exc:
                return "failed", {"error": str(exc)}

        if tool == "terminal.stop":
            result = await terminal.stop_session(params.get("session_id", ""))
            return ("succeeded" if "stopped" in result else "failed"), result

        return "failed", {"error": f"unsupported tool: {tool}"}

    async def serve(self) -> None:
        """Run forever: heartbeat + work loop."""
        await self.register()
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        try:
            while self._running:
                try:
                    executed = await self.run_once()
                    if executed == 0:
                        await asyncio.sleep(self.poll_seconds)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("work loop error: %s", exc)
                    await asyncio.sleep(self.poll_seconds)
        finally:
            self._running = False
            heartbeat.cancel()