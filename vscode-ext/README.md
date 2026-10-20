# Zyntry Code — for VS Code

Run AI engineering tasks on the folder you have open — plan, approve, execute,
and review without leaving the editor.

## Quick start

1. **Install** the extension and reload VS Code.
2. Click the **Z** icon in the activity bar — the Zyntry dashboard opens in
   the sidebar: chat, plan stages, live execution stream, diffs, verification,
   and evidence packs. Prefer a wide view? Run **Zyntry: Open Dashboard**.
3. Describe a task. Zyntry plans it, asks for approval when a task is
   high-risk, executes, and reports back.

No extra setup for local runs — install, open the sidebar, and start coding.

## Dashboard (bundled UI)

The full Zyntry dashboard ships inside the `.vsix` — no separate app to run.
It is served by the extension from a loopback-only local server
(ports 8799–8803) and appears as a normal VS Code side panel.

> Refreshing the bundled UI: in `frontend/` run `npm ci && npm run build`,
> then copy `frontend/dist/` into `vscode-ext/dashboard/` and repackage.

## Commands

| Command | What it does |
| ------- | ------------ |
| **Zyntry: Open Dashboard** | Open the bundled dashboard (sidebar, editor tab, or system browser). |
| **Zyntry: Create Task** | Prompt for a task → shows the plan; offers approve (high-risk) or run. A 503 with a clear reason means no LLM provider is configured on the service. |
| **Zyntry: Approve / Reject Task** | Approve (optionally auto-execute) or reject a high-risk task. |
| **Zyntry: Run Task (sync)** | Execute → prints the audit summary. |
| **Zyntry: Run Task (stream)** | Execute with live SSE progress in the output channel. |
| **Zyntry: Ingest Repo Snapshot** | Uploads the open folder (code files only, size-capped) so planning/execution see real context. |
| **Zyntry: Create Workspace (local runner)** | Creates a `provider=local` workspace and stores its one-time runner token. |
| **Zyntry: Start / Stop Local Runner** | Long-polls pending workspaces and executes claimed tool requests **in your workspace folder** with plain JS (`fs`, `child_process`): `fs.list/read/write/edit/delete/search`, `git.status/diff/commit/push`, `command.run` (timeout + secret redaction). |

## Settings

| Setting | Default | Purpose |
| ------- | ------- | ------- |
| `zyntry.backendUrl` | `http://localhost:8787` | Zyntry service endpoint — works out of the box for local runs; point it at your deployed instance for remote setups |
| `zyntry.runnerPollSeconds` | `3` | Local runner poll interval |
| `zyntry.runnerMaxFiles` | `200` | Repo snapshot file cap |

## Security notes

- The per-workspace **runner token** is shown exactly once at workspace
  creation; keep it in the extension (it is required on every runner call).
- Command output is redacted against workspace `env` values before posting.
- `git.push` and `command.run` of dangerous commands only reach the runner
  after the approval gate releases them.
