import { 
  TaskSession, 
  DiffFile, 
  VerificationCheck, 
  RoutingInfo, 
  TaskPlanStep, 
  ToolActivityItem,
  ExecutionStageItem,
  EvidencePackData,
  BlastRadiusRisk,
  ConstitutionRule,
  EngineeringMemoryItem,
  RuntimeIncidentSignal,
  StageModelAssignment
} from '../types';

export const WORKSPACE_FILES = [
  'src/auth/session.ts',
  'src/auth/pkce.ts',
  'src/auth/tokens.ts',
  'src/api/routes.ts',
  'src/api/middleware.ts',
  'src/db/client.ts',
  'src/db/cache.ts',
  'src/services/billing.ts',
  'src/utils/logger.ts',
  'package.json',
  'tsconfig.json',
  'vitest.config.ts',
];

export const INITIAL_PLAN_STEPS: TaskPlanStep[] = [
  { id: 'step-1', label: 'Understand request', status: 'complete', detail: 'Analyzed token refresh concurrency requirement in active session manager', durationMs: 240 },
  { id: 'step-2', label: 'Inspect relevant files', status: 'complete', detail: 'Read src/auth/session.ts and src/auth/tokens.ts AST references', durationMs: 380 },
  { id: 'step-3', label: 'Propose changes', status: 'complete', detail: 'Introduced mutex-guarded refresh promise with deduplication queue', durationMs: 650 },
  { id: 'step-4', label: 'Verify result', status: 'complete', detail: 'Ran TypeScript checks and session concurrency unit tests', durationMs: 820 },
  { id: 'step-5', label: 'Apply approved changes', status: 'pending', detail: 'Awaiting human authorization before writing to disk' },
];

export const MOCK_EXECUTION_STAGES: ExecutionStageItem[] = [
  {
    id: 'stage-1',
    name: 'Understanding repository',
    status: 'complete',
    modelAssigned: 'Gemini 2.0 Flash-Lite',
    durationMs: 180,
    cost: 0.0006,
    detail: 'AST symbol tree parsed for SessionManager and downstream callers without raw prompt dumping.',
    handoffSummary: 'Identified single concurrency point in src/auth/session.ts line 39.',
  },
  {
    id: 'stage-2',
    name: 'Reproducing issue',
    status: 'complete',
    modelAssigned: 'Local Test Runner',
    durationMs: 340,
    cost: 0.0000,
    detail: 'Spawned 10 simultaneous getValidToken() invocations. Captured reproduction failure state.',
    handoffSummary: 'Captured failing stack: Error: Concurrent token refresh not allowed.',
  },
  {
    id: 'stage-3',
    name: 'Planning & Decomposition',
    status: 'complete',
    modelAssigned: 'Gemini 1.5 Pro',
    durationMs: 650,
    cost: 0.0092,
    detail: 'Decomposed into shared promise singleton, monotonic expiration check, and unit test harness.',
    handoffSummary: 'Handoff to implementation: Use promise memoization pattern with .finally() cleanup.',
  },
  {
    id: 'stage-4',
    name: 'Implementation',
    status: 'complete',
    modelAssigned: 'Claude 3.5 Sonnet',
    durationMs: 890,
    cost: 0.0067,
    detail: 'Parallel task execution: backend patch applied and concurrency unit test suite created.',
    parallelBranch: 'Parallel: Session Patch + Vitest Harness',
    handoffSummary: 'Unified diff generated. 19 lines added, 7 removed.',
  },
  {
    id: 'stage-5',
    name: 'Deterministic Verification',
    status: 'complete',
    modelAssigned: 'Vitest + tsc',
    durationMs: 540,
    cost: 0.0000,
    detail: '18 unit tests passed, 0 type errors, 0 lint warnings, architecture boundaries verified.',
    handoffSummary: 'All deterministic verification checks green.',
  },
  {
    id: 'stage-6',
    name: 'Review & Evidence Pack',
    status: 'complete',
    modelAssigned: 'Zyntry Supervisor',
    durationMs: 120,
    cost: 0.0000,
    detail: 'Synthesized Evidence Pack with blast radius analysis and root cause documentation.',
    handoffSummary: 'Ready for developer approval before disk mutation.',
  },
];

export const MOCK_BLAST_RADIUS: BlastRadiusRisk = {
  level: 'medium',
  score: 42,
  affectedSubsystems: [
    { name: 'Authentication & Session Store', sensitive: true, impact: 'Modified concurrency lock in token refresh lifecycle' },
    { name: 'Public API Contracts', sensitive: true, impact: 'Method signature unchanged, backward compatible' },
    { name: 'Database & Cache Layers', sensitive: false, impact: 'Zero mutations to query or cache layers' },
    { name: 'Tenant Isolation Boundary', sensitive: true, impact: 'Session isolation invariants intact' },
  ],
  requiresStrongerModel: true,
  requiresDeepVerification: true,
};

export const MOCK_EVIDENCE_PACK: EvidencePackData = {
  id: 'ev-auth-race-409',
  taskSummary: 'Deduplicate concurrent token refresh calls with singleton promise in SessionManager',
  whatChanged: 'Replaced naive boolean lock isRefreshing with a shared refreshPromise that coalesces multiple callers during token expiration.',
  whyChanged: 'Under burst traffic, simultaneous API requests received unhandled 409 rejections instead of waiting for the single active refresh.',
  affectedFiles: ['src/auth/session.ts', 'test/auth/session.test.ts'],
  rootCause: 'Race condition where concurrent callers reached getValidToken() while an asynchronous refresh was already in flight.',
  reproductionStep: 'Simulated 10 concurrent requests at T=0 during token expiration window. Captured 9 rejections.',
  reproductionVerified: true,
  testsPerformed: [
    { name: 'TypeScript Strict Typecheck', status: 'passed', durationMs: 240, detail: 'Zero compiler errors on strict mode' },
    { name: 'Concurrency Eviction Suite', status: 'passed', durationMs: 380, detail: '18 tests passed across 5 simulated parallel workers' },
    { name: 'ESLint Ruleset', status: 'passed', durationMs: 120, detail: 'Complies with project strict linter' },
    { name: 'Security Boundary Audit', status: 'passed', durationMs: 80, detail: 'No sensitive token data exposed in errors or logs' },
  ],
  modelsUsed: [
    { stage: 'Repository Understanding', model: 'Gemini 2.0 Flash-Lite', tokensUsed: 850, cost: 0.0006 },
    { stage: 'Planning & Architecture', model: 'Gemini 1.5 Pro', tokensUsed: 1840, cost: 0.0092 },
    { stage: 'Implementation', model: 'Claude 3.5 Sonnet', tokensUsed: 1420, cost: 0.0067 },
  ],
  attemptsCount: 1,
  totalCost: 0.0165,
  taskBudget: 0.2000,
  remainingRisk: 'Negligible. Existing public API signatures and return types are strictly preserved.',
  constitutionPassed: true,
};

export const MOCK_CONSTITUTION_RULES: ConstitutionRule[] = [
  {
    id: 'cr-1',
    rule: 'Controllers cannot access database directly',
    category: 'architecture',
    status: 'passed',
    detail: 'All data operations flow through services and repositories. Invariant strictly preserved.',
  },
  {
    id: 'cr-2',
    rule: 'Every tenant query must contain tenant_id predicate',
    category: 'database',
    status: 'passed',
    detail: 'No direct database queries touched in this patch. Schema boundary intact.',
  },
  {
    id: 'cr-3',
    rule: 'All external network calls require retries with exponential backoff',
    category: 'api',
    status: 'passed',
    detail: 'Refresh token provider incorporates jittered backoff retry policy.',
  },
  {
    id: 'cr-4',
    rule: 'Authentication secrets must never leak into log pipelines',
    category: 'security',
    status: 'passed',
    detail: 'Zero token strings logged; only token expiration timestamps referenced.',
  },
  {
    id: 'cr-5',
    rule: 'Session handlers must not introduce mutable global state',
    category: 'architecture',
    status: 'passed',
    detail: 'Singleton promise is instance-scoped on SessionManager.',
  },
];

export const MOCK_ENGINEERING_MEMORY: EngineeringMemoryItem[] = [
  {
    id: 'mem-1',
    title: 'Mutex Promise for Token Refresh Deduplication',
    decision: 'Used promise memoization with .finally() cleanup rather than distributed Redis locks for local worker efficiency.',
    context: 'Avoids network hop overhead on high-frequency token queries within a single container process.',
    date: 'Oct 2026',
    subsystem: 'src/auth/',
  },
  {
    id: 'mem-2',
    title: 'In-Memory LRU Eviction Ceiling of 64MB',
    decision: 'Set query cache memory boundary to 64MB with stale-while-revalidate to prevent V8 heap spikes during large exports.',
    context: 'Agreed upon during memory profiling benchmark on staging cluster.',
    date: 'Sep 2026',
    subsystem: 'src/db/cache.ts',
  },
  {
    id: 'mem-3',
    title: 'Monotonic Clock for Expiration Checks',
    decision: 'Adopted monotonic performance counter instead of Date.now() for time-sensitive leases to guard against NTP clock jumps.',
    context: 'Resolved intermittent false-positive session logouts during time synchronization sync.',
    date: 'Aug 2026',
    subsystem: 'src/auth/tokens.ts',
  },
];

export const MOCK_INCIDENT_SIGNALS: RuntimeIncidentSignal[] = [
  {
    id: 'inc-1',
    source: 'sentry',
    title: 'AUTH-CONCURRENCY-409: Concurrent token refresh not allowed in SessionManager',
    traceId: '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01',
    severity: 'high',
    timestamp: '12:41 PM (24 events)',
    correlatedFile: 'src/auth/session.ts:39',
    stackSummary: 'SessionManager.getValidToken -> throw Error("Concurrent token refresh not allowed")',
  },
  {
    id: 'inc-2',
    source: 'ci_pipeline',
    title: 'Vitest Regression: session concurrency test timed out',
    severity: 'medium',
    timestamp: '11:58 AM',
    correlatedFile: 'test/auth/session.test.ts:18',
    stackSummary: 'AssertionError: expected rejected promise to resolve',
  },
];

export const MOCK_STAGE_ASSIGNMENTS: StageModelAssignment[] = [
  {
    stage: 'understanding',
    label: 'Repository Understanding',
    model: 'Gemini 2.0 Flash-Lite',
    provider: 'Google Vertex AI',
    tier: 'fast',
  },
  {
    stage: 'planning',
    label: 'Decomposition & Planning',
    model: 'Gemini 1.5 Pro (Deep Reasoning)',
    provider: 'Google Vertex AI',
    tier: 'reasoning',
  },
  {
    stage: 'implementation',
    label: 'Code Generation & Patching',
    model: 'Claude 3.5 Sonnet',
    provider: 'Anthropic via Vertex',
    tier: 'code',
  },
  {
    stage: 'verification',
    label: 'Deterministic Verification',
    model: 'Local Sandbox (Vitest + tsc)',
    provider: 'Node.js Isolated VM',
    tier: 'fast',
  },
];

export const MOCK_DIFF_FILES_SESSION: DiffFile[] = [
  {
    path: 'src/auth/session.ts',
    status: 'modified',
    addedCount: 19,
    removedCount: 7,
    originalContent: `export class SessionManager {
  private activeToken: string | null = null;
  private isRefreshing: boolean = false;

  public async getValidToken(): Promise<string> {
    if (!this.activeToken || this.isExpired()) {
      if (this.isRefreshing) {
        throw new Error('Concurrent token refresh not allowed');
      }
      this.isRefreshing = true;
      this.activeToken = await this.refreshToken();
      this.isRefreshing = false;
    }
    return this.activeToken;
  }
}`,
    newContent: `export class SessionManager {
  private activeToken: string | null = null;
  private refreshPromise: Promise<string> | null = null;

  public async getValidToken(): Promise<string> {
    if (this.activeToken && !this.isExpired()) {
      return this.activeToken;
    }

    // Deduplicate in-flight token refreshes across concurrent callers
    if (!this.refreshPromise) {
      this.refreshPromise = this.refreshToken()
        .then((newToken) => {
          this.activeToken = newToken;
          return newToken;
        })
        .finally(() => {
          this.refreshPromise = null;
        });
    }

    return this.refreshPromise;
  }
}`,
    hunks: [
      {
        oldStart: 2,
        oldLines: 15,
        newStart: 2,
        newLines: 23,
        lines: [
          { type: 'context', text: 'export class SessionManager {', oldLineNumber: 1, newLineNumber: 1 },
          { type: 'context', text: '  private activeToken: string | null = null;', oldLineNumber: 2, newLineNumber: 2 },
          { type: 'remove', text: '  private isRefreshing: boolean = false;', oldLineNumber: 3 },
          { type: 'add', text: '  private refreshPromise: Promise<string> | null = null;', newLineNumber: 3 },
          { type: 'context', text: '', oldLineNumber: 4, newLineNumber: 4 },
          { type: 'context', text: '  public async getValidToken(): Promise<string> {', oldLineNumber: 5, newLineNumber: 5 },
          { type: 'remove', text: '    if (!this.activeToken || this.isExpired()) {', oldLineNumber: 6 },
          { type: 'remove', text: '      if (this.isRefreshing) {', oldLineNumber: 7 },
          { type: 'remove', text: '        throw new Error(\'Concurrent token refresh not allowed\');', oldLineNumber: 8 },
          { type: 'remove', text: '      }', oldLineNumber: 9 },
          { type: 'remove', text: '      this.isRefreshing = true;', oldLineNumber: 10 },
          { type: 'remove', text: '      this.activeToken = await this.refreshToken();', oldLineNumber: 11 },
          { type: 'remove', text: '      this.isRefreshing = false;', oldLineNumber: 12 },
          { type: 'remove', text: '    }', oldLineNumber: 13 },
          { type: 'add', text: '    if (this.activeToken && !this.isExpired()) {', newLineNumber: 6 },
          { type: 'add', text: '      return this.activeToken;', newLineNumber: 7 },
          { type: 'add', text: '    }', newLineNumber: 8 },
          { type: 'add', text: '', newLineNumber: 9 },
          { type: 'add', text: '    // Deduplicate in-flight token refreshes across concurrent callers', newLineNumber: 10 },
          { type: 'add', text: '    if (!this.refreshPromise) {', newLineNumber: 11 },
          { type: 'add', text: '      this.refreshPromise = this.refreshToken()', newLineNumber: 12 },
          { type: 'add', text: '        .then((newToken) => {', newLineNumber: 13 },
          { type: 'add', text: '          this.activeToken = newToken;', newLineNumber: 14 },
          { type: 'add', text: '          return newToken;', newLineNumber: 15 },
          { type: 'add', text: '        })', newLineNumber: 16 },
          { type: 'add', text: '        .finally(() => {', newLineNumber: 17 },
          { type: 'add', text: '          this.refreshPromise = null;', newLineNumber: 18 },
          { type: 'add', text: '        });', newLineNumber: 19 },
          { type: 'add', text: '    }', newLineNumber: 20 },
          { type: 'add', text: '', newLineNumber: 21 },
          { type: 'add', text: '    return this.refreshPromise;', newLineNumber: 22 },
          { type: 'context', text: '  }', oldLineNumber: 14, newLineNumber: 23 },
          { type: 'context', text: '}', oldLineNumber: 15, newLineNumber: 24 },
        ],
      },
    ],
  },
  {
    path: 'test/auth/session.test.ts',
    status: 'created',
    addedCount: 14,
    removedCount: 0,
    originalContent: '',
    newContent: `describe('SessionManager concurrency', () => {
  it('deduplicates parallel getValidToken calls into single refresh request', async () => {
    const session = new SessionManager();
    const calls = await Promise.all([
      session.getValidToken(),
      session.getValidToken(),
      session.getValidToken()
    ]);
    expect(calls[0]).toBe(calls[1]);
    expect(session.getRefreshCount()).toBe(1);
  });
});`,
    hunks: [
      {
        oldStart: 0,
        oldLines: 0,
        newStart: 1,
        newLines: 14,
        lines: [
          { type: 'add', text: 'describe(\'SessionManager concurrency\', () => {', newLineNumber: 1 },
          { type: 'add', text: '  it(\'deduplicates parallel getValidToken calls into single refresh request\', async () => {', newLineNumber: 2 },
          { type: 'add', text: '    const session = new SessionManager();', newLineNumber: 3 },
          { type: 'add', text: '    const calls = await Promise.all([', newLineNumber: 4 },
          { type: 'add', text: '      session.getValidToken(),', newLineNumber: 5 },
          { type: 'add', text: '      session.getValidToken(),', newLineNumber: 6 },
          { type: 'add', text: '      session.getValidToken()', newLineNumber: 7 },
          { type: 'add', text: '    ]);', newLineNumber: 8 },
          { type: 'add', text: '    expect(calls[0]).toBe(calls[1]);', newLineNumber: 9 },
          { type: 'add', text: '    expect(session.getRefreshCount()).toBe(1);', newLineNumber: 10 },
          { type: 'add', text: '  });', newLineNumber: 11 },
          { type: 'add', text: '});', newLineNumber: 12 },
        ],
      },
    ],
  },
];

export const MOCK_VERIFICATIONS_PASSED: VerificationCheck[] = [
  {
    id: 'v1',
    name: 'TypeScript Strict Compiler',
    status: 'passed',
    durationMs: 240,
    summary: '0 diagnostics emitted. Strict null checks & return types verified.',
    strategy: 'types',
  },
  {
    id: 'v2',
    name: 'Vitest Concurrency Regression Suite',
    status: 'passed',
    durationMs: 380,
    summary: '18 unit tests passed across 5 simulated parallel workers.',
    strategy: 'unit',
  },
  {
    id: 'v3',
    name: 'ESLint Architecture & Guardrails',
    status: 'passed',
    durationMs: 120,
    summary: 'No circular dependencies, zero disallowed globals.',
    strategy: 'linter',
  },
  {
    id: 'v4',
    name: 'Project Constitution Compliance',
    status: 'passed',
    durationMs: 80,
    summary: '5/5 engineering rules verified against working tree.',
    strategy: 'benchmark',
  },
];

export const MOCK_VERIFICATIONS_FAILED: VerificationCheck[] = [
  {
    id: 'v1',
    name: 'TypeScript Strict Compiler',
    status: 'passed',
    durationMs: 280,
    summary: 'Types compiled successfully with 0 errors.',
    strategy: 'types',
  },
  {
    id: 'v2',
    name: 'Vitest Concurrency Regression Suite',
    status: 'failed',
    durationMs: 410,
    file: 'test/auth/session.test.ts:42',
    summary: 'Assertion failed: expected 1 refresh request, received 2.',
    suggestion: 'Escalate to Gemini 1.5 Pro to analyze concurrent clock-skew tolerance in eviction loop.',
    strategy: 'unit',
  },
  {
    id: 'v3',
    name: 'ESLint Architecture & Guardrails',
    status: 'passed',
    durationMs: 110,
    summary: 'Code formatting and style rules satisfied.',
    strategy: 'linter',
  },
];

export const MOCK_TOOL_ACTIVITIES_SESSION: ToolActivityItem[] = [
  {
    id: 't1',
    name: 'Searching AST references for getValidToken',
    action: 'symbol_search',
    target: 'src/auth/session.ts',
    status: 'complete',
    timestamp: '12:44 PM',
    durationMs: 140,
  },
  {
    id: 't2',
    name: 'Reproducing concurrency bug with synthetic harness',
    action: 'reproduce_failure',
    target: 'test/auth/session.test.ts',
    status: 'complete',
    timestamp: '12:44 PM',
    durationMs: 340,
  },
  {
    id: 't3',
    name: 'Running deterministic Vitest runner',
    action: 'run_tests',
    target: 'vitest.config.ts',
    status: 'complete',
    timestamp: '12:44 PM',
    durationMs: 380,
  },
];

export const MOCK_ROUTING_INFO: RoutingInfo = {
  provider: 'Google Vertex AI',
  model: 'Gemini 1.5 Pro (Adaptive Multi-Stage)',
  routingMode: 'auto',
  estimatedCost: 0.0200,
  actualCost: 0.0165,
  latencyMs: 540,
  reason: 'Auto mode routed repository discovery to Flash-Lite, architecture reasoning to Gemini Pro, and patch construction to Claude Sonnet.',
  retryCount: 0,
  fallbackStatus: 'nominal',
  taskBudget: 0.2000,
};

export const INITIAL_SESSIONS: TaskSession[] = [
  {
    id: 'task-auth-race',
    title: 'Fix token expiry race condition in session manager',
    createdAt: '12:44 PM',
    mode: 'agent',
    state: 'awaiting_approval',
    branch: 'fix/auth-race',
    executionMode: 'auto',
    taskBudget: 0.20,
    messages: [
      {
        id: 'm1',
        role: 'user',
        content: 'When multiple API requests trigger at the exact same moment on token expiration, SessionManager throws "Concurrent token refresh not allowed". Please deduplicate concurrent calls using a shared refresh promise so only one refresh request goes out.',
        timestamp: '12:44 PM',
        attachedFiles: ['src/auth/session.ts'],
      },
      {
        id: 'm2',
        role: 'assistant',
        content: 'I analyzed `src/auth/session.ts`. The root issue was an eager boolean lock `isRefreshing` that rejected simultaneous callers instead of coalescing them into the active refresh promise. I reproduced the issue first with a concurrency harness, decomposed the fix into a shared promise singleton pattern with `.finally()` cleanup, implemented the patch in parallel with a regression test, and ran deterministic verifications.',
        timestamp: '12:44 PM',
        planSteps: INITIAL_PLAN_STEPS,
        executionStages: MOCK_EXECUTION_STAGES,
        evidencePack: MOCK_EVIDENCE_PACK,
        blastRadius: MOCK_BLAST_RADIUS,
        toolActivities: MOCK_TOOL_ACTIVITIES_SESSION,
        diffFiles: MOCK_DIFF_FILES_SESSION,
        verificationChecks: MOCK_VERIFICATIONS_PASSED,
        routing: MOCK_ROUTING_INFO,
      },
    ],
    diffFiles: MOCK_DIFF_FILES_SESSION,
    verificationChecks: MOCK_VERIFICATIONS_PASSED,
    routing: MOCK_ROUTING_INFO,
    planSteps: INITIAL_PLAN_STEPS,
    toolActivities: MOCK_TOOL_ACTIVITIES_SESSION,
    executionStages: MOCK_EXECUTION_STAGES,
    evidencePack: MOCK_EVIDENCE_PACK,
    blastRadius: MOCK_BLAST_RADIUS,
    constitutionRules: MOCK_CONSTITUTION_RULES,
  },
  {
    id: 'task-cache-evict',
    title: 'Refactor database query cache with stale-while-revalidate',
    createdAt: '11:15 AM',
    mode: 'agent',
    state: 'failed',
    branch: 'feat/query-cache',
    executionMode: 'custom',
    taskBudget: 0.25,
    messages: [
      {
        id: 'm20',
        role: 'user',
        content: 'Implement stale-while-revalidate logic in `src/db/cache.ts` with LRU eviction when memory ceiling hits 64MB.',
        timestamp: '11:15 AM',
        attachedFiles: ['src/db/cache.ts'],
      },
      {
        id: 'm21',
        role: 'assistant',
        content: 'I created the eviction policy, but deterministic unit tests failed on clock-skew tolerance in `test/db/cache.test.ts:42`. We can either retry with an adjusted threshold or trigger verification escalation to pass the failure evidence to a stronger model.',
        timestamp: '11:16 AM',
        diffFiles: [],
        verificationChecks: MOCK_VERIFICATIONS_FAILED,
        routing: {
          ...MOCK_ROUTING_INFO,
          model: 'Gemini 2.5 Flash',
          routingMode: 'balanced',
          estimatedCost: 0.0052,
          actualCost: 0.0049,
          reason: 'Balanced mode selected for multi-method database cache implementation.',
          retryCount: 1,
          fallbackStatus: 'retrying',
        },
        executionStages: [
          { id: 's1', name: 'Understanding repository', status: 'complete', modelAssigned: 'Flash-Lite' },
          { id: 's2', name: 'Reproducing issue', status: 'complete', modelAssigned: 'Local Runner' },
          { id: 's3', name: 'Planning', status: 'complete', modelAssigned: 'Gemini Pro' },
          { id: 's4', name: 'Implementation', status: 'complete', modelAssigned: 'Flash Coder' },
          { id: 's5', name: 'Verification', status: 'failed', detail: 'Eviction clock-skew test assertion failure' },
          { id: 's6', name: 'Review', status: 'waiting' },
        ],
        planSteps: [
          { id: 's1', label: 'Understand request', status: 'complete' },
          { id: 's2', label: 'Inspect relevant files', status: 'complete' },
          { id: 's3', label: 'Propose changes', status: 'complete' },
          { id: 's4', label: 'Verify result', status: 'failed', detail: 'Unit test assertion failed on eviction threshold' },
          { id: 's5', label: 'Apply approved changes', status: 'pending' },
        ],
        toolActivities: [
          { id: 'ta1', name: 'Reading src/db/cache.ts', action: 'view_file', status: 'complete', timestamp: '11:15 AM' },
          { id: 'ta2', name: 'Running tests', action: 'run_tests', status: 'failed', timestamp: '11:15 AM' },
        ],
      },
    ],
    diffFiles: [],
    verificationChecks: MOCK_VERIFICATIONS_FAILED,
    routing: {
      ...MOCK_ROUTING_INFO,
      model: 'Gemini 2.5 Flash',
      routingMode: 'balanced',
      estimatedCost: 0.0052,
      actualCost: 0.0049,
      reason: 'Balanced mode selected for multi-method database cache implementation.',
      retryCount: 1,
      fallbackStatus: 'retrying',
    },
    planSteps: [
      { id: 's1', label: 'Understand request', status: 'complete' },
      { id: 's2', label: 'Inspect relevant files', status: 'complete' },
      { id: 's3', label: 'Propose changes', status: 'complete' },
      { id: 's4', label: 'Verify result', status: 'failed', detail: 'Unit test assertion failed on eviction threshold' },
      { id: 's5', label: 'Apply approved changes', status: 'pending' },
    ],
    toolActivities: [
      { id: 'ta1', name: 'Reading src/db/cache.ts', action: 'view_file', status: 'complete', timestamp: '11:15 AM' },
      { id: 'ta2', name: 'Running tests', action: 'run_tests', status: 'failed', timestamp: '11:15 AM' },
    ],
    executionStages: [
      { id: 's1', name: 'Understanding repository', status: 'complete', modelAssigned: 'Flash-Lite' },
      { id: 's2', name: 'Reproducing issue', status: 'complete', modelAssigned: 'Local Runner' },
      { id: 's3', name: 'Planning', status: 'complete', modelAssigned: 'Gemini Pro' },
      { id: 's4', name: 'Implementation', status: 'complete', modelAssigned: 'Flash Coder' },
      { id: 's5', name: 'Verification', status: 'failed', detail: 'Eviction clock-skew test assertion failure' },
      { id: 's6', name: 'Review', status: 'waiting' },
    ],
    constitutionRules: MOCK_CONSTITUTION_RULES,
  },
  {
    id: 'task-explain-repo',
    title: 'Explain repository architecture & security invariants',
    createdAt: 'Yesterday',
    mode: 'ask',
    state: 'complete',
    branch: 'main',
    executionMode: 'auto',
    taskBudget: 0.10,
    messages: [
      {
        id: 'm30',
        role: 'user',
        content: 'Explain how authentication, session management, and database query layers connect in this repository.',
        timestamp: 'Yesterday 4:10 PM',
      },
      {
        id: 'm31',
        role: 'assistant',
        content: 'This repository follows a layered architecture:\n\n1. Entry & Routing (src/api/): Express routes dispatching authenticated requests.\n2. Security & Tokens (src/auth/): JWT verification, token refresh deduplication, and cookie parsing.\n3. Data Layer (src/db/): Type-safe client wrapper with connection pooling and in-memory LRU caching.\n\nAll mutations run within transaction blocks, and auth tokens are verified prior to any handler invocation.',
        timestamp: 'Yesterday 4:11 PM',
        routing: {
          provider: 'Google Vertex AI',
          model: 'Gemini 2.5 Flash',
          routingMode: 'fast',
          estimatedCost: 0.0012,
          actualCost: 0.0011,
          latencyMs: 290,
          reason: 'Read-only architecture question routed to Fast model for minimal latency.',
          retryCount: 0,
          fallbackStatus: 'nominal',
        },
      },
    ],
    diffFiles: [],
    verificationChecks: [],
    routing: {
      provider: 'Google Vertex AI',
      model: 'Gemini 2.5 Flash',
      routingMode: 'fast',
      estimatedCost: 0.0012,
      actualCost: 0.0011,
      latencyMs: 290,
      reason: 'Read-only architecture question routed to Fast model for minimal latency.',
      retryCount: 0,
      fallbackStatus: 'nominal',
    },
    planSteps: [],
    toolActivities: [
      { id: 't-exp-1', name: 'Inspecting project tree', action: 'list_dir', status: 'complete', timestamp: '4:10 PM' },
      { id: 't-exp-2', name: 'Reading package.json dependencies', action: 'view_file', status: 'complete', timestamp: '4:10 PM' },
    ],
  },
];
