"""Repository ingestion endpoints — feed the agent's repository understanding.

The VS Code extension posts a snapshot of the repo (file list + optional
contents) so the "understand" stage and planner work from real context instead
of an empty prompt.
"""

from fastapi import APIRouter, Depends, HTTPException

import store
from runtime import Runtime, get_runtime
from schemas import RepoIngestRequest
from security import is_sensitive_path

router = APIRouter(prefix="/tasks", tags=["repo"])


@router.post("/{task_id}/repo")
async def ingest_repo(task_id: str, body: RepoIngestRequest, runtime: Runtime = Depends(get_runtime)) -> dict:
    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    files = []
    total_bytes = 0
    for file in body.files:
        path = file.path.replace("\\", "/")
        if path.startswith("/") or any(part == ".." for part in path.split("/")):
            continue
        if is_sensitive_path(path):
            continue
        payload = file.model_dump()
        payload["path"] = path
        total_bytes += len((payload.get("content") or "").encode("utf-8"))
        if total_bytes > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="repository snapshot is too large")
        files.append(payload)
    count = await store.replace_repo_files(runtime.db, task_id, files)
    return {"task_id": task_id, "files_ingested": count}


@router.get("/{task_id}/repo")
async def get_repo(task_id: str, runtime: Runtime = Depends(get_runtime), include_content: bool = True) -> dict:
    task = await store.get_task(runtime.db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    files = await store.get_repo_files(runtime.db, task_id)
    if not include_content:
        for f in files:
            f.pop("content", None)
    return {"task_id": task_id, "files": files}
