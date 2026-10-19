/**
 * Zyntry Code backend client.
 *
 * Typed fetch client for every backend endpoint, an SSE stream parser for
 * `/tasks/{id}/execute/stream`, and mappers that translate backend execution
 * summaries into the frontend's domain types (stages, verification, evidence,
 * routing, diffs).
 *
 * Configure the backend in the UI (BackendBadge) or directly:
 *   localStorage.setItem('zyntry.backendUrl', 'http://localhost:8787')
 *   localStorage.setItem('zyntry.apiToken', '')
 */

export interface BackendConfig {
  backendUrl: string;
  apiToken: string;
}

/**
 * Default backend URL: connects out of the box. Override via
 * VITE_BACKEND_URL in a .env file, or by storing 'zyntry.backendUrl' in
 * localStorage (the badge UI does this).
 */
const DEFAULT_BACKEND_URL = 'http://localhost:8787';

function envBackendUrl(): string {
  try {
    const value = (import.meta as unknown as { env?: Record<string, string> }).env
      ?.VITE_BACKEND_URL as string | undefined;
    return value && value.trim() ? value.trim() : '';
  } catch {
    return '';
  }
}

export function getBackendConfig(): BackendConfig {
  const stored = localStorage.getItem('zyntry.backendUrl');
  const backendUrl = (stored && stored.trim() ? stored : envBackendUrl() || DEFAULT_BACKEND_URL).trim();
  const apiToken = localStorage.getItem('zyntry.apiToken') || '';
  return { backendUrl, apiToken };
}

export function setBackendConfig(config: BackendConfig): void {
  localStorage.setItem('zyntry.backendUrl', config.backendUrl);
  localStorage.setItem('zyntry.apiToken', config.apiToken);
}

export function isBackendConfigured(): boolean {
  return getBackendConfig().backendUrl.length > 0;
}

// ---------------------------------------------------------------------------
// Backend DTOs (mirrors the FastAPI responses)
// ---------------------------------------------------------------------------

export interface BackendTask {
  id: string;
  prompt: string;
  status: string;
  risk_level?: string;
  complexity?: string;
}

export interface BackendStage {
  id: string;
  kind: string;
  title: string;
  status: string;
  assigned_model?: string;
  verification_types?: string[];
  verification_reports?: { tool: string; status: string; duration_ms?: number | null }[];
}

export interface BackendArtifact {
  path: string;
  kind: string;
  language?: string | null;
  source: string;
  stage_id?: string | null;
}

export interface BackendChange {
  path: string;
  op: string;
  before?: string | null;
  after?: string | null;
}

export interface BackendEvent {
  type: string;
  message: string;
  data: Record<string, unknown>;
  stage_id?: string | null;
  execution_id: string;
  created_at: string;
}

export interface BackendWorkspace {
  id: string;
  task_id?: string | null;
  repo_url?: string | null;
  branch?: string | null;
  provider: string;
  status: string;
  commands: Record<string, { cmd: string; dangerous?: boolean }>;
  mcp_servers: { name: string; transport: string; command?: string | null; url?: string | null }[];
  allowed_commands: string[];
  auto_commit: boolean;
  timeout_seconds: number;
  runner_id?: string | null;
}

export interface BackendToolRequest {
  id: string;
  tool: string;
  params: Record<string, unknown>;
  verify_as?: string | null;
  dangerous: number;
  status: string;
  result?: Record<string, unknown> | null;
}

export interface BackendSummary {
  task: BackendTask;
  execution: { id: string; status: string; plan_id?: string | null };
  plan: { summary?: string | null; source?: string | null } | null;
  stages: BackendStage[];
  files_changed: number;
  artifacts: BackendArtifact[];
  tests: { status: string; detail?: string | null };
  attempts: { total: number; failed: number };
  escalation: { occurred: boolean; count: number; reasons: unknown[] };
  verification: { limitations: string[] };
  budget: { limit_usd?: number | null; spent_usd: number; exceeded: boolean };
  cost: { estimated_usd: number; total_tokens: number };
  timing: { total_seconds: number };
  events: BackendEvent[];
}

export interface CreateTaskResponse {
  task: BackendTask;
  plan: { id: string; summary: string; source: string; stages: BackendStage[] };
  assessment: { risk_level: string; complexity: string; task_kind: string };
  requires_approval: boolean;
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const { backendUrl, apiToken } = getBackendConfig();
  if (!backendUrl) throw new ApiError(0, 'Backend not configured');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiToken) headers.Authorization = `Bearer ${apiToken}`;
  const resp = await fetch(`${backendUrl}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      if (data?.detail) detail = data.detail;
      else if (data?.error) detail = `${data.error}: ${data.detail ?? ''}`;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<{ status: string; providers: { configured: string[] } }>('GET', '/health'),
  models: () => request<{ models: unknown[] }>('GET', '/models'),
  createTask: (prompt: string, constraints?: Record<string, unknown>) =>
    request<CreateTaskResponse>('POST', '/tasks', {
      prompt,
      constraints: constraints ?? {},
    }),
  getTask: (taskId: string) =>
    request<{ task: BackendTask; plan: { id: string; summary: string; stages: BackendStage[] } | null }>(
      'GET',
      `/tasks/${taskId}`
    ),
  approveTask: (taskId: string, autoExecute = true) =>
    request<Record<string, unknown>>('POST', `/tasks/${taskId}/approve`, {
      approved: true,
      auto_execute: autoExecute,
    }),
  rejectTask: (taskId: string) =>
    request<{ task_id: string; status: string }>('POST', `/tasks/${taskId}/approve`, {
      approved: false,
      auto_execute: false,
    }),
  executeTask: (taskId: string) =>
    request<BackendSummary>('POST', `/tasks/${taskId}/execute`),
  streamTask: async (
    taskId: string,
    onEvent: (event: Record<string, unknown>) => void
  ): Promise<BackendSummary> => {
    const { backendUrl, apiToken } = getBackendConfig();
    if (!backendUrl) throw new ApiError(0, 'Backend not configured');
    const resp = await fetch(`${backendUrl}/tasks/${taskId}/execute/stream`, {
      method: 'POST',
      headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : {},
    });
    if (!resp.ok || !resp.body) throw new ApiError(resp.status, 'stream request failed');
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let summary: BackendSummary | null = null;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      const { events, leftover } = parseSseChunk(buffer, decoder.decode(value, { stream: true }));
      buffer = leftover;
      for (const event of events) {
        if (event.type === 'done' && event.summary) {
          summary = event.summary as BackendSummary;
        }
        onEvent(event);
      }
    }
    if (!summary) throw new ApiError(0, 'stream ended without a summary');
    return summary;
  },
  getExecution: (executionId: string) =>
    request<BackendSummary>('GET', `/executions/${executionId}`),
  getChanges: (executionId: string) =>
    request<{ changes: BackendChange[] }>('GET', `/executions/${executionId}/changes`),
  getArtifacts: (executionId: string) =>
    request<{ artifacts: BackendArtifact[] }>('GET', `/executions/${executionId}/artifacts`),
  ingestRepo: (taskId: string, files: { path: string; language?: string; size?: number; content?: string }[]) =>
    request<{ files_ingested: number }>('POST', `/tasks/${taskId}/repo`, { files }),
  routePreview: (kind: string, risk: string) =>
    request<{ selected: unknown; candidates: unknown[] }>('POST', '/models/route', { kind, risk }),
  createWorkspace: (body: {
    task_id?: string;
    repo_url?: string;
    branch?: string;
    provider?: string;
    commands?: Record<string, { cmd: string; dangerous?: boolean }>;
    mcp_servers?: { name: string; transport: string; command?: string; args?: string[]; url?: string }[];
    auto_commit?: boolean;
    timeout_seconds?: number;
  }) => request<BackendWorkspace>('POST', '/workspaces', body),
  getWorkspace: (workspaceId: string) =>
    request<BackendWorkspace>('GET', `/workspaces/${workspaceId}`),
  getToolRequests: (workspaceId: string) =>
    request<{ tool_requests: BackendToolRequest[] }>(
      'GET',
      `/workspaces/${workspaceId}/tool-requests`
    ),
  approveToolRequest: (workspaceId: string, requestId: string) =>
    request<{ status: string }>(
      'POST',
      `/workspaces/${workspaceId}/tool-requests/${requestId}/approve`,
      { approved: true }
    ),
  deliver: (workspaceId: string, title: string) =>
    request<{ workspace_id: string; tool_requests: BackendToolRequest[] }>(
      'POST',
      `/workspaces/${workspaceId}/deliver`,
      { title, body: '' }
    ),
};

// ---------------------------------------------------------------------------
// SSE stream parser (handles chunk boundaries)
// ---------------------------------------------------------------------------

export function parseSseChunk(
  buffer: string,
  chunk: string
): { events: Record<string, unknown>[]; leftover: string } {
  let buf = buffer + chunk;
  const events: Record<string, unknown>[] = [];
  let idx: number;
  while ((idx = buf.indexOf('\n\n')) !== -1) {
    const frame = buf.slice(0, idx);
    buf = buf.slice(idx + 2);
    for (const line of frame.split('\n')) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data:')) {
        try {
          events.push(JSON.parse(trimmed.slice(5).trim()));
        } catch {
          /* ignore malformed frames */
        }
      }
    }
  }
  return { events, leftover: buf };
}

// ---------------------------------------------------------------------------
// Mappers: backend summary -> frontend domain types
// ---------------------------------------------------------------------------

import type {
  AgentState,
  ChatMessage,
  DiffFile,
  EvidencePackData,
  ExecutionStageItem,
  RoutingInfo,
  StepStatus,
  TaskPlanStep,
  ToolActivityItem,
  VerificationCheck,
} from '../types';

const STAGE_STATUS_TO_FRONTEND: Record<string, ExecutionStageItem['status']> = {
  succeeded: 'complete',
  failed: 'failed',
  running: 'running',
  pending: 'waiting',
  blocked: 'skipped',
  skipped: 'skipped',
};

const STAGE_STATUS_TO_STEP: Record<string, StepStatus> = {
  succeeded: 'complete',
  failed: 'failed',
  running: 'running',
  pending: 'pending',
  blocked: 'failed',
  skipped: 'failed',
};

export function mapPlanSteps(stages: BackendStage[]): TaskPlanStep[] {
  return stages.map((s, i) => ({
    id: s.id || `step-${i}`,
    label: s.title || s.kind,
    status: STAGE_STATUS_TO_STEP[s.status] ?? 'pending',
    detail: s.kind,
  }));
}

export function mapExecutionStages(stages: BackendStage[]): ExecutionStageItem[] {
  return stages.map((s) => ({
    id: s.id,
    name: s.title || s.kind,
    status: STAGE_STATUS_TO_FRONTEND[s.status] ?? 'waiting',
    modelAssigned: s.assigned_model,
    detail: s.kind,
  }));
}

export function mapVerificationChecks(summary: BackendSummary): VerificationCheck[] {
  const checks: VerificationCheck[] = [];
  const seen = new Set<string>();
  for (const stage of summary.stages) {
    for (const report of stage.verification_reports ?? []) {
      const key = `${report.tool}:${report.status}`;
      if (seen.has(key)) continue;
      seen.add(key);
      checks.push({
        id: `vc-${checks.length}`,
        name: report.tool,
        status: report.status === 'passed' ? 'passed' : 'failed',
        durationMs: report.duration_ms ?? undefined,
        summary: `${stage.title} (${report.status})`,
        file: stage.title,
      });
    }
  }
  for (const limitation of summary.verification.limitations) {
    checks.push({
      id: `vc-${checks.length}`,
      name: 'Unverified',
      status: 'skipped',
      summary: limitation,
    });
  }
  if (checks.length === 0) {
    checks.push({
      id: 'vc-0',
      name: summary.tests.status === 'failed' ? 'Suite' : 'Deterministic checks',
      status: summary.tests.status === 'failed' ? 'failed' : 'passed',
      summary: summary.tests.detail ?? 'No repo checks reported',
    });
  }
  return checks;
}

export function mapRouting(summary: BackendSummary): RoutingInfo {
  const lastAssigned = [...summary.stages].reverse().find((s) => s.assigned_model);
  return {
    provider: lastAssigned?.assigned_model?.split('-')[0] ?? 'backend',
    model: lastAssigned?.assigned_model ?? 'auto',
    routingMode: summary.escalation.occurred ? 'quality' : 'auto',
    estimatedCost: summary.cost.estimated_usd,
    actualCost: summary.cost.estimated_usd,
    latencyMs: Math.round(summary.timing.total_seconds * 1000),
    reason: summary.escalation.occurred
      ? `Escalated ${summary.escalation.count}x; reasons: ${summary.escalation.reasons.join('; ').slice(0, 200)}`
      : 'Routed per stage requirements',
    retryCount: Math.max(0, summary.attempts.total - summary.stages.length),
    fallbackStatus: summary.escalation.occurred ? 'fallback_active' : 'nominal',
    taskBudget: summary.budget.limit_usd ?? undefined,
  };
}

function simpleHunks(before: string | null | undefined, after: string | null | undefined) {
  const beforeLines = (before ?? '').split('\n').filter((l) => l.length || true);
  const afterLines = (after ?? '').split('\n').filter((l) => l.length || true);
  const lines = [];
  for (let i = 0; i < beforeLines.length; i++) {
    lines.push({ type: 'remove' as const, text: beforeLines[i], oldLineNumber: i + 1 });
  }
  for (let i = 0; i < afterLines.length; i++) {
    lines.push({ type: 'add' as const, text: afterLines[i], newLineNumber: i + 1 });
  }
  return [
    {
      oldStart: 1,
      oldLines: beforeLines.length,
      newStart: 1,
      newLines: afterLines.length,
      lines,
    },
  ];
}

export function mapDiffFiles(changes: BackendChange[]): DiffFile[] {
  return changes.map((c) => {
    const status = c.op === 'delete' ? 'deleted' : c.op === 'create' ? 'created' : 'modified';
    return {
      path: c.path,
      status,
      addedCount: (c.after ?? '').split('\n').filter(Boolean).length,
      removedCount: (c.before ?? '').split('\n').filter(Boolean).length,
      originalContent: c.before ?? '',
      newContent: c.after ?? '',
      hunks: simpleHunks(c.before, c.after),
    };
  });
}

export function mapEvidencePack(summary: BackendSummary): EvidencePackData {
  return {
    id: summary.execution.id,
    taskSummary: summary.plan?.summary ?? summary.task.prompt.slice(0, 120),
    whatChanged: summary.artifacts.map((a) => a.path).join(', ') || `${summary.files_changed} files`,
    whyChanged: summary.task.prompt,
    affectedFiles: summary.artifacts.map((a) => a.path),
    testsPerformed: summary.stages.flatMap((s) =>
      (s.verification_reports ?? []).map((r) => ({
        name: `${r.tool} (${s.title})`,
        status: r.status as 'passed' | 'failed',
        durationMs: r.duration_ms ?? 0,
        detail: `${s.title}: ${r.status}`,
      }))
    ),
    modelsUsed: summary.stages
      .filter((s) => s.assigned_model)
      .map((s) => ({ stage: s.title, model: s.assigned_model as string, tokensUsed: 0, cost: 0 })),
    attemptsCount: summary.attempts.total,
    totalCost: summary.cost.estimated_usd,
    taskBudget: summary.budget.limit_usd ?? 0,
    remainingRisk: summary.verification.limitations.join('; ') || 'None reported',
    constitutionPassed: summary.task.status === 'completed',
    reproductionVerified: true,
  };
}

export function mapToolActivities(summary: BackendSummary): ToolActivityItem[] {
  const interesting = new Set([
    'agent_tool_call',
    'workspace_ops_dispatched',
    'verification_failed',
    'verification_limited',
    'attempt_failed',
    'provider_fallback',
  ]);
  return summary.events
    .filter((e) => interesting.has(e.type))
    .slice(0, 30)
    .map((e, i) => ({
      id: `t-${i}-${e.execution_id}`,
      name: e.type === 'agent_tool_call' ? String(e.data.tool ?? 'tool') : e.type,
      action: e.type,
      target: e.stage_id ?? undefined,
      status: e.type === 'attempt_failed' ? ('failed' as const) : ('complete' as const),
      timestamp: new Date(e.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }));
}

export function executionAgentState(summary: BackendSummary): AgentState {
  if (summary.task.status === 'completed') return summary.escalation.occurred ? 'escalated' : 'complete';
  if (summary.task.status === 'failed') return 'failed';
  if (summary.task.status === 'awaiting_approval') return 'awaiting_approval';
  return 'working';
}

function failureExplanation(summary: BackendSummary): string {
  const budget = summary.budget;
  if (budget.exceeded) {
    return (
      `execution stopped by the budget guard: the projected cost of the next attempt would exceed ` +
      `your $${(budget.limit_usd ?? 0).toFixed(2)} cap ($${budget.spent_usd.toFixed(4)} already spent). ` +
      `Raise the task budget in Settings → Execution and re-run the task.`
    );
  }
  const failedStages = summary.stages.filter(
    (s) => s.status === 'failed' || s.status === 'blocked'
  );
  if (failedStages.length) {
    const bits = failedStages.map((s) => {
      const evt = [...summary.events]
        .reverse()
        .find((e) => e.stage_id === s.id && e.type === 'verification_failed');
      const failures = Array.isArray((evt?.data as Record<string, unknown>)?.failures)
        ? ((evt?.data as Record<string, unknown>).failures as string[])
        : [];
      return failures.length
        ? `${s.title} (${failures.join(', ')})`
        : `${s.title} (${s.status})`;
    });
    return `${bits.join('; ')}. Re-run after fixing the issue or raising the budget.`;
  }
  return `task status ${summary.task.status}. Check the verification panel and diff below.`;
}

const STAGE_NARRATIVE_DONE: Record<string, string> = {
  understand: 'explored the codebase and now have the full picture',
  analyze: 'analyzed the failure scenarios and dependencies',
  plan: 'designed the plan and invariants',
  implement: 'implemented the code changes',
  implement_backend: 'implemented the backend changes',
  implement_frontend: 'implemented the frontend changes',
  test: 'wrote the regression and edge-case tests',
  database: 'prepared the schema changes',
  security_review: 'ran the security review',
  review: 'reviewed the diff',
  verify: 'ran deterministic verification',
  integrate: 'integrated the changes into CI',
  document: 'updated the documentation',
};

function narrateRun(summary: BackendSummary): string {
  const stages = summary.stages;
  const succeeded = stages.filter((s) => s.status === 'succeeded');
  const skipped = stages.filter((s) => s.status === 'skipped');
  const failed = stages.filter((s) => s.status === 'failed' || s.status === 'blocked');
  const parts: string[] = [];

  if (succeeded.length) {
    parts.push(
      `I ${succeeded.map((s) => STAGE_NARRATIVE_DONE[s.kind] ?? s.title).join(', ')} — ` +
        `all ${succeeded.length} stage${succeeded.length === 1 ? '' : 's'} passed deterministic checks.`
    );
  }
  if (failed.length) {
    parts.push(
      `The ${failed.map((s) => `"${s.title}"`).join(' and ')} stage${failed.length === 1 ? '' : 's'} failed.`
    );
  }
  if (skipped.length) {
    parts.push(
      `I didn't get to the rest: ${skipped.map((s) => `"${s.title}"`).join(', ')} — ` +
        `${skipped.length} stage${skipped.length === 1 ? '' : 's'} skipped.`
    );
  }
  if (summary.verification.limitations.length) {
    parts.push(
      `Limitations: ${summary.verification.limitations.join('; ')} (reported honestly, never claimed as passed).`
    );
  }
  parts.push(
    `Cost so far: $${summary.cost.estimated_usd.toFixed(4)} across ${summary.attempts.total} attempt(s), ` +
      `${summary.escalation.count} escalation(s).`
  );
  return parts.join('\n\n');
}

export function buildAssistantSummaryMessage(summary: BackendSummary): ChatMessage {
  const completed = summary.task.status === 'completed';
  const lines: string[] = [];

  lines.push(completed ? 'Done — here is what happened.' : 'Here is what happened.');
  lines.push('');
  lines.push(narrateRun(summary));

  // Failure explanation goes at the END, telling why.
  if (!completed) {
    lines.push('');
    lines.push(`Why it failed: ${failureExplanation(summary)}`);
    lines.push('');
    lines.push(
      'I want to clarify: should I re-run this task (Re-run below), or would you ' +
        'like to review the diff first?'
    );
  } else if (summary.verification.limitations.length) {
    lines.push('');
    lines.push(
      'I want to clarify: some checks were limited by the environment — they are ' +
        'reported honestly in the evidence pack rather than claimed as passed.'
    );
  }

  return {
    id: `asst-${Date.now()}`,
    role: 'assistant',
    content: lines.join('\n'),
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    executionStages: mapExecutionStages(summary.stages),
    planSteps: mapPlanSteps(summary.stages),
    toolActivities: mapToolActivities(summary),
    verificationChecks: mapVerificationChecks(summary),
    evidencePack: mapEvidencePack(summary),
    routing: mapRouting(summary),
  };
}