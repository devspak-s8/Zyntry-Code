"""Pydantic request schemas for the API."""

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    prompt: str = Field(..., min_length=3, description="The engineering task description.")
    repo: str | None = Field(default=None, description="Optional repository path/URL context.")
    constraints: dict | None = Field(default=None, description="Optional constraints (budget, provider, max_attempts).")
    max_attempts_per_stage: int | None = Field(default=None, ge=1, le=5)
    budget_usd: float | None = Field(default=None, ge=0)


class RoutePreviewRequest(BaseModel):
    kind: str = Field(..., description="Stage kind, e.g. implement_backend, review, security_review.")
    risk: str = Field(default="medium", description="Task risk level: low | medium | high | critical.")
    preferred_provider: str | None = Field(default=None)


class CompletionStreamRequest(BaseModel):
    """Parameters for a provider-backed token completion stream."""

    model: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    system: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)


class ApproveRequest(BaseModel):
    approved: bool = True
    auto_execute: bool = False


class RepoFile(BaseModel):
    path: str = Field(..., min_length=1)
    language: str | None = None
    size: int | None = Field(default=0, ge=0)
    content: str | None = None


class RepoIngestRequest(BaseModel):
    files: list[RepoFile] = Field(default_factory=list, max_length=500)


class VerificationReportRequest(BaseModel):
    tool: str = Field(..., description="tests | lint | type_check | build | visual | security | benchmark | contract | migration")
    status: str = Field(..., pattern="^(passed|failed)$")
    output: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    attempt_id: str | None = None


class ArtifactRequest(BaseModel):
    path: str = Field(..., min_length=1)
    kind: str = Field(default="file", pattern="^(file|patch|result)$")
    language: str | None = None
    content: str | None = None


class CommandSpec(BaseModel):
    cmd: str = Field(..., min_length=1)
    dangerous: bool = False


class WorkspaceCreate(BaseModel):
    task_id: str | None = None
    repo_url: str | None = None
    branch: str | None = None
    provider: str = Field(default="remote", pattern="^(remote|local)$")
    commands: dict[str, CommandSpec] = Field(default_factory=dict,
                                             description="{test: {cmd, dangerous}, lint: {...}, ...}")
    env: dict[str, str] = Field(default_factory=dict)
    allowed_commands: list[str] = Field(default_factory=list)
    auto_commit: bool = False
    timeout_seconds: int = Field(default=600, ge=10, le=7200)
    mcp_servers: list["McpServer"] = Field(default_factory=list)


class WorkspaceStateRequest(BaseModel):
    """Runner-reported workspace state updates (base commit, workdir, status, error)."""
    status: str | None = Field(default=None, pattern="^(provisioning|ready|running|stopped|failed|cleaned)$")
    base_commit: str | None = None
    head_commit: str | None = None
    workdir: str | None = None
    error: str | None = None


class ToolResultRequest(BaseModel):
    status: str = Field(..., pattern="^(succeeded|failed|timed_out|cancelled)$")
    result: dict = Field(default_factory=dict,
                         description="{stdout, stderr, exit_code, duration_ms, error, files:[{path, op, before, after}]}")


class ToolApproveRequest(BaseModel):
    approved: bool = True


class ToolDispatchRequest(BaseModel):
    """Dispatch a tool request into a workspace.

    ``tool=command.run`` goes through the security/approval gate; other tools
    (fs.write, git.commit, ...) are queued directly.
    """
    command: str | None = Field(default=None, min_length=1)
    tool: str = Field(default="command.run")
    params: dict = Field(default_factory=dict)


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
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class DeliverRequest(BaseModel):
    title: str = Field(default="Zyntry Code changes")
    body: str = Field(default="")
    base_branch: str | None = None


class McpServer(BaseModel):
    name: str = Field(..., min_length=1, description="Identifier used in the agent's mcp.call tool.")
    transport: str = Field(default="stdio", pattern="^(stdio|http)$")
    command: str | None = Field(default=None, description="For stdio servers (e.g. 'npx -y @modelcontextprotocol/server-github').")
    args: list[str] = Field(default_factory=list)
    url: str | None = Field(default=None, description="For http/streamable-http servers.")
    env: dict[str, str] = Field(default_factory=dict, description="Extra env for stdio servers (values are stored as secrets, never logged).")


class McpServersRequest(BaseModel):
    servers: list[McpServer] = Field(default_factory=list, max_length=20)


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)
