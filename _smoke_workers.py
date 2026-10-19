"""Smoke test against the running Workers dev server (workerd + Pyodide).

Validates that the real Cloudflare runtime (asgi adapter, D1 binding) serves
the app. Run with: python _smoke_workers.py [base_url]
"""

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8790"


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def main() -> None:
    status, health = call("GET", "/health")
    print(f"GET /health -> {status} providers={health.get('providers')}")
    assert status == 200 and health["status"] == "ok"

    status, models = call("GET", "/models")
    print(f"GET /models -> {status} models={len(models['models'])}")
    assert status == 200 and models["models"]

    status, created = call("POST", "/tasks", {"prompt": "Add a new API endpoint to the users service"})
    print(f"POST /tasks -> {status} detail={created.get('detail')}")
    # Planning is LLM-only: with no provider keys configured the API must fail
    # loudly (503) instead of silently falling back to a template plan.
    assert status == 503 and created.get("detail")

    # Task-dependent flows (repo ingest, execution, events) require a configured
    # provider now that planning is LLM-only; they are covered by the pytest suite.
    print("Skipping repo/execute/event flows (require a configured provider for LLM planning).")

    status, m = call("GET", "/metrics")
    print(f"GET /metrics -> {status} counters={m['counters']}")
    assert status == 200

    print("\nSMOKE OK — FastAPI runs on the Workers runtime (asgi adapter + D1).")


if __name__ == "__main__":
    main()