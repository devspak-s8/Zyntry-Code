"""Zyntry Code remote worker — the "durable computer".

Runs on any Linux host (VPS, container, CI runner). Connects to the Zyntry Code
backend, claims workspaces with queued tool requests, executes them in isolated
workspace directories, and posts real results back — closing the loop between
generated code and running software.

Run:
    python -m execworker.main --backend http://localhost:8787 [--once]

Env/config:
    ZYNTRY_BACKEND_URL, ZYNTRY_TOKEN (if API_TOKEN auth enabled),
    ZYNTRY_WORKER_ID, ZYNTRY_WORKER_NAME, ZYNTRY_WORKSPACES_DIR,
    WORKER_HEARTBEAT_SECONDS, WORKER_POLL_SECONDS
"""