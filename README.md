# Zyntry Code — Backend

An **Adaptive AI Engineering Agent** backend. It receives engineering tasks,
decomposes them into a dependency-ordered plan, routes each stage to an
appropriate model, executes the stages (in parallel where possible), verifies
the results (deterministic checks + real repo reports), escalates to stronger
models when verification fails, enforces a cost budget, and produces an
auditable execution summary. Routing improves over time from execution
evidence.

Built with **Python / FastAPI**, deployed on **Cloudflare Workers** (Python
Workers) with **D1** for storage, **Workers AI** for edge inference, and
**Durable Workflows** for long-running execution.

---

## Architecture

```
                    ┌──────────────────────────────────────────────┐
  VS Code extension │            FastAPI (Python Workers)           │
        │           │                                               │
  POST /tasks ──────►  assess → LLM-only plan (strict JSON) → plan  │
  POST /tasks/{id}   │      (dependency DAG, approval gate)         │
      /repo ────────►  repo ingestion → feeds planner + prompts     │
        │           │                                               │
  execute (sync ────►  parallel stage executor                      │
   or workflow)     │    route (evidence-adjusted) → run → verify   │
  POST verification ►    (deterministic + repo reports) → escalate  │
  reports/artifacts │    budget enforced → artifacts recorded       │
        │           │                                               │
  GET /executions ──►  auditable summary (models, cost, evidence)   │
  /{id}/stream ─────►  SSE progress stream                          │
        │           │                                               │
                    │  D1 · Workers AI / OpenAI / Anthropic         │
                    │  Durable Workflows · routing_stats (learning) │
                    └──────────────────────────────────────────────┘
```

### The coding execution environment (Part 2)

The engine coordinates intelligence; the **execution environment gives it
somewhere to act**. Two interchangeable runners speak one bridge protocol:

```
      Zyntry Code backend (Workers + D1 + Workflows)
                       │  tool_requests: queued → dispatched → result
        ┌──────────────┴──────────────┐
        ▼                             ▼
  provider=local                provider=remote
  VS Code extension             execworker (Python, Linux host)
  (developer's machine)         git clone · fs ops · commands · diffs
        │                             │
        └──────────► POST result ◄────┘   → verification reports → escalation
```

- **Workspaces** (`POST /workspaces`) — repo URL/branch, provider, commands
  (test/lint/build/type-check), env, allowlist, timeout, auto-commit.
- **Tool requests** — `fs.list/read/write/edit/delete/search`,
  `git.status/diff/commit`, `command.run/start/stop`. Runners long-poll
  `GET /workspaces/{id}/tool-requests/next` and post results back.
- **Executor integration** — after a stage's model output, the executor
  dispatches artifact-applies + the stage's mapped verification commands,
  waits for the real results, and merges them into verification: **failing
  tests now genuinely trigger escalation**, and every file change is recorded
  (`/executions/{id}/changes`).
- **Security** — unknown/dangerous commands are held in `awaiting_approval`
  (`POST /workspaces/{id}/tool-requests/{id}/approve`); the worker enforces an
  allowlist and redacts secrets from output.
- **MCP ecosystem** — configure MCP servers per workspace
  (`PUT /workspaces/{id}/mcp-servers`, stdio or streamable-http transports).
  The agent can call them with `mcp.list_tools` / `mcp.call` inside the agentic
  loop; the worker executes the JSON-RPC handshake and returns real results.
- **Interactive terminals** — the agent can start live terminal sessions
  (`terminal.start/input/output/resize/stop`): real PTY on POSIX, pipe
  fallback on Windows — prompts, REPLs, and long-running servers become
  poked, not just launched.
- **Context compaction** — once accumulated prior-stage context exceeds 8k
  chars, the executor asks the model for a dense technical digest
  (`context_compactions_total` metric) instead of feeding raw history, keeping
  token cost flat as plans grow.
- **The worker** (`execworker/`, run on any VPS/container) registers +
  heartbeats, checks out the repo on an isolated branch, applies changes,
  runs commands with timeouts/output capture, computes diffs, commits
  optionally, and posts everything back. **Resource limits** (rlimits) cap
  every command's CPU time and address space *in the kernel before it starts* —
  a `while True` loop or a memory bomb is killed by the OS, never taking down
  the worker (`--cpu-limit` / `--mem-limit-mb`, or `ZYNTRY_CPU_LIMIT_SECONDS` /
  `ZYNTRY_MEM_LIMIT_MB`; POSIX only). Run it:

```bash
python -m execworker.main --backend https://your-worker.workers.dev --once   # drain + exit
python -m execworker.main --backend http://localhost:8787                    # run forever
```

or as a container (see **Docker** below): `docker compose up -d`.

Concurrency control lives in the runner: it executes requests sequentially, so
parallel stages never corrupt each other's files. Local mode: the VS Code
extension implements the same two endpoints against the developer's repo.

### The execution loop (per stage)

1. **Routing** — cheapest model meeting the stage's capabilities *and* the
   task's risk tier, only from configured providers, with a failure-rate
   penalty learned from past executions (`routing_stats`).
2. **Run** — prompt includes the task, repo context, prior stage outputs, and
   any failure evidence from earlier attempts.
3. **Verify** — deterministic checks (structure, code presence, Python `ast`
   syntax) **merged with repo-side reports** posted by the extension (tests,
   lint, build, visual, security…). Uncovered environment checks are reported
   as *limitations*, never claimed passed. Optional `verify_wait_seconds`
   makes the workflow path wait for reports.
4. **Escalate** — failed verification retries with the failure context,
   upgrading to a stronger model when one exists.
5. **Budget** — a projected-cost guard stops execution before the budget is
   exceeded; remaining stages are marked skipped.

---

## Project layout

```
zyntry-code/
├── pyproject.toml / wrangler.jsonc / migrations/
├── Dockerfile              # execution worker image (Python 3.13 + git)
├── docker-compose.yml      # one-command worker on a VPS (rlimits, restart, volume)
├── .github/workflows/      # CI: uv sync + full test suite on push/PR
├── src/
│   ├── worker.py           # Workers entrypoint + durable Workflow class
│   ├── app.py              # FastAPI app, auth/rate-limit middleware, CORS
│   ├── security.py         # bearer-token auth + rate limiting
│   ├── metrics.py          # counters/histograms (routing, escalation, errors)
│   ├── runtime.py / db.py  # Workers env + D1 / local sqlite backends
│   ├── store.py            # repository layer (raw SQL, atomic upserts)
│   ├── planner.py          # intake: assess + LLM-only plan (no template fallback)
│   ├── executor.py         # parallel stage engine: route → run → verify → escalate
│   ├── reporter.py         # auditable execution summary
│   ├── schemas.py
│   ├── domain/             # pure logic: assessment, routing (+learning),
│   │                       # verification (+report merge), escalation, artifacts, catalog
│   ├── providers/          # openai-compatible / anthropic / workers_ai
│   └── routers/            # health, models, tasks, stream (SSE), ingest (repo),
│                           # executions, verification, artifacts, metrics
├── execworker/             # the remote runner: gitops, fsops, commandops (rlimits),
│                           # security (allowlist/redaction), delivery (PRs), main
├── vscode-ext/             # VS Code extension: task commands + local runner
├── local/                  # uvicorn dev server (no Cloudflare tooling needed)
└── tests/                  # 81 tests incl. D1 adapter, parallelism, budget, auth,
                            # rlimits, SSE, fallback, agent loop, secrets/delivery
```

---

## Quickstart

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (for `pywrangler`) + Node.js

### 1. Local dev with the Workers runtime (recommended)

```bash
uv run pywrangler dev
uv run pywrangler d1 migrations apply DB --local
```

Put keys in `.dev.vars` (see `.dev.vars.example`):
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Docs at `http://localhost:8787/docs`.

### 2. Local dev with plain uvicorn

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e . && pip install uvicorn pytest pytest-asyncio
copy .env.example .env            # put keys in .env
uvicorn local.dev:app --reload --port 8787
```

### 3. Deploy to Cloudflare

```bash
uv run pywrangler d1 create zyntry-code     # copy id into wrangler.jsonc
uv run pywrangler secret put OPENAI_API_KEY
uv run pywrangler secret put ANTHROPIC_API_KEY
uv run pywrangler secret put API_TOKEN      # optional: requires Bearer auth

uv run pywrangler deploy
uv run pywrangler d1 migrations apply DB --remote
```

### 4. Execution worker with Docker

One command gives the worker a reproducible home on any VPS/container host
(Python 3.13 + git + the worker, persistent workspaces, restart policy):

```bash
export ZYNTRY_BACKEND_URL=https://your-worker.workers.dev
export ZYNTRY_TOKEN=your-api-token            # only if the backend enforces one
docker compose up -d --build
docker compose logs -f worker
```

- Persistent workspace checkouts live in `./worker-data` (bind-mounted).
- Per-command CPU/memory caps are on by default (`ZYNTRY_CPU_LIMIT_SECONDS=120`,
  `ZYNTRY_MEM_LIMIT_MB=1024`); set either to `0` to disable.
- The worker runs on its own bridge network; uncomment `internal: true` in
  `docker-compose.yml` for strict egress isolation (backend must be reachable
  from the host).

### 5. CI

`.github/workflows/ci.yml` runs `uv sync` + the full test suite on every push
and PR — regressions are caught before they reach a deploy.

### 6. VS Code extension

`vscode-ext/` is the client half of the product. Open it in VS Code and press
F5 to run: create/approve/run/stream tasks, ingest your repo snapshot, create
a `provider=local` workspace, and start the **local runner** that executes
tool requests (fs + `child_process`) directly in your workspace folder. See
`vscode-ext/README.md`.

### Tests
```bash
uv run pytest          # or .venv\Scripts\python -m pytest
```

---

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/health` | Liveness + configured providers |
| `GET` | `/metrics` | Counters: routing, escalations, errors, timings |
| `GET` | `/models` | Model catalog with availability |
| `POST` | `/models/route` | Routing preview (kind + risk) |
| `POST` | `/completion/stream` | Stream provider completion tokens as SSE |
| `POST` | `/tasks` | Create + assess + LLM-plan a task (503 if planning fails) |
| `POST` | `/tasks/{id}/repo` | Ingest the repo snapshot (file list + contents) |
| `GET` | `/tasks/{id}/repo` | Read the ingested repo snapshot |
| `GET` | `/tasks/{id}` | Task + plan + stages + latest execution |
| `POST` | `/tasks/{id}/approve` | Approve/deny high-risk work |
| `POST` | `/tasks/{id}/execute` | Run the plan (add `?mode=workflow` for the durable path) |
| `POST` | `/tasks/{id}/execute/stream` | Run the plan with an SSE progress stream |
| `GET` | `/tasks/{id}/events` | Execution event log |
| `GET` | `/executions/{id}` | Full execution summary/evidence |
| `POST` | `/executions/{id}/stages/{sid}/verification` | Report real repo check results (tests/lint/…) |
| `POST` | `/executions/{id}/stages/{sid}/artifacts` | Record files/patches written by the extension |
| `GET` | `/executions/{id}/artifacts` | List recorded artifacts |
| `POST` | `/executions/{id}/changes` | Record workspace file changes (worker/extension) |
| `GET` | `/executions/{id}/changes` | List workspace file changes |
| `POST` | `/workspaces` | Create an execution workspace (repo, commands, env, allowlist) |
| `GET` | `/workspaces?pending=true` | Workspaces with queued tool requests (for runners) |
| `GET` | `/workspaces/{id}` | Workspace state |
| `POST` | `/workspaces/{id}/state` | Runner-reported state (base/head commit, status) |
| `POST` | `/workspaces/{id}/secrets` | Store a workspace secret (values never returned by the API) |
| `GET` | `/workspaces/{id}/secrets` | List secret keys — values stay server-side |
| `PUT` | `/workspaces/{id}/mcp-servers` | Configure MCP servers for the agent (stdio/http) |
| `GET` | `/workspaces/{id}/mcp-servers` | Read MCP server config |
| `POST` | `/workspaces/{id}/deliver` | Delivery: commit → push → PR (push/PR are approval-gated) |
| `POST` | `/workspaces/{id}/stop` · `/resume` | Workspace lifecycle |
| `POST` | `/workspaces/{id}/tool-requests` | Dispatch a command through the security gate |
| `GET` | `/workspaces/{id}/tool-requests` | List tool requests |
| `GET` | `/workspaces/{id}/tool-requests/next` | Runner long-poll: claim the next operation |
| `POST` | `/workspaces/{id}/tool-requests/{rid}/result` | Runner: post the operation result |
| `POST` | `/workspaces/{id}/tool-requests/{rid}/approve` | Approve/deny a gated command |
| `POST` | `/workers/register` · `/workers/{id}/heartbeat` | Worker registry |

Example: intake → approve (if high-risk) → execute (sync or workflow) → inspect:

```bash
curl -X POST localhost:8787/tasks -H 'Content-Type: application/json' \
  -d '{"prompt": "Add role-based permissions to the admin API"}'

curl -X POST localhost:8787/tasks/<id>/approve -H 'Content-Type: application/json' \
  -d '{"approved": true}'

curl -X POST "localhost:8787/tasks/<id>/execute?mode=workflow"   # durable, long-running
curl -X POST  localhost:8787/tasks/<id>/execute/stream           # SSE progress
curl localhost:8787/executions/<execution_id>                     # audit summary
```

---

## Configuration

| Setting | Where | Purpose |
| ------- | ----- | ------- |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | secret / vars | OpenAI-compatible provider |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` | secret / vars | Anthropic provider |
| `PROVIDER_ORDER` | vars | Provider preference |
| `MAX_ATTEMPTS_PER_STAGE` | vars | Attempts before a stage fails |
| `DEFAULT_BUDGET_USD` | vars | Default cost budget (enforced) |
| `ALLOWED_ORIGINS` | vars | CORS origins (comma-separated) |
| `RATE_LIMIT_PER_MINUTE` | vars | Per-IP rate limit on mutations |
| `API_TOKEN` | secret | Optional bearer token required on all routes |

The model catalog (`src/domain/catalog.py`) and routing tiers
(`src/domain/routing.py`) are where you tune models and prices.

---

## Design notes

- **LLM-driven planning only** — the plan comes exclusively from a plan-capable
  model (strict JSON validation with a 3-attempt refinement loop). There is no
  deterministic template fallback: if no provider is configured or the model
  can't produce a valid plan, `POST /tasks` fails loudly with a 503.
- **Execution modes** — synchronous for small tasks and demos; the durable
  Workflow (`?mode=workflow`) for production tasks that outlive a request.
- **Verification honesty** — repo-required checks are limitations until real
  results are posted back; failed reports trigger escalation.
- **Worker hardening** — every command is kernel-capped (CPU/memory rlimits),
  secret-redacted, and approval-gated before it reaches a runner; the worker
  executes requests sequentially so parallel stages never corrupt files.
- **Learning** — `routing_stats` aggregates per (kind, risk, model) outcomes;
  routing penalizes models with poor success records.

## License

MIT
