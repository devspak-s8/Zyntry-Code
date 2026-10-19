"""Cloudflare Workers entrypoint.

Referenced by ``wrangler.jsonc`` (``main = "src/worker.py"``). Adapts the
FastAPI ``app`` (an ASGI application) to the Workers runtime using the ``asgi``
adapter injected by the Python Workers runtime, and defines the durable
execution Workflow used for long-running tasks.

The ``asgi``/``workers`` modules only exist inside the Workers runtime (via
``pywrangler``), which is why this file is kept separate from the rest of the
application. Local development uses ``local/dev.py`` (uvicorn) instead.
"""

from app import app

import asgi

from workers import WorkflowEntrypoint


class ZyntryCodeExecutionWorkflow(WorkflowEntrypoint):
    """Durable, long-running execution of a task's plan.

    Triggered from ``POST /tasks/{id}/execute?mode=workflow``. Runs the same
    engine as the synchronous path, but survives Workers request/CPU limits —
    the execution state lives in D1, so progress can be polled via the REST API
    while the workflow runs.
    """

    async def run(self, event, step):
        from executor import execute_task
        from runtime import runtime_from_env

        runtime = runtime_from_env(self.env)
        task_id = event.get("task_id") if isinstance(event, dict) else None
        if not task_id:
            raise ValueError("workflow event must include task_id")

        @step.do("execute plan", retries={"maxAttempts": 1})
        async def run_plan():
            return await execute_task(runtime, task_id)

        return await run_plan()


Default = asgi.entrypoint(app)