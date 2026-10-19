import { TaskSession } from '../types';

/**
 * Builds a single-file JSON transcript for a session — everything the
 * sidecar (VS Code extension) or a human reviewer needs to replay what
 * happened: messages, narrated tool activities, stages, verification,
 * routing and the final diff.
 */
export function buildTranscript(session: TaskSession) {
  return {
    format: 'zyntry-transcript',
    version: 1,
    exported_at: new Date().toISOString(),
    session: {
      id: session.id,
      title: session.title,
      created_at: session.createdAt,
      branch: session.branch,
      mode: session.mode,
      state: session.state,
      backend_task_id: session.backendTaskId ?? null,
      backend_execution_id: session.backendExecutionId ?? null,
      backend_workspace_id: session.backendWorkspaceId ?? null,
    },
    messages: session.messages.map((m) => ({
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
      attached_files: m.attachedFiles ?? [],
    })),
    execution: {
      stages: (session.executionStages ?? []).map((s) => ({
        name: s.name,
        status: s.status,
        model: s.modelAssigned ?? null,
      })),
      plan: session.planSteps.map((s) => ({ label: s.label, status: s.status })),
      activity: session.toolActivities.map((a) => ({
        time: a.timestamp,
        action: a.action,
        message: a.name,
        status: a.status,
      })),
      verification: session.verificationChecks.map((c) => ({
        check: c.name,
        status: c.status,
        summary: c.summary ?? null,
      })),
      routing: session.routing,
    },
    changes: session.diffFiles.map((f) => ({
      path: f.path,
      status: f.status,
      added: f.addedCount,
      removed: f.removedCount,
    })),
    evidence_pack: session.evidencePack ?? null,
  };
}

export function downloadTranscript(session: TaskSession) {
  const payload = JSON.stringify(buildTranscript(session), null, 2);
  const blob = new Blob([payload], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const safeTitle =
    session.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48) || 'session';
  a.download = `zyntry-transcript-${safeTitle}-${session.id.slice(0, 8)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}