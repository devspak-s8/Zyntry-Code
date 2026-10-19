"""Semantic repo search endpoints: index, search, status."""

from fastapi import APIRouter, Depends, HTTPException

from runtime import Runtime, get_runtime
from schemas import SemanticSearchRequest
import semantic

router = APIRouter(prefix="/workspaces", tags=["semantic"])


@router.post("/{workspace_id}/semantic/index")
async def index_semantic(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    try:
        return await semantic.index_workspace(runtime, workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/{workspace_id}/semantic/search")
async def search_semantic(workspace_id: str, body: SemanticSearchRequest,
                          runtime: Runtime = Depends(get_runtime)) -> dict:
    try:
        results = await semantic.search_query(runtime, workspace_id, body.query, body.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"workspace_id": workspace_id, "query": body.query, "results": results}


@router.get("/{workspace_id}/semantic/status")
async def semantic_status(workspace_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    count = await semantic.store.semantic_chunk_count(runtime.db, workspace_id)
    return {"workspace_id": workspace_id, "chunks": count, "indexed": count > 0}