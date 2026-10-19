export type AgentState =
  | 'idle'
  | 'planning'
  | 'working'
  | 'awaiting_approval'
  | 'applying_changes'
  | 'verifying'
  | 'complete'
  | 'failed'
  | 'escalated';

export type WorkspaceMode = 'ask' | 'edit' | 'agent';

export type RoutingMode = 'auto' | 'fast' | 'balanced' | 'quality';

export type ExecutionMode = 'auto' | 'custom';

export type StepStatus = 'pending' | 'running' | 'complete' | 'failed';

export type CheckStatus = 'passed' | 'failed' | 'running' | 'skipped';

export type ExecutionStageStatus = 'complete' | 'running' | 'waiting' | 'failed' | 'skipped';

export interface ExecutionStageItem {
  id: string;
  name: string;
  status: ExecutionStageStatus;
  modelAssigned?: string;
  durationMs?: number;
  cost?: number;
  detail?: string;
  parallelBranch?: string;
  handoffSummary?: string;
}

export interface BlastRadiusRisk {
  level: 'low' | 'medium' | 'high' | 'critical';
  score: number;
  affectedSubsystems: {
    name: string;
    sensitive: boolean;
    impact: string;
  }[];
  requiresStrongerModel: boolean;
  requiresDeepVerification: boolean;
}

export interface TaskPlanStep {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
  durationMs?: number;
}

export interface DiffLine {
  type: 'context' | 'add' | 'remove';
  text: string;
  oldLineNumber?: number;
  newLineNumber?: number;
}

export interface DiffHunk {
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: DiffLine[];
}

export interface DiffFile {
  path: string;
  status: 'modified' | 'created' | 'deleted';
  addedCount: number;
  removedCount: number;
  originalContent: string;
  newContent: string;
  hunks: DiffHunk[];
}

export interface VerificationCheck {
  id: string;
  name: string;
  status: CheckStatus;
  durationMs?: number;
  summary?: string;
  file?: string;
  suggestion?: string;
  command?: string;
  strategy?: 'unit' | 'types' | 'linter' | 'integration' | 'browser' | 'migration' | 'benchmark';
}

export interface RoutingInfo {
  provider: string;
  model: string;
  routingMode: RoutingMode;
  estimatedCost: number;
  actualCost: number;
  latencyMs: number;
  reason: string;
  retryCount: number;
  fallbackStatus: 'nominal' | 'retrying' | 'fallback_active';
  taskBudget?: number;
}

export interface ToolActivityItem {
  id: string;
  name: string;
  action: string;
  target?: string;
  status: 'running' | 'complete' | 'failed';
  timestamp: string;
  durationMs?: number;
}

export interface EvidencePackData {
  id: string;
  taskSummary: string;
  whatChanged: string;
  whyChanged: string;
  affectedFiles: string[];
  rootCause?: string;
  reproductionStep?: string;
  reproductionVerified: boolean;
  testsPerformed: {
    name: string;
    status: 'passed' | 'failed';
    durationMs: number;
    detail: string;
  }[];
  modelsUsed: {
    stage: string;
    model: string;
    tokensUsed: number;
    cost: number;
  }[];
  attemptsCount: number;
  totalCost: number;
  taskBudget: number;
  remainingRisk: string;
  constitutionPassed: boolean;
}

export interface ConstitutionRule {
  id: string;
  rule: string;
  category: 'architecture' | 'security' | 'database' | 'api';
  status: 'passed' | 'warning' | 'violated';
  detail: string;
}

export interface EngineeringMemoryItem {
  id: string;
  title: string;
  decision: string;
  context: string;
  date: string;
  subsystem: string;
}

export interface RuntimeIncidentSignal {
  id: string;
  source: 'sentry' | 'opentelemetry' | 'ci_pipeline' | 'runtime_log';
  title: string;
  traceId?: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  timestamp: string;
  correlatedFile: string;
  stackSummary: string;
}

export interface StageModelAssignment {
  stage: 'understanding' | 'planning' | 'implementation' | 'verification';
  label: string;
  model: string;
  provider: string;
  tier: 'fast' | 'balanced' | 'reasoning' | 'code';
}

export type AgentEvent =
  | { type: 'plan'; steps: string[] }
  | { type: 'tool'; name: string; status: 'running' | 'complete' | 'failed'; target?: string }
  | { type: 'diff'; files: DiffFile[] }
  | { type: 'verification'; check: string; status: 'running' | 'passed' | 'failed' | 'skipped' }
  | { type: 'routing'; model: string; provider: string; cost: number; reason: string }
  | { type: 'message'; content: string; role?: 'user' | 'assistant' | 'system' };

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  attachedFiles?: string[];
  planSteps?: TaskPlanStep[];
  toolActivities?: ToolActivityItem[];
  diffFiles?: DiffFile[];
  verificationChecks?: VerificationCheck[];
  routing?: RoutingInfo;
  executionStages?: ExecutionStageItem[];
  evidencePack?: EvidencePackData;
  blastRadius?: BlastRadiusRisk;
}

export interface TaskSession {
  id: string;
  title: string;
  createdAt: string;
  mode: WorkspaceMode;
  state: AgentState;
  branch: string;
  executionMode?: ExecutionMode;
  taskBudget?: number;
  backendTaskId?: string;
  backendExecutionId?: string;
  backendWorkspaceId?: string;
  messages: ChatMessage[];
  diffFiles: DiffFile[];
  verificationChecks: VerificationCheck[];
  routing: RoutingInfo;
  planSteps: TaskPlanStep[];
  toolActivities: ToolActivityItem[];
  executionStages?: ExecutionStageItem[];
  evidencePack?: EvidencePackData;
  blastRadius?: BlastRadiusRisk;
  constitutionRules?: ConstitutionRule[];
}
