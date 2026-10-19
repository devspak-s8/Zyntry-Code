# Zyntry Code — VS Code extension

The client half of Zyntry Code: drive tasks against the backend and run the
whole loop locally.

## Install (dev)

1. `code --install-extension` requires packaging (`@vscode/vsce`); for dev, open
   this folder in VS Code and press **F5** ("Run Extension").
2. Configure `zyntry.backendUrl` (default `http://localhost:8787`) and, if the
   backend enforces it, `zyntry.apiToken` in Settings.

## Commands

| Command | What it does |
| ------- | ------------ |
| **Zyntry: Create Task** | Prompt for a task → `POST /tasks` → shows the LLM-only plan; offers approve (high-risk) or run. A 503 with a clear reason means the backend has no configured LLM provider. |
| **Zyntry: Approve / Reject Task** | Approve (optionally auto-execute) or reject a high-risk task. |
| **Zyntry: Run Task (sync)** | `POST /tasks/{id}/execute` → prints the audit summary. |
| **Zyntry: Run Task (stream)** | `POST /tasks/{id}/execute/stream` → live SSE progress in the output channel. |
| **Zyntry: Ingest Repo Snapshot** | Uploads the open folder (code files only, size-capped) to `POST /tasks/{id}/repo` so planning/execution see real context. |
| **Zyntry: Create Workspace (local runner)** | Creates a `provider=local` workspace and stores its one-time runner token. |
| **Zyntry: Start / Stop Local Runner** | Long-polls `GET /workspaces?pending=true&provider=local` and executes claimed tool requests **in your workspace folder** with plain JS (`fs`, `child_process`): `fs.list/read/write/edit/delete/search`, `git.status/diff/commit/push`, `command.run` (timeout + secret redaction). |

## Settings

| Setting | Default | Purpose |
| ------- | ------- | ------- |
| `zyntry.backendUrl` | `http://localhost:8787` | Backend base URL |
| `zyntry.apiToken` | *(empty)* | Bearer token when the backend has `API_TOKEN` set |
| `zyntry.runnerPollSeconds` | `3` | Local runner poll interval |
| `zyntry.runnerMaxFiles` | `200` | Repo snapshot file cap |

## Security notes

- The per-workspace **runner token** is shown exactly once at workspace
  creation; keep it in the extension (it is required on every runner call).
- Command output is redacted against workspace `env` values before posting.
- `git.push` and `command.run` of dangerous commands only reach the runner
  after the backend's approval gate releases them.