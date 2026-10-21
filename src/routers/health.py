"""Health and capability endpoints."""

from fastapi import APIRouter, Depends

from providers import available_providers, provider_order
from runtime import Runtime, get_runtime

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(runtime: Runtime = Depends(get_runtime)) -> dict:
    workflow = getattr(runtime.env, "EXECUTION_WORKFLOW", None) if runtime.env else None
    return {
        "status": "ok",
        "service": "zyntry-code",
        "version": "0.1.0",
        "providers": {
            "configured": sorted(available_providers(runtime)),
            "order": provider_order(runtime),
        },
        "workflow": {
            # Cloud (Workers) durable execution: POST /tasks/{id}/execute?mode=workflow.
            # Available only on the deployed Worker with the EXECUTION_WORKFLOW binding.
            "available": workflow is not None,
        },
    }