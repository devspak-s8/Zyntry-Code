/**
 * Contextual narration for backend execution events.
 *
 * Turns raw stage events ("stage_succeeded", "stage_started", ...) into the
 * natural, conversational progress lines the way OpenCode / Codex / Claude
 * Code narrate their work ("Now I have the full picture…", "Writing the
 * patch…") instead of a bare "stage 1 passed" log.
 */

interface RawEvent {
  type?: string;
  message?: string;
  data?: Record<string, unknown>;
}

const STAGE_KIND_STARTED: Record<string, string> = {
  understand: 'Reading the codebase to build the full picture…',
  analyze: 'Tracing data flows, dependencies and invariants…',
  plan: 'Designing the plan and architecture…',
  implement: 'Writing the code changes…',
  implement_backend: 'Implementing backend changes…',
  implement_frontend: 'Implementing frontend changes…',
  test: 'Writing regression and edge-case tests…',
  database: 'Preparing schema changes…',
  security_review: 'Auditing for security issues…',
  review: 'Reviewing the diff…',
  verify: 'Running deterministic verification…',
  integrate: 'Integrating changes…',
  document: 'Documenting the changes…',
};

const STAGE_KIND_DONE: Record<string, string> = {
  understand: 'Now I have the full picture of the codebase.',
  analyze: 'Analysis complete — risks and dependencies mapped.',
  plan: 'Plan ready with invariants and stage breakdown.',
  implement: 'Code written and syntax-checked.',
  implement_backend: 'Backend code written and syntax-checked.',
  implement_frontend: 'Frontend code written and syntax-checked.',
  test: 'Tests drafted and staged for the repo runner.',
  database: 'Schema changes prepared.',
  security_review: 'Security review complete.',
  review: 'Diff reviewed.',
  verify: 'Verification finished.',
  integrate: 'Changes integrated.',
  document: 'Documentation written.',
};

const kindOf = (e: RawEvent): string => String(e.data?.kind ?? '');

export function narrateEvent(event: RawEvent): string | null {
  const type = String(event.type ?? '');
  const message = String(event.message ?? '');
  const kind = kindOf(event);

  switch (type) {
    case 'execution_started':
      return 'Kicking off the execution loop…';
    case 'stage_started': {
      if (kind === 'understand') return STAGE_KIND_STARTED.understand;
      return STAGE_KIND_STARTED[kind] ?? `Working on: ${message.replace(/^Stage:\s*/, '')}…`;
    }
    case 'stage_succeeded': {
      if (kind === 'understand') return STAGE_KIND_DONE.understand;
      return STAGE_KIND_DONE[kind] ?? message;
    }
    case 'stage_failed':
      return `This step failed: ${message}`;
    case 'stage_skipped':
      return message;
    case 'stage_blocked':
      return message;
    case 'stage_warning':
      return message;
    case 'agent_tool_call':
      return `Using tool: ${String(event.data?.tool ?? 'tool')}`;
    case 'workspace_ops_dispatched':
      return 'Applying changes to the workspace…';
    case 'verification_failed':
      return 'Verification failed — retrying with a stronger approach…';
    case 'verification_limited':
      return 'Finished with some checks reported as limitations (never claimed verified).';
    case 'attempt_failed':
      return message;
    case 'provider_fallback':
      return 'Provider hiccup — fell back to another model and kept going.';
    case 'escalation':
      return 'Escalating to a stronger model with the failure evidence…';
    case 'budget_exceeded':
      return 'Budget ceiling reached — stopping before overspending.';
    case 'execution_completed':
      return 'Execution completed — assembling the evidence pack.';
    case 'execution_failed':
      return 'Execution failed — review the evidence pack and diff.';
    case 'warning':
      return message;
    default:
      return null;
  }
}