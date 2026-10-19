"""Metrics endpoint — operational counters (routing, escalation, errors)."""

from fastapi import APIRouter

from metrics import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics() -> dict:
    return metrics.snapshot()