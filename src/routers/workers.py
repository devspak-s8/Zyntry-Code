"""Worker registry — remote execution runners register and heartbeat here."""

from fastapi import APIRouter, Depends, HTTPException

import store
from runtime import Runtime, get_runtime
from schemas import WorkerRegisterRequest
from util import uuid_str

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("/register")
async def register_worker(body: WorkerRegisterRequest, runtime: Runtime = Depends(get_runtime)) -> dict:
    worker_id = body.id or uuid_str()
    await store.register_worker(runtime.db, worker_id, body.name, body.capabilities)
    return {"worker_id": worker_id, "status": "online"}


@router.post("/{worker_id}/heartbeat")
async def heartbeat(worker_id: str, runtime: Runtime = Depends(get_runtime)) -> dict:
    await store.worker_heartbeat(runtime.db, worker_id)
    return {"worker_id": worker_id, "status": "online"}


@router.get("")
async def list_workers(runtime: Runtime = Depends(get_runtime)) -> dict:
    workers = await store.list_workers(runtime.db)
    return {"workers": workers}