import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  AgentState,
  WorkspaceMode,
  RoutingMode,
  ExecutionMode,
  TaskSession,
  ChatMessage,
  ToolActivityItem,
  RoutingInfo,
} from '../types';
import {
  api,
  isBackendConfigured,
  mapPlanSteps,
  mapExecutionStages,
  mapVerificationChecks,
  mapRouting,
  mapDiffFiles,
  mapEvidencePack,
  mapToolActivities,
  buildAssistantSummaryMessage,
  executionAgentState,
} from '../api/client';
import { WORKSPACE_FILES } from '../data/mockData';
import { narrateEvent } from '../api/narration';
import { Sidebar, SidebarTab } from './Sidebar';
import { TopBar } from './TopBar';
import { ConversationView } from './ConversationView';
import { Composer } from './Composer';
import { EmptyState } from './EmptyState';
import { DiffReview } from './DiffReview';
import { VerificationPanel } from './VerificationPanel';
import { InlineApproval, ApprovalVariant } from './InlineApproval';
import { StatusBadge } from './StatusBadge';
import { SettingsView } from './SettingsView';
import { ConstitutionView } from './ConstitutionView';
import { WorkspaceSetupLoader } from './WorkspaceSetupLoader';
import { BackendBadge } from './BackendBadge';
import { RepoIngestButton } from './RepoIngestButton';
import { WorkspaceDialog } from './WorkspaceDialog';
import { DeliverPanel } from './DeliverPanel';
import { BackendWorkspace } from '../api/client';
import { downloadTranscript } from '../api/transcript';
import { CheckCircle2, RotateCcw, FileDown } from 'lucide-react';

const INITIAL_ROUTING: RoutingInfo = {
  provider: '',
  model: 'auto',
  routingMode: 'auto',
  estimatedCost: 0,
  actualCost: 0,
  latencyMs: 0,
  reason: '',
  retryCount: 0,
  fallbackStatus: 'nominal',
  taskBudget: 1.0,
};

function createBlankSession(): TaskSession {
  const id = `task-${Date.now()}`;
  return {
    id,
    title: 'New Engineering Task',
    createdAt: new Date().toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }),
    mode: 'agent',
    state: 'idle',
    branch: 'main',
    executionMode: 'auto',
    taskBudget: 1.0,
    backendTaskId: undefined,
    backendExecutionId: undefined,
    messages: [],
    diffFiles: [],
    verificationChecks: [],
    routing: { ...INITIAL_ROUTING },
    planSteps: [],
    toolActivities: [],
    executionStages: [],
  };
}

export const AppShell: React.FC = () => {
  // Workspace state
  const [sessions, setSessions] = useState<TaskSession[]>(() => [createBlankSession()]);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => sessions[0]?.id ?? '');
  const [currentTab, setCurrentTab] = useState<SidebarTab>('chat');
  const [mode, setMode] = useState<WorkspaceMode>('agent');
  const [routingMode, setRoutingMode] = useState<RoutingMode>('auto');
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('auto');
  const [taskBudget, setTaskBudget] = useState<number>(() => {
    const stored = Number(localStorage.getItem('zyntry.taskBudget'));
    return Number.isFinite(stored) && stored > 0 ? stored : 1.0;
  });
  const [runtime, setRuntime] = useState<string>('Node v22.14 LTS');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [showApprovalDialog, setShowApprovalDialog] = useState<boolean>(false);
  const [isChangesApplied, setIsChangesApplied] = useState<boolean>(false);
  const [isSubmittingApproval, setIsSubmittingApproval] = useState<boolean>(false);
  const [composerSeedText, setComposerSeedText] = useState<string>('');
  const [isSettingUpWorkspace, setIsSettingUpWorkspace] = useState<boolean>(false);
  const [pendingApprovalTask, setPendingApprovalTask] = useState<string | null>(null);
  const [liveToolActivities, setLiveToolActivities] = useState<ToolActivityItem[]>([]);
  const [workspaceDialogOpen, setWorkspaceDialogOpen] = useState(false);
  const [deliverOpen, setDeliverOpen] = useState(false);

  // Active session helper
  const currentSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];

  // Set mode when active session changes
  useEffect(() => {
    if (currentSession) {
      setMode(currentSession.mode);
      setIsChangesApplied(currentSession.state === 'complete');
      if (currentSession.executionMode) setExecutionMode(currentSession.executionMode);
      if (currentSession.taskBudget) setTaskBudget(currentSession.taskBudget);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  // Update session state helper
  const updateCurrentSession = (updater: Partial<TaskSession>) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSessionId ? { ...s, ...updater } : s))
    );
  };

  // Human-in-the-loop: approve a high-risk task, or authorize applied changes.
  const handleConfirmApproval = () => {
    // High-risk task approval path (real backend mode).
    if (pendingApprovalTask) {
      const taskId = pendingApprovalTask;
      setPendingApprovalTask(null);
      setIsSubmittingApproval(true);
      setShowApprovalDialog(false);
      updateCurrentSession({ state: 'working' });
      api
        .approveTask(taskId, false)
        .then(async () => {
          await runExecution(taskId, currentSession.messages);
          setIsSubmittingApproval(false);
        })
        .catch((err) => {
          setIsSubmittingApproval(false);
          updateCurrentSession({
            state: 'failed',
            messages: [
              ...currentSession.messages,
              {
                id: `m-err-${Date.now()}`,
                role: 'assistant',
                content: `Approval failed: ${err instanceof Error ? err.message : String(err)}`,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              },
            ],
          });
        });
      return;
    }

    // Post-execution change authorization: the workspace changes were already
    // applied by the runner; this marks them as reviewed and approved.
    setIsSubmittingApproval(true);
    setShowApprovalDialog(false);
    updateCurrentSession({ state: 'applying_changes' });
    setTimeout(() => {
      setIsSubmittingApproval(false);
      setIsChangesApplied(true);
      updateCurrentSession({
        state: 'complete',
        messages: [
          ...currentSession.messages,
          {
            id: `m-applied-${Date.now()}`,
            role: 'assistant',
            content: '✓ Changes authorized. Workspace state recorded for the execution.',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ],
      });
    }, 600);
  };

  // Reject from the inline approval prompt.
  const handleRejectApproval = () => {
    // Pre-execution high-risk rejection: cancel the task on the backend.
    if (pendingApprovalTask) {
      const taskId = pendingApprovalTask;
      setPendingApprovalTask(null);
      setIsSubmittingApproval(true);
      setShowApprovalDialog(false);
      api
        .rejectTask(taskId)
        .then(() => {
          setIsSubmittingApproval(false);
          updateCurrentSession({
            state: 'idle',
            planSteps: [],
            messages: [
              ...currentSession.messages,
              {
                id: `m-cancelled-${Date.now()}`,
                role: 'assistant',
                content:
                  'Task cancelled by developer before execution. Start a new task to continue.',
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              },
            ],
          });
        })
        .catch((err) => {
          setIsSubmittingApproval(false);
          updateCurrentSession({
            state: 'failed',
            messages: [
              ...currentSession.messages,
              {
                id: `m-err-${Date.now()}`,
                role: 'assistant',
                content: `Cancellation failed: ${err instanceof Error ? err.message : String(err)}`,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              },
            ],
          });
        });
      return;
    }

    // Post-execution change rejection: discard the proposed diff.
    setShowApprovalDialog(false);
    handleRejectChanges();
  };

  // Reject proposed changes
  const handleRejectChanges = () => {
    const updatedMessages: ChatMessage[] = [
      ...currentSession.messages,
      {
        id: `m-reject-${Date.now()}`,
        role: 'user',
        content: 'Changes rejected by developer. Please revise the approach.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
      {
        id: `m-reject-ack-${Date.now()}`,
        role: 'assistant',
        content: 'Proposed changes discarded from review. The execution record remains in history.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ];

    updateCurrentSession({
      state: 'idle',
      diffFiles: [],
      messages: updatedMessages,
    });
  };

  // Re-run the task against the backend.
  const handleRetryVerification = () => {
    const taskId = currentSession.backendTaskId;
    if (!taskId) {
      updateCurrentSession({
        messages: [
          ...currentSession.messages,
          {
            id: `m-err-${Date.now()}`,
            role: 'assistant',
            content: 'No backend task attached to this session — start a new task first.',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ],
      });
      return;
    }
    updateCurrentSession({ state: 'working' });
    runExecution(taskId, currentSession.messages);
  };

  // Escalation is automatic in the backend; re-running surfaces the result.
  const handleEscalateModel = () => {
    const taskId = currentSession.backendTaskId;
    if (!taskId) {
      updateCurrentSession({
        messages: [
          ...currentSession.messages,
          {
            id: `m-err-${Date.now()}`,
            role: 'assistant',
            content: 'No backend task attached — escalation happens automatically during backend execution.',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ],
      });
      return;
    }
    updateCurrentSession({ state: 'working' });
    runExecution(taskId, currentSession.messages);
  };

  // Send message from composer — real backend pipeline only.
  const handleSendMessage = async (text: string, attachedFiles: string[]) => {
    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      attachedFiles,
    };

    const newMessages = [...currentSession.messages, userMsg];
    const isFirstMessage = currentSession.messages.length === 0;
    updateCurrentSession({
      state: 'planning',
      messages: newMessages,
      ...(isFirstMessage
        ? { title: text.length > 72 ? `${text.slice(0, 72).trimEnd()}…` : text }
        : {}),
    });
    setIsChangesApplied(false);

    if (!isBackendConfigured()) {
      updateCurrentSession({
        state: 'idle',
        messages: [
          ...newMessages,
          {
            id: `m-connect-${Date.now()}`,
            role: 'assistant',
            content:
              'Connect the Zyntry backend first — click the "Not connected" badge (bottom-right) and enter the backend URL (e.g. http://localhost:8787).',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ],
      });
      return;
    }

    try {
      const created = await api.createTask(text, {
        budget_usd: taskBudget,
        max_attempts_per_stage: 2,
      });
      updateCurrentSession({
        backendTaskId: created.task.id,
        planSteps: mapPlanSteps(created.plan.stages),
        state: created.requires_approval ? 'awaiting_approval' : 'working',
      });
      if (created.requires_approval) {
        setPendingApprovalTask(created.task.id);
        setShowApprovalDialog(true);
        return;
      }
      await runExecution(created.task.id, newMessages);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      updateCurrentSession({
        state: 'failed',
        messages: [
          ...newMessages,
          {
            id: `m-err-${Date.now()}`,
            role: 'assistant',
            content: `Backend error: ${detail}`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ],
      });
    }
  };

  // Real execution: stream stage events, then materialize the full summary.
  const runExecution = async (taskId: string, baseMessages: ChatMessage[]) => {
    updateCurrentSession({ state: 'working' });
    const live: ToolActivityItem[] = [];
    const summary = await api.streamTask(taskId, (event) => {
      const type = String(event.type ?? '');
      const narration = narrateEvent({
        type,
        message: event.message as string | undefined,
        data: event.data as Record<string, unknown>,
      });
      const label =
        narration ??
        (type === 'stage_succeeded'
          ? String(event.message ?? 'stage completed')
          : type === 'verification_failed'
          ? 'verification failed'
          : type === 'agent_tool_call'
          ? `tool: ${String((event.data as Record<string, unknown>)?.tool ?? '')}`
          : String(event.message ?? type));
      // Prefer the backend event timestamp so the log reflects real time.
      let stamp: string;
      try {
        const iso = String(event.created_at ?? '');
        stamp = iso
          ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch {
        stamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
      live.unshift({
        id: `t-live-${live.length}-${Date.now()}`,
        name: label,
        action: type,
        target: typeof event.stage_id === 'string' ? event.stage_id : undefined,
        status:
          type === 'verification_failed' || type === 'attempt_failed' ? 'failed' : 'complete',
        timestamp: stamp,
      });
      setLiveToolActivities([...live.slice(0, 20)]);
      if (type === 'verification_failed' || type === 'verification_limited') {
        updateCurrentSession({ state: 'verifying' });
      }
    });

    const changes = await api.getChanges(summary.execution.id).catch(() => ({ changes: [] }));
    const endState = executionAgentState(summary);
    const diffFiles = mapDiffFiles(changes.changes);
    const summaryMessage: ChatMessage = {
      ...buildAssistantSummaryMessage(summary),
      diffFiles,
      blastRadius: currentSession.blastRadius,
    };
    updateCurrentSession({
      state: endState,
      backendExecutionId: summary.execution.id,
      executionStages: mapExecutionStages(summary.stages),
      planSteps: mapPlanSteps(summary.stages),
      verificationChecks: mapVerificationChecks(summary),
      routing: mapRouting(summary),
      diffFiles,
      evidencePack: mapEvidencePack(summary),
      toolActivities: [...live, ...mapToolActivities(summary)].slice(0, 30),
      messages: [...baseMessages, summaryMessage],
    });
    setLiveToolActivities([]);
  };

  // Stop running agent
  const handleStopAgent = () => {
    updateCurrentSession({ state: 'idle' });
  };

  // Create new task
  const handleNewTask = () => {
    const newTask = createBlankSession();
    setSessions([newTask, ...sessions]);
    setActiveSessionId(newTask.id);
    setCurrentTab('chat');
    setIsChangesApplied(false);
  };

  const isAgentRunning = ['planning', 'working', 'verifying', 'applying_changes'].includes(
    currentSession.state
  );

  // Standalone Workspace Setup Loading screen
  if (isSettingUpWorkspace) {
    return (
      <WorkspaceSetupLoader
        onFinished={() => {
          setIsSettingUpWorkspace(false);
          setCurrentTab('chat');
        }}
        repoName="zyntry-core-engine"
        branch={currentSession.branch}
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.45, ease: 'easeOut' }}
      className="flex h-screen w-screen overflow-hidden bg-[#0D1217] text-[#F2F6F4]"
    >
      {/* Mobile Drawer Overlay */}
      {isMobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm md:hidden"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      {/* 1. Left Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 transition-transform duration-250 ease-in-out md:static md:translate-x-0 ${
          isMobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={setActiveSessionId}
          onNewTask={handleNewTask}
          repoName="zyntry-core-engine"
          branch={currentSession.branch}
          activeFiles={WORKSPACE_FILES}
          runtime={runtime}
          onCloseMobileDrawer={() => setIsMobileSidebarOpen(false)}
        />
      </div>

      {/* 2. Main Workspace Center Column */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-transparent">
        {/* TopBar */}
        <TopBar
          repoName="zyntry-core-engine"
          branch={currentSession.branch}
          runtime={runtime}
          onRuntimeChange={setRuntime}
          routingMode={routingMode}
          onRoutingModeChange={(rm) => {
            setRoutingMode(rm);
            updateCurrentSession({
              routing: { ...currentSession.routing, routingMode: rm },
            });
          }}
          routingInfo={currentSession.routing}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
        />

        {/* Tab Views - Single Unified Scroll Container without separate scroll traps */}
        <main className="flex-1 flex flex-col min-h-0 overflow-hidden relative bg-transparent">
          {/* Main scrollable view for all content */}
          <div className="flex-1 overflow-y-auto min-h-0 scroll-smooth">
            {/* 1. CHAT TAB */}
            {currentTab === 'chat' &&
              (currentSession.messages.length === 0 ? (
                <EmptyState
                  repoName="zyntry-core-engine"
                  branch={currentSession.branch}
                />
              ) : (
                <ConversationView
                  messages={currentSession.messages}
                  agentState={currentSession.state}
                  liveActivities={liveToolActivities}
                  isAgentRunning={isAgentRunning}
                  onApplyChanges={() => setShowApprovalDialog(true)}
                  onRejectChanges={handleRejectChanges}
                  onRetryVerification={handleRetryVerification}
                  onEscalateModel={handleEscalateModel}
                  onSeedComposer={(text) => setComposerSeedText(text)}
                  onNavigateTab={(tab) => setCurrentTab(tab)}
                  isChangesApplied={isChangesApplied}
                />
              ))}

            {/* 2. CHANGES TAB */}
            {currentTab === 'changes' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="px-6 sm:px-10 md:px-16 lg:px-20 xl:px-24 py-6 sm:py-8 space-y-6 w-full pb-16"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base sm:text-lg font-bold text-[#F2F6F4] tracking-tight">
                      Workspace Changes
                    </h2>
                    <p className="text-xs text-[#A3AEAA] mt-0.5">
                      Unified diff review comparing working tree against HEAD
                    </p>
                  </div>
                  {currentSession.state === 'awaiting_approval' && (
                    <motion.button
                      type="button"
                      whileHover={{ scale: 1.04 }}
                      whileTap={{ scale: 0.96 }}
                      onClick={() => {
                        setCurrentTab('chat');
                        setShowApprovalDialog(true);
                      }}
                      className="flex items-center gap-2 px-4 py-2 bg-white text-zinc-900 hover:bg-zinc-200 border border-white/30 rounded-full text-xs font-semibold cursor-pointer shadow-md active:scale-95 transition-all"
                    >
                      <CheckCircle2 size={14} />
                      <span>Authorize Changes</span>
                    </motion.button>
                  )}
                </div>

                <DiffReview
                  files={currentSession.diffFiles}
                  onApplyChanges={() => {
                    setCurrentTab('chat');
                    setShowApprovalDialog(true);
                  }}
                  onRejectChanges={handleRejectChanges}
                  isApplied={isChangesApplied}
                />
              </motion.div>
            )}

            {/* 4. VERIFICATION TAB */}
            {currentTab === 'verification' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="px-6 sm:px-10 md:px-16 lg:px-20 xl:px-24 py-6 sm:py-8 space-y-6 w-full pb-16"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base sm:text-lg font-bold text-[#F2F6F4] tracking-tight">
                      Quality & Safety Matrix
                    </h2>
                    <p className="text-xs text-[#A3AEAA] mt-0.5">
                      Verification results from the execution — passed, failed, or
                      reported as limitations (never claimed verified).
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <motion.button
                      type="button"
                      whileHover={{ scale: 1.04 }}
                      whileTap={{ scale: 0.96 }}
                      onClick={handleRetryVerification}
                      className="flex items-center gap-2 px-4 py-2 bg-white/6 hover:bg-white/10 text-[#F2F6F4] border border-white/10 rounded-full text-xs font-medium cursor-pointer shadow-xs"
                    >
                      <RotateCcw size={13} className="text-[#82B9FF]" />
                      <span>Re-run Task</span>
                    </motion.button>
                  </div>
                </div>

                <VerificationPanel
                  checks={currentSession.verificationChecks}
                  onRetry={handleRetryVerification}
                  onEscalate={handleEscalateModel}
                  defaultExpanded={true}
                />
              </motion.div>
            )}

            {/* 5. CONSTITUTION TAB */}
            {currentTab === 'constitution' && <ConstitutionView />}

            {/* 6. HISTORY TAB */}
            {currentTab === 'history' && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="px-6 sm:px-10 md:px-16 lg:px-20 xl:px-24 py-6 sm:py-8 space-y-6 w-full pb-16"
              >
                <div>
                  <h2 className="text-base sm:text-lg font-bold text-[#F2F6F4] tracking-tight">
                    Task History & Evidence
                  </h2>
                  <p className="text-xs text-[#A3AEAA] mt-0.5">
                    Audit log of previous reasoning sessions, patches, and model allocations
                  </p>
                </div>

                <div className="space-y-3.5">
                  {sessions.map((sess) => (
                    <motion.div
                      key={sess.id}
                      whileHover={{ y: -2 }}
                      onClick={() => {
                        setActiveSessionId(sess.id);
                        setCurrentTab('chat');
                      }}
                      className="p-5 bg-[#121820]/95 hover:bg-[#151D28] border border-white/10 hover:border-white/20 rounded-[22px] transition-all cursor-pointer space-y-3 shadow-xl backdrop-blur-xl"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs sm:text-sm text-[#F2F6F4]">
                          {sess.title}
                        </span>
                        <StatusBadge state={sess.state} />
                      </div>

                      <div className="flex items-center gap-4 text-[11px] font-mono text-[#6F7B77] tabular-nums">
                        <span>Created {sess.createdAt}</span>
                        <span>·</span>
                        <span>Branch: {sess.branch}</span>
                        <span>·</span>
                        <span className="text-[#93C5FD] font-semibold">
                          ${sess.routing.actualCost.toFixed(4)}
                        </span>
                        {sess.backendTaskId && (
                          <>
                            <span>·</span>
                            <span className="font-mono text-[#6F7B77]">
                              task: {sess.backendTaskId.slice(0, 8)}
                            </span>
                          </>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* 7. SETTINGS TAB */}
            {currentTab === 'settings' && (
              <SettingsView
                repoName="zyntry-core-engine"
                branch={currentSession.branch}
                onBranchChange={(newBranch) => {
                  updateCurrentSession({ branch: newBranch });
                }}
                taskBudget={taskBudget}
                onTaskBudgetChange={(tb) => {
                  setTaskBudget(tb);
                  updateCurrentSession({ taskBudget: tb });
                }}
                onSave={() => {
                  localStorage.setItem('zyntry.taskBudget', String(taskBudget));
                  localStorage.setItem('zyntry.branch', currentSession.branch);
                }}
              />
            )}
          </div>

          {/* Floating Solitary Rounded Input */}
          {currentTab === 'chat' && (
            <>
              {/* Toolbar: repo ingest, workspace, deliver, transcript (with a backend task or any chat) */}
              {(currentSession.backendTaskId || currentSession.messages.length > 0) && (
                <div className="flex items-center gap-2 px-4 sm:px-6 pb-2">
                  {currentSession.backendTaskId && <RepoIngestButton taskId={currentSession.backendTaskId} compact />}
                  <button
                    onClick={() => setWorkspaceDialogOpen(true)}
                    title="Create an execution workspace (runner target) for this task"
                    className="px-3 py-1.5 rounded-full bg-[#121820]/95 hover:bg-[#151D28] border border-white/10 hover:border-[#82B9FF]/40 text-[#F2F6F4] text-xs font-medium cursor-pointer shadow-lg backdrop-blur-xl"
                  >
                    {currentSession.backendWorkspaceId ? 'Workspace ✓' : 'Workspace'}
                  </button>
                  <button
                    onClick={() => setDeliverOpen(true)}
                    disabled={!currentSession.backendWorkspaceId}
                    title={
                      currentSession.backendWorkspaceId
                        ? 'Commit → push → PR (approval-gated)'
                        : 'Create a workspace first'
                    }
                    className="px-3 py-1.5 rounded-full bg-[#121820]/95 hover:bg-[#151D28] border border-white/10 hover:border-[#55E6A5]/40 text-[#F2F6F4] text-xs font-medium cursor-pointer disabled:opacity-40 shadow-lg backdrop-blur-xl"
                  >
                    Deliver
                  </button>
                  <button
                    onClick={() => downloadTranscript(currentSession)}
                    disabled={currentSession.messages.length === 0}
                    title="Export the full session transcript to a single JSON file"
                    className="px-3 py-1.5 rounded-full bg-[#121820]/95 hover:bg-[#151D28] border border-white/10 hover:border-[#93C5FD]/40 text-[#F2F6F4] text-xs font-medium cursor-pointer disabled:opacity-40 shadow-lg backdrop-blur-xl"
                  >
                    Transcript
                  </button>
                </div>
              )}
              {showApprovalDialog ? (
                <InlineApproval
                  isOpen={showApprovalDialog}
                  variant={
                    (pendingApprovalTask ? 'pre-execution' : 'apply-changes') as ApprovalVariant
                  }
                  files={currentSession.diffFiles}
                  planSteps={currentSession.planSteps}
                  isSubmitting={isSubmittingApproval}
                  onApprove={handleConfirmApproval}
                  onReject={handleRejectApproval}
                  onDismiss={() => {
                    if (isSubmittingApproval) return;
                    handleRejectApproval();
                  }}
                />
              ) : (
                <Composer
                  onSendMessage={handleSendMessage}
                  onStopAgent={handleStopAgent}
                  isRunning={isAgentRunning}
                  mode={mode}
                  onModeChange={(newMode) => {
                    setMode(newMode);
                    updateCurrentSession({ mode: newMode });
                  }}
                  initialText={composerSeedText}
                />
              )}
            </>
          )}
        </main>
      </div>

      {/* 3. Approval is handled inline at the input side (Codex-style) */}
      <WorkspaceDialog
        isOpen={workspaceDialogOpen}
        taskId={currentSession.backendTaskId}
        onClose={() => setWorkspaceDialogOpen(false)}
        onCreated={(ws: BackendWorkspace) => {
          updateCurrentSession({ backendWorkspaceId: ws.id });
        }}
      />
      <DeliverPanel
        isOpen={deliverOpen}
        workspaceId={currentSession.backendWorkspaceId}
        title={currentSession.title}
        onClose={() => setDeliverOpen(false)}
      />
      <BackendBadge />
    </motion.div>
  );
};