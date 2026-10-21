"""Artifact endpoints — record concrete file/patch results per execution.

The execution engine auto-detects artifacts from model output
(`` ```language:path/to/file`` fenced blocks); the VS Code extension can also
post explicit artifacts (patches it applied, files it wrote) here so the
execution summary reflects what actually changed.
"""

from fastapi import APIRouter, Depends, HTTPException

import store
from runtime import Runtime, get_runtime
from schemas import ArtifactRequest

router = APIRouter(prefix="/executions", tags=["artifacts"])


@router.post("/{execution_id}/stages/{stage_id}/artifacts")
async def post_artifact(execution_id: str, stage_id: str, body: ArtifactRequest,
                        runtime: Runtime = Depends(get_runtime)) -> dict:
    execution = await store.get_execution(runtime.db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    stage = await store.get_stage(runtime.db, stage_id)
    if stage is None or stage["plan_id"] != execution["plan_id"]:
        raise HTTPException(status_code=404, detail="stage not found in this execution")

    artifact_id = await store.create_artifact(
        runtime.db, execution_id=execution_id, stage_id=stage_id, path=body.path,
        kind=body.kind, language=body.language, source="extension", content=body.content)
    return {"artifact_id": artifact_id, "path": body.path, "source": "extension"}


@router.get("/{execution_id}/artifacts")
async def get_artifacts(execution_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    execution = await store.get_execution(runtime.db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return {"artifacts": await store.get_artifacts(runtime.db, execution_id)}
