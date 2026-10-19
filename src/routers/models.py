"""Model catalog and routing-preview endpoints."""

from fastapi import APIRouter, Depends

from domain import routing
from domain.catalog import MODELS
from providers import available_providers
from runtime import Runtime, get_runtime
from schemas import RoutePreviewRequest

router = APIRouter(prefix="/models", tags=["models"])


def _model_out(m: dict, available: set[str]) -> dict:
    return {
        "id": m.id,
        "provider": m.provider,
        "display_name": m.display_name,
        "tier": m.tier,
        "context_window": m.context_window,
        "cost": {"in_per_1m": m.cost_in, "out_per_1m": m.cost_out},
        "capabilities": sorted(m.capabilities),
        "latency_class": m.latency_class,
        "available": m.provider in available,
    }


@router.get("")
async def list_models(runtime: Runtime = Depends(get_runtime)) -> dict:
    available = available_providers(runtime)
    return {"models": [_model_out(m, available) for m in MODELS]}


@router.post("/route")
async def route_preview(body: RoutePreviewRequest, runtime: Runtime = Depends(get_runtime)) -> dict:
    available = available_providers(runtime)
    from providers import provider_order
    selected, candidates, reasoning = routing.select_model(
        body.kind, body.risk, available, provider_order(runtime), body.preferred_provider)
    return {
        "selected": _model_out(selected, available) if selected else None,
        "candidates": [_model_out(m, available) for m in candidates],
        "reasoning": reasoning,
    }