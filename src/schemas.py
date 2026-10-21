"""Pydantic request schemas for the API."""

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=20_000, description="The engineering task description.")
    repo: str | None = Field(default=None, max_length=2_000, description="Optional repository path/URL context.")
    constraints: dict | None = Field(default=None, description="Optional constraints (budget, provider, max_attempts).")
    max_attempts_per_stage: int | None = Field(default=None, ge=1, le=5)
    budget_usd: float | None = Field(default=None, ge=0)


class RoutePreviewRequest(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64,
                      description="Stage kind, e.g. implement_backend, review, security_review.")
    risk: str = Field(default="medium", max_length=32,
                      description="Task risk level: low | medium | high | critical.")
    preferred_provider: str | None = Field(default=None, max_length=32)


class CompletionStreamRequest(BaseModel):
    """Parameters for a provider-backed token completion stream."""

    model: str = Field(..., min_length=1, max_length=128)
    prompt: str = Field(..., min_length=1, max_length=100_000)
    provider: str | None = Field(default=None, min_length=1, max_length=32)
    system: str | None = Field(default=None, max_length=20_000)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=8_192)


class ApproveRequest(BaseModel):
    approved: bool = True
    auto_execute: bool = False


class TaskMessageRequest(BaseModel):
    """A developer message sent mid-execution to steer the agent conversationally."""
    message: str = Field(..., min_length=1, max_length=2000)


class TaskConstraintsUpdate(BaseModel):
    """Merge additional constraints into a task (plan review exclusions, etc.)."""
    constraints: dict = Field(default_factory=dict, max_length=100)


class RepoFile(BaseModel):
    path: str = Field(..., min_length=1, max_length=1_000)
    language: str | None = Field(default=None, max_length=64)
    size: int | None = Field(default=0, ge=0)
    content: str | None = Field(default=None, max_length=512 * 1024)


class RepoIngestRequest(BaseModel):
    files: list[RepoFile] = Field(default_factory=list, max_length=500)


class VerificationReportRequest(BaseModel):
    tool: str = Field(..., min_length=1, max_length=64,
                      description="tests | lint | type_check | build | visual | security | benchmark | contract | migration")
    status: str = Field(..., pattern="^(passed|failed)$")
    output: str | None = Field(default=None, max_length=20_000)
    duration_ms: int | None = Field(default=None, ge=0)
    attempt_id: str | None = Field(default=None, max_length=128)


class ArtifactRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1_000)
    kind: str = Field(default="file", pattern="^(file|patch|result)$")
    language: str | None = Field(default=None, max_length=64)
    content: str | None = Field(default=None, max_length=512 * 1024)


class CommandSpec(BaseModel):
    cmd: str = Field(..., min_length=1, max_length=1_000)
    dangerous: bool = False


class WorkspaceCreate(BaseModel):
    task_id: str | None = None
    repo_url: str | None = Field(default=None, max_length=2_000)
    branch: str | None = Field(default=None, max_length=256,
                               pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    provider: str = Field(default="remote", pattern="^(remote|local)$")
    commands: dict[str, CommandSpec] = Field(default_factory=dict,
                                             description="{test: {cmd, dangerous}, lint: {...}, ...}")
    env: dict[str, str] = Field(default_factory=dict, max_length=32)
    allowed_commands: list[str] = Field(default_factory=list, max_length=64)
    auto_commit: bool = False
    timeout_seconds: int = Field(default=600, ge=10, le=7200)
    mcp_servers: list["McpServer"] = Field(default_factory=list)


class WorkspaceStateRequest(BaseModel):
    """Runner-reported workspace state updates (base commit, workdir, status, error)."""
    status: str | None = Field(default=None, pattern="^(provisioning|ready|running|stopped|failed|cleaned)$")
    base_commit: str | None = Field(default=None, max_length=256)
    head_commit: str | None = Field(default=None, max_length=256)
    workdir: str | None = Field(default=None, max_length=2_000)
    error: str | None = Field(default=None, max_length=2_000)


class WorkspaceAttachRequest(BaseModel):
    """Attach an existing (runner-owned) workspace to a task so the executor
    dispatches file ops and verification commands to it."""
    task_id: str = Field(..., min_length=1)


class ToolResultRequest(BaseModel):
    status: str = Field(..., pattern="^(succeeded|failed|timed_out|cancelled)$")
    result: dict = Field(default_factory=dict, max_length=500,
                         description="{stdout, stderr, exit_code, duration_ms, error, files:[{path, op, before, after}]}")


class ToolApproveRequest(BaseModel):
    approved: bool = True


class ToolDispatchRequest(BaseModel):
    """Dispatch a tool request into a workspace.

    ``tool=command.run`` goes through the security/approval gate; other tools
    (fs.write, git.commit, ...) are queued directly.
    """
    command: str | None = Field(default=None, min_length=1, max_length=1_000)
    tool: str = Field(default="command.run", min_length=1, max_length=64)
    params: dict = Field(default_factory=dict, max_length=100)


class ChangeRecordRequest(BaseModel):
    path: str = Field(..., min_length=1)
    op: str = Field(..., pattern="^(create|modify|delete)$")
    before: str | None = None
    after: str | None = None


class WorkerRegisterRequest(BaseModel):
    id: str | None = None
    name: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class SecretSetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str = Field(..., min_length=1, max_length=8_192)


class DeliverRequest(BaseModel):
    title: str = Field(default="Zyntry Code changes", max_length=256)
    body: str = Field(default="", max_length=20_000)
    base_branch: str | None = Field(default=None, max_length=256)


class McpServer(BaseModel):
    name: str = Field(..., min_length=1, max_length=64,
                      description="Identifier used in the agent's mcp.call tool.")
    transport: str = Field(default="stdio", pattern="^(stdio|http)$")
    command: str | None = Field(default=None, max_length=256, description="For stdio servers.")
    args: list[str] = Field(default_factory=list, max_length=32)
    url: str | None = Field(default=None, max_length=2_000, description="For http/streamable-http servers.")
    env: dict[str, str] = Field(default_factory=dict, max_length=32, description="Extra env for stdio servers.")


class McpServersRequest(BaseModel):
    servers: list[McpServer] = Field(default_factory=list, max_length=20)


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


class RetryStagesRequest(BaseModel):
    """Retry one or more failed stages, reusing prior outputs of others."""
    stage_ids: list[str] = Field(..., min_length=1, max_length=50)


class RepoRuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    kind: str = Field(..., pattern="^(regex|command|constitution)$")
    spec: str = Field(..., min_length=1, max_length=2000)
    enabled: bool = True


class RepoRulesRequest(BaseModel):
    rules: list[RepoRuleIn] = Field(default_factory=list, max_length=50)


class CiWebhookRequest(BaseModel):
    """CI posts this after a delivered push; the status lands on the task."""
    workspace_id: str = Field(..., min_length=1)
    status: str = Field(..., pattern="^(pending|running|success|failure|failed|cancelled)$")
    url: str | None = Field(default=None, max_length=2_000)
    detail: str | None = Field(default=None, max_length=500)
