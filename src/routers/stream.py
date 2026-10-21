"""SSE progress streaming.

``POST /tasks/{id}/execute/stream`` runs the execution and streams its events
(stage starts, attempts, verification, escalation, completion) to the client as
Server-Sent Events, ending with a ``done`` event carrying the full summary.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from runtime import Runtime, get_runtime

router = APIRouter(prefix="/tasks", tags=["stream"])


def format_sse(event: dict) -> str:
    """Encode one event as an SSE frame."""
    return f"data: {json.dumps(event, default=str)}\n\n"


def parse_sse_chunk(buffer: str) -> tuple[list[dict], str]:
    """Parse complete SSE frames from a stream chunk.

    Returns ``(events, leftover)`` — the leftover is retained for the next
    chunk, so partial frames never get dropped.
    """
    events: list[dict] = []
    leftover = buffer
    while True:
        marker = leftover.find("\n\n")
        if marker == -1:
            break
        frame, leftover = leftover[:marker], leftover[marker + 2:]
        for line in frame.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    continue
    return events, leftover


@router.post("/{task_id}/execute/stream")
async def execute_stream(task_id: str, runtime: Runtime = Depends(get_runtime)) -> StreamingResponse:
    from executor import execute_task

    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def on_event(event: dict) -> None:
        await queue.put(event)

    async def run_execution() -> None:
        try:
            summary = await execute_task(runtime, task_id, on_event=on_event)
            await queue.put({"type": "done", "summary": summary})
        except ValueError as exc:
            await queue.put({"type": "error", "detail": "invalid task request", "status": 404})
        except PermissionError as exc:
            await queue.put({"type": "error", "detail": "task cannot be executed", "status": 409})
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "detail": "execution failed", "status": 500})

    execution_task = asyncio.create_task(run_execution())

    async def event_stream():
        try:
            while True:
                event = await queue.get()
                yield format_sse(event)
                if event["type"] in ("done", "error"):
                    return
        finally:
            if not execution_task.done():
                execution_task.cancel()
            try:
                await execution_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
