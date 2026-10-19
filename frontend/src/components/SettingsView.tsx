import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  FolderGit2, 
  PlayCircle, 
  ShieldCheck, 
  GitFork, 
  Lock, 
  Wrench, 
  Bell, 
  Palette, 
  UserCheck, 
  Search, 
  Check, 
  ExternalLink, 
  RefreshCw, 
  Download, 
  Trash2, 
  LogOut, 
  Sliders, 
  ChevronRight, 
  Info,
  CheckCircle2,
  AlertCircle,
  Terminal,
  Server,
  Box,
  Cpu,
  Layers,
  Shield,
  GitBranch,
  FileCode
} from 'lucide-react';
import { CustomSelect, SelectOption } from './CustomSelect';
import { api, getBackendConfig } from '../api/client';

export type SettingsSectionId = 
  | 'workspace'
  | 'execution'
  | 'verification'
  | 'routing'
  | 'context_privacy'
  | 'tools_integrations'
  | 'notifications'
  | 'appearance'
  | 'account_diagnostics';

interface SettingsViewProps {
  repoName?: string;
  branch?: string;
  onBranchChange?: (branch: string) => void;
  taskBudget?: number;
  onTaskBudgetChange?: (budget: number) => void;
  onSave?: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  repoName = 'zyntry-core-engine',
  branch = 'main',
  onBranchChange,
  taskBudget = 1.0,
  onTaskBudgetChange,
  onSave,
}) => {
  const [activeSection, setActiveSection] = useState<SettingsSectionId>('workspace');
  const [searchQuery, setSearchQuery] = useState('');
  const [saveToast, setSaveToast] = useState<string | null>(null);

  // 1. Workspace State
  const [currentRepo] = useState(repoName);
  const [defaultBranch, setDefaultBranch] = useState(branch);
  const [defaultRuntime, setDefaultRuntime] = useState('local-daemon-v2.4.1');
  const [projectEnv, setProjectEnv] = useState('Core Production / Staging');
  const [includedFolders, setIncludedFolders] = useState(['src/**', 'tests/**', 'packages/**', 'config/**']);
  const [excludedFolders, setExcludedFolders] = useState(['node_modules/**', '.git/**', 'dist/**', 'build/**']);
  const [isReindexing, setIsReindexing] = useState(false);

  // Backend connection (live — read from the same config the API client uses)
  const [backendUrl] = useState(getBackendConfig().backendUrl);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'unreachable'>('checking');
  const [backendDetail, setBackendDetail] = useState<string>('');
  const checkBackend = async () => {
    setBackendStatus('checking');
    try {
      const h = await api.health();
      setBackendStatus('connected');
      setBackendDetail(
        `ok · providers: ${(h.providers?.configured ?? []).join(', ') || 'none'}`
      );
    } catch (err) {
      setBackendStatus('unreachable');
      setBackendDetail(err instanceof Error ? err.message : String(err));
    }
  };

  // 2. Execution State
  const [requireApprovalForFiles, setRequireApprovalForFiles] = useState(true);
  const [requireApprovalForCommands, setRequireApprovalForCommands] = useState(true);
  const [allowedWriteOps, setAllowedWriteOps] = useState({
    create: true,
    modify: true,
    delete: false,
    runBuild: true,
  });
  const [commandTimeoutSec, setCommandTimeoutSec] = useState(60);
  const [maxFilesPerRun, setMaxFilesPerRun] = useState(15);
  const [maxExecutionSteps, setMaxExecutionSteps] = useState(30);

  // 3. Verification State
  const [enableTypeScript, setEnableTypeScript] = useState(true);
  const [enableLinting, setEnableLinting] = useState(true);
  const [enableTests, setEnableTests] = useState(true);
  const [enableBuildVerification, setEnableBuildVerification] = useState(true);
  const [enableSecurityChecks, setEnableSecurityChecks] = useState(true);
  const [retryFailedVerification, setRetryFailedVerification] = useState(true);
  const [escalateOnFailure, setEscalateOnFailure] = useState(true);

  // 4. Routing State
  const [selectedRoutingPreset, setSelectedRoutingPreset] = useState<'auto' | 'fastest' | 'cheapest' | 'balanced' | 'highest_quality'>('balanced');
  const [fallbackBehavior, setFallbackBehavior] = useState('fallback_next_tier');
  const [allowedModels, setAllowedModels] = useState({
    claudeSonnet: true,
    gpt45: true,
    geminiPro: true,
    deepseekR1: true,
  });

  // 5. Context and Privacy State
  const [filesIncludedDefault, setFilesIncludedDefault] = useState(['src/**/*', 'tests/**/*', 'package.json', 'tsconfig.json']);
  const [filesExcludedDefault, setFilesExcludedDefault] = useState(['*.pem', '*.key', 'credentials.json', '*.log', '.env*']);
  const [ignoreSecretsAndEnv, setIgnoreSecretsAndEnv] = useState(true);
  const [maxContextSize, setMaxContextSize] = useState('128k');
  const [storeRunHistory, setStoreRunHistory] = useState(true);
  const [storeDiffs, setStoreDiffs] = useState(true);
  const [redactSensitiveValues, setRedactSensitiveValues] = useState(true);

  // 6. Tools and Integrations State
  const [gitAccess, setGitAccess] = useState<'read_write' | 'read_only' | 'disabled'>('read_write');
  const [terminalAccess, setTerminalAccess] = useState<'interactive_confirm' | 'read_only' | 'disabled'>('interactive_confirm');
  const [mcpFilesystem, setMcpFilesystem] = useState(true);
  const [mcpPostgres, setMcpPostgres] = useState(true);
  const [mcpGithub, setMcpGithub] = useState(true);
  const [permissionsMode, setPermissionsMode] = useState<'write' | 'read_only'>('write');
  const [confirmationReq, setConfirmationReq] = useState('prompt_destructive');

  // 7. Notifications State
  const [notifyTaskCompleted, setNotifyTaskCompleted] = useState(true);
  const [notifyVerificationFailed, setNotifyVerificationFailed] = useState(true);
  const [notifyApprovalRequired, setNotifyApprovalRequired] = useState(true);
  const [notifyRuntimeBlocked, setNotifyRuntimeBlocked] = useState(true);
  const [notifyProviderFallback, setNotifyProviderFallback] = useState(true);
  const [notifyBudgetWarning, setNotifyBudgetWarning] = useState(true);

  // 8. Appearance State
  const [themeMode, setThemeMode] = useState<'dark_slate' | 'midnight' | 'oled' | 'light'>('dark_slate');
  const [density, setDensity] = useState<'comfortable' | 'compact'>('comfortable');
  const [showRoutingDetails, setShowRoutingDetails] = useState(true);
  const [showCostAndLatency, setShowCostAndLatency] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [highContrastBorders, setHighContrastBorders] = useState(false);

  // 9. Account & Diagnostics
  const [currentUser] = useState('apatirasulayman@gmail.com');
  const [connectedRuntime] = useState('local-daemon @ 127.0.0.1:4820');
  const [runtimeStatus] = useState('nominal');

  // Custom Dropdown Option Configs
  const RUNTIME_OPTIONS: SelectOption[] = [
    {
      value: 'local-daemon-v2.4.1',
      label: 'Local Daemon (v2.4.1 - Recommended)',
      desc: 'Local isolated development engine for private codebases',
      badge: 'Local',
      icon: <Server size={14} />
    },
    {
      value: 'cloud-sandbox-secure',
      label: 'Cloud Isolated Sandbox',
      desc: 'Ephemeral micro-VM with hardware security isolation',
      badge: 'Cloud',
      icon: <Cpu size={14} />
    },
    {
      value: 'docker-container-node20',
      label: 'Docker DevContainer',
      desc: 'Containerized environment with Node.js 20 & Rust toolchain',
      badge: 'Docker',
      icon: <Box size={14} />
    }
  ];

  const FALLBACK_OPTIONS: SelectOption[] = [
    {
      value: 'fallback_next_tier',
      label: 'Gracefully fallback to alternative provider',
      desc: 'Maintains uninterrupted workflow across redundant model providers',
      badge: 'Auto',
      icon: <GitFork size={14} />
    },
    {
      value: 'pause_prompt',
      label: 'Pause execution and prompt human operator',
      desc: 'Interactive confirmation before switching to secondary providers',
      badge: 'Confirm',
      icon: <AlertCircle size={14} />
    },
    {
      value: 'strict_fail',
      label: 'Strict fail (do not route to alternate models)',
      desc: 'Halts task immediately if primary model encounters outage',
      badge: 'Strict',
      icon: <Shield size={14} />
    }
  ];

  const CONTEXT_OPTIONS: SelectOption[] = [
    {
      value: '64k',
      label: '64,000 Tokens (Lightweight context)',
      desc: 'Fast single-file edits and rapid turnaround',
      badge: '64k',
      icon: <FileCode size={14} />
    },
    {
      value: '128k',
      label: '128,000 Tokens (Standard multi-file)',
      desc: 'Standard multi-file index for full-repo reasoning',
      badge: '128k',
      icon: <Layers size={14} />
    },
    {
      value: '200k',
      label: '200,000 Tokens (Large codebase index)',
      desc: 'Expanded buffer for complex architecture refactoring',
      badge: '200k',
      icon: <Server size={14} />
    }
  ];

  const GIT_ACCESS_OPTIONS: SelectOption[] = [
    {
      value: 'read_write',
      label: 'Read & Write (Inspect, Stage, Diff)',
      desc: 'Allows inspecting status, staging files, and creating diffs',
      badge: 'Full',
      icon: <GitBranch size={14} />
    },
    {
      value: 'read_only',
      label: 'Read-only (Inspect & Log only)',
      desc: 'Inspect repository tree and commit log without write permissions',
      badge: 'Inspect',
      icon: <Lock size={14} />
    },
    {
      value: 'disabled',
      label: 'Disabled',
      desc: 'Completely decouple Git operations from agent execution',
      badge: 'Off',
      icon: <AlertCircle size={14} />
    }
  ];

  const TERMINAL_ACCESS_OPTIONS: SelectOption[] = [
    {
      value: 'interactive_confirm',
      label: 'Interactive (Prompt before execution)',
      desc: 'Prompt for human approval before spawning shell subprocesses',
      badge: 'Safe',
      icon: <Terminal size={14} />
    },
    {
      value: 'read_only',
      label: 'Read-only (Safe query commands only)',
      desc: 'Allow safe query commands (ls, git status) automatically',
      badge: 'Query',
      icon: <PlayCircle size={14} />
    },
    {
      value: 'disabled',
      label: 'Disabled (No shell access)',
      desc: 'Block all terminal execution and subshells',
      badge: 'Blocked',
      icon: <AlertCircle size={14} />
    }
  ];

  useEffect(() => {
    checkBackend();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const triggerToast = (msg: string) => {
    setSaveToast(msg);
    setTimeout(() => setSaveToast(null), 3200);
  };

  const handleReindex = () => {
    setIsReindexing(true);
    setTimeout(() => {
      setIsReindexing(false);
      triggerToast('Workspace AST index successfully synchronized (1,842 nodes)');
    }, 1500);
  };

  const handleClearCache = () => {
    triggerToast('Local AST diff cache & reasoning checkpoints purged');
  };

  const handleExportDiagnostics = () => {
    const diagnosticPayload = {
      timestamp: new Date().toISOString(),
      app: 'Zyntry Code | Engineering Agent',
      version: 'v2.4.1',
      runtime: connectedRuntime,
      repo: currentRepo,
      branch: defaultBranch,
      settingsSnapshot: {
        execution: { commandTimeoutSec, maxFilesPerRun, maxExecutionSteps },
        verification: { enableTypeScript, enableLinting, enableTests, enableBuildVerification },
        routing: { preset: selectedRoutingPreset, fallbackBehavior },
      }
    };
    const blob = new Blob([JSON.stringify(diagnosticPayload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zyntry-code-diagnostics-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    triggerToast('Diagnostic report downloaded successfully');
  };

  const SECTIONS: { id: SettingsSectionId; label: string; icon: React.ReactNode; desc: string }[] = [
    { id: 'workspace', label: 'Workspace', icon: <FolderGit2 size={16} />, desc: 'Repository, branch, indexing & environment' },
    { id: 'execution', label: 'Execution', icon: <PlayCircle size={16} />, desc: 'Human approvals, timeouts & write limits' },
    { id: 'verification', label: 'Verification', icon: <ShieldCheck size={16} />, desc: 'TypeScript, lint, tests & escalation' },
    { id: 'routing', label: 'Routing', icon: <GitFork size={16} />, desc: 'Model tier presets & fallback policy' },
    { id: 'context_privacy', label: 'Context & Privacy', icon: <Lock size={16} />, desc: 'Excluded files, secrets & token caps' },
    { id: 'tools_integrations', label: 'Tools & Integrations', icon: <Wrench size={16} />, desc: 'Git, terminal, MCP & tool permissions' },
    { id: 'notifications', label: 'Notifications', icon: <Bell size={16} />, desc: 'Task completion, failures & budget alerts' },
    { id: 'appearance', label: 'Appearance', icon: <Palette size={16} />, desc: 'Theme, density, shortcuts & telemetry metrics' },
    { id: 'account_diagnostics', label: 'Account & Diagnostics', icon: <UserCheck size={16} />, desc: 'Session credentials, cache & logs' },
  ];

  const filteredSections = searchQuery.trim() 
    ? SECTIONS.filter(s => s.label.toLowerCase().includes(searchQuery.toLowerCase()) || s.desc.toLowerCase().includes(searchQuery.toLowerCase()))
    : SECTIONS;

  return (
    <div className="w-full px-6 sm:px-10 md:px-16 lg:px-20 xl:px-24 py-6 sm:py-8 space-y-6 pb-24 text-[#F3F4F6]">
      
      {/* Toast Notification */}
      <AnimatePresence>
        {saveToast && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="fixed top-6 right-6 z-50 flex items-center gap-2.5 px-4 py-2.5 bg-[#141C25] border border-white/20 rounded-full shadow-2xl text-xs font-medium text-white backdrop-blur-xl"
          >
            <CheckCircle2 size={14} className="text-[#93C5FD]" />
            <span>{saveToast}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Page Header with Bubbly Title & Global Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-white/6">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-white/10 border border-white/15 flex items-center justify-center text-[#93C5FD]">
              <Sliders size={16} />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">Settings</h1>
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-white/6 border border-white/10 text-[#93C5FD]">
              Zyntry Code v2.4.1
            </span>
          </div>
          <p className="text-xs text-[#9CA3AF] mt-1">
            Configure developer ergonomics, autonomous execution safety, verification pipelines, and local workspace policy.
          </p>
        </div>

        {/* Search Bar for Settings */}
        <div className="relative w-full md:w-72">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search settings..."
            className="w-full h-10 rounded-full bg-[#121820] hover:bg-[#141C25] focus:bg-[#151E28] border border-white/12 focus:border-white/30 text-xs text-[#F3F4F6] placeholder-[#9CA3AF] pl-9 pr-4 shadow-sm focus:outline-hidden transition-all"
          />
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
        </div>
      </div>

      {/* Global Save Bar */}
      <div className="flex items-center justify-between gap-3 p-4 rounded-[22px] bg-[#121820]/90 border border-[#55E6A5]/25 shadow-md backdrop-blur-md">
        <div className="flex items-center gap-2.5 text-xs text-[#9CA3AF]">
          <Info size={14} className="text-[#93C5FD] shrink-0" />
          <span>
            Budget &amp; branch apply to new tasks. Changes you make here are live,
            but press <span className="text-white font-medium">Save</span> to persist
            them across reloads.
          </span>
        </div>
        <motion.button
          type="button"
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => {
            onSave?.();
            triggerToast('Settings saved — budget & branch persisted');
          }}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-[#173D30] to-[#1F4E3E] hover:from-[#1F4E3E] hover:to-[#26624E] text-[#55E6A5] border border-[#2D9E70] rounded-full text-xs font-semibold transition-all cursor-pointer shadow-lg shrink-0"
        >
          <Check size={14} />
          <span>Save Settings</span>
        </motion.button>
      </div>

      {/* Console Authority Notice Banner */}
      <div className="p-4 rounded-[22px] bg-[#121820]/90 border border-white/10 flex items-start gap-3 shadow-md backdrop-blur-md">
        <Info size={16} className="text-[#93C5FD] shrink-0 mt-0.5" />
        <div className="text-xs leading-relaxed text-[#9CA3AF]">
          <span className="font-semibold text-white">Security & Governance Architecture: </span>
          Raw API keys, provider credentials, organizational IAM roles, and project billing are securely managed in the{' '}
          <span className="text-[#93C5FD] font-medium underline cursor-pointer hover:text-white">Rivet Console</span>. 
          Local settings control your IDE experience, while the connected runtime acts as the authoritative security sandbox.
        </div>
      </div>

      {/* Main Settings Layout: Bubbly Section Pills + Section Card Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Side Navigation Pills (Sticky on desktop) */}
        <div className="lg:col-span-4 lg:sticky lg:top-4 space-y-1.5 bg-[#10151C]/80 border border-white/8 rounded-[26px] p-2.5 shadow-xl backdrop-blur-xl">
          <div className="px-3 py-1.5 text-[10px] font-mono text-[#9CA3AF] uppercase tracking-wider">
            Configuration Sections
          </div>
          {filteredSections.map((sec) => {
            const isActive = activeSection === sec.id;
            return (
              <button
                key={sec.id}
                type="button"
                onClick={() => setActiveSection(sec.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-2xl text-left transition-all cursor-pointer group ${
                  isActive
                    ? 'bg-white/10 text-white font-medium border border-white/15 shadow-sm'
                    : 'text-[#9CA3AF] hover:text-[#F3F4F6] hover:bg-white/5 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`p-1.5 rounded-xl transition-transform group-hover:scale-105 ${
                    isActive ? 'text-[#93C5FD] bg-white/10' : 'text-[#6B7280]'
                  }`}>
                    {sec.icon}
                  </span>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold truncate">{sec.label}</div>
                    <div className="text-[10px] text-[#6B7280] truncate">{sec.desc}</div>
                  </div>
                </div>
                <ChevronRight size={13} className={`shrink-0 transition-transform ${isActive ? 'text-[#93C5FD] translate-x-0.5' : 'text-transparent'}`} />
              </button>
            );
          })}
        </div>

        {/* Right Side Settings Panels */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* ================= SECTION 1: WORKSPACE ================= */}
          {activeSection === 'workspace' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="flex items-center justify-between pb-3 border-b border-white/8">
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <FolderGit2 size={16} className="text-[#93C5FD]" />
                    <span>Workspace Settings</span>
                  </h2>
                  <p className="text-xs text-[#9CA3AF] mt-0.5">
                    Repository parameters, working tree references, and code indexing
                  </p>
                </div>
              </div>

              {/* Setting 1: Current Repo */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white block">Current Repository</label>
                <div className="flex items-center gap-3">
                  <input
                    type="text"
                    value={currentRepo}
                    disabled
                    className="flex-1 h-10 rounded-full bg-white/4 border border-white/10 px-4 text-xs font-mono text-[#F3F4F6] cursor-not-allowed opacity-80"
                  />
                  <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-full">
                    Active Clean
                  </span>
                </div>
              </div>

              {/* Setting 2: Backend Connection (live) */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white block">Zyntry Backend</label>
                <div className="p-4 rounded-2xl bg-[#0F141A] border border-white/8 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-xs font-mono text-[#F3F4F6] truncate">
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 ${
                          backendStatus === 'connected'
                            ? 'bg-emerald-400'
                            : backendStatus === 'checking'
                            ? 'bg-amber-400 animate-pulse'
                            : 'bg-rose-400'
                        }`}
                      />
                      <span className="truncate">{backendUrl}</span>
                    </div>
                    <div className="text-[11px] text-[#9CA3AF] mt-1 font-mono truncate">
                      {backendStatus === 'checking'
                        ? 'Checking connection…'
                        : backendDetail}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={checkBackend}
                    disabled={backendStatus === 'checking'}
                    className="flex items-center justify-center gap-2 px-4 py-2 rounded-full bg-white/8 hover:bg-white/12 border border-white/12 text-xs font-medium cursor-pointer transition-colors shrink-0 disabled:opacity-50"
                  >
                    <RefreshCw
                      size={13}
                      className={backendStatus === 'checking' ? 'animate-spin text-[#93C5FD]' : 'text-[#93C5FD]'}
                    />
                    <span>Test Connection</span>
                  </button>
                </div>
              </div>

              {/* Setting 3: Default Branch */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white block">Default Branch</label>
                <input
                  type="text"
                  value={defaultBranch}
                  onChange={(e) => {
                    setDefaultBranch(e.target.value);
                    onBranchChange?.(e.target.value);
                  }}
                  className="w-full h-10 rounded-full bg-[#0F141A] border border-white/12 focus:border-white/30 px-4 text-xs font-mono text-white focus:outline-hidden"
                />
              </div>

              {/* Setting 3: Default Execution Runtime */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white block">Default Execution Runtime</label>
                <CustomSelect
                  value={defaultRuntime}
                  onChange={(val) => setDefaultRuntime(val)}
                  options={RUNTIME_OPTIONS}
                />
              </div>

              {/* Setting 4: Project and Environment */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white block">Project & Environment</label>
                <input
                  type="text"
                  value={projectEnv}
                  onChange={(e) => setProjectEnv(e.target.value)}
                  className="w-full h-10 rounded-full bg-[#0F141A] border border-white/12 focus:border-white/30 px-4 text-xs text-white focus:outline-hidden"
                />
              </div>

              {/* Setting 5: Included & Excluded Folders */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-white block">Included Folders</label>
                  <div className="p-3 bg-[#0F141A] border border-white/10 rounded-2xl space-y-2 min-h-[90px]">
                    <div className="flex flex-wrap gap-1.5">
                      {includedFolders.map((f) => (
                        <span key={f} className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-white/6 border border-white/10 text-[#93C5FD]">
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-white block">Excluded Folders</label>
                  <div className="p-3 bg-[#0F141A] border border-white/10 rounded-2xl space-y-2 min-h-[90px]">
                    <div className="flex flex-wrap gap-1.5">
                      {excludedFolders.map((f) => (
                        <span key={f} className="text-[10px] font-mono px-2.5 py-1 rounded-full bg-white/6 border border-white/10 text-rose-300">
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Setting 6: Context Indexing Status */}
              <div className="p-4 rounded-2xl bg-[#0F141A] border border-white/8 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span>Context Indexing Status: 100% Synchronized</span>
                  </div>
                  <div className="text-[11px] text-[#9CA3AF] mt-0.5 font-mono">
                    1,842 AST files · 14,920 symbol references cached
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleReindex}
                  disabled={isReindexing}
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-full bg-white/8 hover:bg-white/12 border border-white/12 text-xs font-medium cursor-pointer transition-colors shrink-0 disabled:opacity-50"
                >
                  <RefreshCw size={13} className={isReindexing ? "animate-spin text-[#93C5FD]" : "text-[#93C5FD]"} />
                  <span>{isReindexing ? 'Indexing...' : 'Re-index Workspace'}</span>
                </button>
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 2: EXECUTION ================= */}
          {activeSection === 'execution' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <PlayCircle size={16} className="text-[#93C5FD]" />
                  <span>Execution & Autonomous Safety</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Govern file write authorizations, execution timeouts, and action step limits
                </p>
              </div>

              {/* Budget: wired to the session & sent to the backend on task creation */}
              <div className="space-y-2.5">
                <label className="text-xs font-semibold text-white block">Task Budget (USD)</label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    value={taskBudget}
                    onChange={(e) => onTaskBudgetChange?.(Number(e.target.value))}
                    className="w-32 h-10 rounded-full bg-[#0F141A] border border-white/12 focus:border-white/30 px-4 text-xs font-mono text-white focus:outline-hidden"
                  />
                  <div className="flex items-center gap-1.5">
                    {[0.1, 0.2, 0.5, 1.0, 5.0].map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => onTaskBudgetChange?.(preset)}
                        className={`px-3 py-1.5 rounded-full text-[11px] font-mono transition-all cursor-pointer border ${
                          Math.abs(taskBudget - preset) < 0.001
                            ? 'bg-white/15 border-white/30 text-white font-bold'
                            : 'bg-white/5 border-white/8 text-[#A3AEAA] hover:text-white hover:bg-white/10'
                        }`}
                      >
                        ${preset.toFixed(2)}
                      </button>
                    ))}
                  </div>
                </div>
                <p className="text-[11px] text-[#9CA3AF]">
                  Sent as <span className="font-mono">budget_usd</span> when a task is created. The
                  backend stops execution (skipping remaining stages) instead of overspending this cap.
                </p>
              </div>

              {/* Toggle 1: Approval required before file changes */}
              <div className="flex items-center justify-between p-4 bg-[#0F141A] border border-white/8 rounded-2xl">
                <div className="space-y-0.5 pr-4">
                  <div className="text-xs font-semibold text-white">Approval Required Before File Changes</div>
                  <div className="text-[11px] text-[#9CA3AF]">
                    Require interactive human authorization before any patch is committed to the working tree.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setRequireApprovalForFiles(!requireApprovalForFiles)}
                  className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                    requireApprovalForFiles ? 'bg-[#93C5FD]' : 'bg-white/10'
                  }`}
                >
                  <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                    requireApprovalForFiles ? 'right-1' : 'left-1'
                  }`} />
                </button>
              </div>

              {/* Toggle 2: Approval required before terminal commands */}
              <div className="flex items-center justify-between p-4 bg-[#0F141A] border border-white/8 rounded-2xl">
                <div className="space-y-0.5 pr-4">
                  <div className="text-xs font-semibold text-white">Approval Required Before Terminal Commands</div>
                  <div className="text-[11px] text-[#9CA3AF]">
                    Prompt for confirmation prior to spawning terminal subprocesses or executing build scripts.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setRequireApprovalForCommands(!requireApprovalForCommands)}
                  className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                    requireApprovalForCommands ? 'bg-[#93C5FD]' : 'bg-white/10'
                  }`}
                >
                  <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                    requireApprovalForCommands ? 'right-1' : 'left-1'
                  }`} />
                </button>
              </div>

              {/* Allowed Write Operations */}
              <div className="space-y-2.5">
                <label className="text-xs font-semibold text-white block">Allowed Write Operations</label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: 'create', label: 'Create New Files', desc: 'Allows generating new modules' },
                    { key: 'modify', label: 'Modify Existing Files', desc: 'Allows editing project ASTs' },
                    { key: 'delete', label: 'Delete Files', desc: 'Allows pruning deprecated files' },
                    { key: 'runBuild', label: 'Execute Build Targets', desc: 'Allows running npm build/test' },
                  ].map((op) => (
                    <div
                      key={op.key}
                      onClick={() => setAllowedWriteOps(prev => ({ ...prev, [op.key]: !prev[op.key as keyof typeof prev] }))}
                      className={`p-3 rounded-2xl border cursor-pointer transition-colors ${
                        allowedWriteOps[op.key as keyof typeof allowedWriteOps]
                          ? 'bg-white/8 border-white/15 text-white'
                          : 'bg-[#0F141A] border-white/6 text-[#9CA3AF]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium">{op.label}</span>
                        {allowedWriteOps[op.key as keyof typeof allowedWriteOps] && <Check size={12} className="text-[#93C5FD]" />}
                      </div>
                      <span className="text-[10px] text-[#6B7280] block mt-0.5">{op.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Command Timeout & Step Caps */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-white block">Command Timeout</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={commandTimeoutSec}
                      onChange={(e) => setCommandTimeoutSec(Number(e.target.value))}
                      className="w-full h-10 rounded-full bg-[#0F141A] border border-white/12 px-3 text-xs font-mono text-center text-white focus:outline-hidden"
                    />
                    <span className="text-xs text-[#9CA3AF] font-mono">sec</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-white block">Max Files Per Run</label>
                  <input
                    type="number"
                    value={maxFilesPerRun}
                    onChange={(e) => setMaxFilesPerRun(Number(e.target.value))}
                    className="w-full h-10 rounded-full bg-[#0F141A] border border-white/12 px-3 text-xs font-mono text-center text-white focus:outline-hidden"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-white block">Max Steps Per Task</label>
                  <input
                    type="number"
                    value={maxExecutionSteps}
                    onChange={(e) => setMaxExecutionSteps(Number(e.target.value))}
                    className="w-full h-10 rounded-full bg-[#0F141A] border border-white/12 px-3 text-xs font-mono text-center text-white focus:outline-hidden"
                  />
                </div>
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 3: VERIFICATION ================= */}
          {activeSection === 'verification' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <ShieldCheck size={16} className="text-[#93C5FD]" />
                  <span>Verification & Quality Checks</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Automated test runners, static linters, regression guards, and self-healing policies
                </p>
              </div>

              {/* Toggles Grid */}
              <div className="space-y-3">
                {[
                  { state: enableTypeScript, setter: setEnableTypeScript, title: 'Enable TypeScript Checks', desc: 'Executes tsc --noEmit across working tree to ensure 100% type soundness' },
                  { state: enableLinting, setter: setEnableLinting, title: 'Enable Linting', desc: 'Validates code styling & structural rules via configured ESLint or Biome' },
                  { state: enableTests, setter: setEnableTests, title: 'Enable Automated Tests', desc: 'Runs unit and integration suites (Vitest/Jest) on affected modules' },
                  { state: enableBuildVerification, setter: setEnableBuildVerification, title: 'Enable Build Verification', desc: 'Confirms production bundle compiles cleanly with no bundle errors' },
                  { state: enableSecurityChecks, setter: setEnableSecurityChecks, title: 'Enable Security Checks', desc: 'Static AST scanner for leaked tokens, SQL injections, and risky APIs' },
                  { state: retryFailedVerification, setter: setRetryFailedVerification, title: 'Retry Failed Verification', desc: 'Allows agent to read compiler/test logs and make 1 automatic self-healing patch' },
                  { state: escalateOnFailure, setter: setEscalateOnFailure, title: 'Escalate to Stronger Model After Failure', desc: 'Automatically escalates to reasoning tier if a test regression persists' },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3.5 bg-[#0F141A] border border-white/8 rounded-2xl">
                    <div className="space-y-0.5 pr-4">
                      <div className="text-xs font-semibold text-white">{item.title}</div>
                      <div className="text-[11px] text-[#9CA3AF]">{item.desc}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => item.setter(!item.state)}
                      className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                        item.state ? 'bg-[#93C5FD]' : 'bg-white/10'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                        item.state ? 'right-1' : 'left-1'
                      }`} />
                    </button>
                  </div>
                ))}
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 4: ROUTING ================= */}
          {activeSection === 'routing' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <GitFork size={16} className="text-[#93C5FD]" />
                  <span>Model Routing & Cost Policy</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Select default capability routing preset and automated fallback behaviors
                </p>
              </div>

              {/* Presets */}
              <div className="space-y-3">
                <label className="text-xs font-semibold text-white block">Routing Policy Preset</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    { id: 'auto', title: 'Automatic Routing', desc: 'Dynamically routes simple edits to fast tier & deep refactors to reasoning tier' },
                    { id: 'fastest', title: 'Fastest Latency', desc: 'Prioritizes immediate token streaming with ultra-low turnaround times' },
                    { id: 'cheapest', title: 'Cheapest Cost', desc: 'Optimizes token spend for lightweight changes and high-volume tasks' },
                    { id: 'balanced', title: 'Balanced (Recommended)', desc: 'Optimal blend of speed, verification precision, and developer experience' },
                    { id: 'highest_quality', title: 'Highest Quality', desc: 'Dedicates high-capacity reasoning models to all task stages' },
                  ].map((preset) => (
                    <div
                      key={preset.id}
                      onClick={() => setSelectedRoutingPreset(preset.id as any)}
                      className={`p-3.5 rounded-2xl border cursor-pointer transition-all ${
                        selectedRoutingPreset === preset.id
                          ? 'bg-white/10 border-white/20 text-white shadow-md'
                          : 'bg-[#0F141A] border-white/6 text-[#9CA3AF] hover:border-white/12'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white">{preset.title}</span>
                        {selectedRoutingPreset === preset.id && <Check size={13} className="text-[#93C5FD]" />}
                      </div>
                      <p className="text-[11px] text-[#9CA3AF] mt-1 leading-relaxed">{preset.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Fallback Behavior */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white block">Fallback Behavior On Provider Outage</label>
                <CustomSelect
                  value={fallbackBehavior}
                  onChange={(val) => setFallbackBehavior(val)}
                  options={FALLBACK_OPTIONS}
                />
              </div>

              {/* Console Governance Note */}
              <div className="p-4 rounded-2xl bg-white/4 border border-white/8 flex items-center justify-between gap-3 text-xs">
                <div className="text-[#9CA3AF]">
                  Model credentials, per-user token quotas, and enterprise rate limits are managed in <span className="text-white font-medium">Rivet Console</span>.
                </div>
                <button
                  type="button"
                  onClick={() => triggerToast('Opening Rivet Console Runtime Policy...')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/8 hover:bg-white/14 text-white text-[11px] font-medium transition-colors shrink-0 cursor-pointer"
                >
                  <span>Runtime Policy</span>
                  <ExternalLink size={11} />
                </button>
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 5: CONTEXT & PRIVACY ================= */}
          {activeSection === 'context_privacy' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Lock size={16} className="text-[#93C5FD]" />
                  <span>Context & Privacy</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Protect proprietary code, redact environmental secrets, and control snapshot retention
                </p>
              </div>

              {/* Toggles */}
              <div className="space-y-3">
                <div className="flex items-center justify-between p-4 bg-[#0F141A] border border-white/8 rounded-2xl">
                  <div className="space-y-0.5 pr-4">
                    <div className="text-xs font-semibold text-white">Ignore Secrets & Environment Files</div>
                    <div className="text-[11px] text-[#9CA3AF]">
                      Automatically strip .env, .env.local, .pem, and key files before model context ingestion.
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIgnoreSecretsAndEnv(!ignoreSecretsAndEnv)}
                    className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                      ignoreSecretsAndEnv ? 'bg-[#93C5FD]' : 'bg-white/10'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                      ignoreSecretsAndEnv ? 'right-1' : 'left-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 bg-[#0F141A] border border-white/8 rounded-2xl">
                  <div className="space-y-0.5 pr-4">
                    <div className="text-xs font-semibold text-white">Redact Sensitive Values</div>
                    <div className="text-[11px] text-[#9CA3AF]">
                      Inline regex sanitizer that blanks Bearer tokens, private certificates, and JWTs in diffs.
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setRedactSensitiveValues(!redactSensitiveValues)}
                    className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                      redactSensitiveValues ? 'bg-[#93C5FD]' : 'bg-white/10'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                      redactSensitiveValues ? 'right-1' : 'left-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 bg-[#0F141A] border border-white/8 rounded-2xl">
                  <div className="space-y-0.5 pr-4">
                    <div className="text-xs font-semibold text-white">Store Run History & Snapshots</div>
                    <div className="text-[11px] text-[#9CA3AF]">
                      Retain encrypted local audit log of reasoning traces and patch rollbacks.
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setStoreRunHistory(!storeRunHistory)}
                    className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                      storeRunHistory ? 'bg-[#93C5FD]' : 'bg-white/10'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                      storeRunHistory ? 'right-1' : 'left-1'
                    }`} />
                  </button>
                </div>
              </div>

              {/* Max Context Size */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-white block">Maximum Context Size</label>
                <CustomSelect
                  value={maxContextSize}
                  onChange={(val) => setMaxContextSize(val)}
                  options={CONTEXT_OPTIONS}
                />
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 6: TOOLS & INTEGRATIONS ================= */}
          {activeSection === 'tools_integrations' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Wrench size={16} className="text-[#93C5FD]" />
                  <span>Tools & Integrations</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Model Context Protocol (MCP) servers, terminal permissions, and external bridges
                </p>
              </div>

              {/* Git & Terminal Permissions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-white block">Git Access Level</label>
                  <CustomSelect
                    value={gitAccess}
                    onChange={(val) => setGitAccess(val as any)}
                    options={GIT_ACCESS_OPTIONS}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-white block">Terminal Subprocess Access</label>
                  <CustomSelect
                    value={terminalAccess}
                    onChange={(val) => setTerminalAccess(val as any)}
                    options={TERMINAL_ACCESS_OPTIONS}
                  />
                </div>
              </div>

              {/* MCP Servers */}
              <div className="space-y-3">
                <label className="text-xs font-semibold text-white block">Connected Model Context Protocol (MCP) Tools</label>
                {[
                  { state: mcpFilesystem, setter: setMcpFilesystem, name: 'Filesystem MCP Server', detail: 'Read/write access to project directory AST' },
                  { state: mcpPostgres, setter: setMcpPostgres, name: 'PostgreSQL Schema Inspector', detail: 'Introspect local database migrations & schemas' },
                  { state: mcpGithub, setter: setMcpGithub, name: 'GitHub PR & Issue Bridge', detail: 'Query issue descriptions and pull request reviews' },
                ].map((mcp, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3.5 bg-[#0F141A] border border-white/8 rounded-2xl">
                    <div>
                      <div className="text-xs font-semibold text-white flex items-center gap-2">
                        <span>{mcp.name}</span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/6 text-[#93C5FD]">
                          MCP v1.2
                        </span>
                      </div>
                      <div className="text-[11px] text-[#9CA3AF] mt-0.5">{mcp.detail}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => mcp.setter(!mcp.state)}
                      className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                        mcp.state ? 'bg-[#93C5FD]' : 'bg-white/10'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                        mcp.state ? 'right-1' : 'left-1'
                      }`} />
                    </button>
                  </div>
                ))}
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 7: NOTIFICATIONS ================= */}
          {activeSection === 'notifications' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Bell size={16} className="text-[#93C5FD]" />
                  <span>Notifications & Alerts</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Configure alerts for task completions, verification failures, and approvals
                </p>
              </div>

              <div className="space-y-3">
                {[
                  { state: notifyTaskCompleted, setter: setNotifyTaskCompleted, title: 'Task Completed', desc: 'Display desktop notification and play subtle chime when reasoning finishes' },
                  { state: notifyVerificationFailed, setter: setNotifyVerificationFailed, title: 'Verification Failed', desc: 'Alert with high-priority visual indicator when type or test suite fails' },
                  { state: notifyApprovalRequired, setter: setNotifyApprovalRequired, title: 'Approval Required', desc: 'Bring IDE window into focus when human confirmation is needed' },
                  { state: notifyRuntimeBlocked, setter: setNotifyRuntimeBlocked, title: 'Runtime Blocked', desc: 'Notify immediately if a security rule or policy blocks a file write' },
                  { state: notifyProviderFallback, setter: setNotifyProviderFallback, title: 'Provider Fallback', desc: 'Show toast notice if active model switches due to upstream rate limits' },
                  { state: notifyBudgetWarning, setter: setNotifyBudgetWarning, title: 'Budget Warning', desc: 'Notify when task token consumption crosses 80% threshold' },
                ].map((n, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3.5 bg-[#0F141A] border border-white/8 rounded-2xl">
                    <div className="space-y-0.5 pr-4">
                      <div className="text-xs font-semibold text-white">{n.title}</div>
                      <div className="text-[11px] text-[#9CA3AF]">{n.desc}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => n.setter(!n.state)}
                      className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                        n.state ? 'bg-[#93C5FD]' : 'bg-white/10'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                        n.state ? 'right-1' : 'left-1'
                      }`} />
                    </button>
                  </div>
                ))}
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 8: APPEARANCE ================= */}
          {activeSection === 'appearance' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <Palette size={16} className="text-[#93C5FD]" />
                  <span>Appearance & Density</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Visual theme palettes, layout density, and keyboard shortcut configuration
                </p>
              </div>

              {/* Theme Options */}
              <div className="space-y-2.5">
                <label className="text-xs font-semibold text-white block">Theme Palette</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { id: 'dark_slate', label: 'Dark Slate (Active)', color: '#121820' },
                    { id: 'midnight', label: 'Midnight Void', color: '#090D12' },
                    { id: 'oled', label: 'OLED Pure Black', color: '#000000' },
                    { id: 'light', label: 'System Light', color: '#F3F4F6' },
                  ].map((thm) => (
                    <button
                      key={thm.id}
                      type="button"
                      onClick={() => setThemeMode(thm.id as any)}
                      className={`p-3 rounded-2xl border text-left cursor-pointer transition-all ${
                        themeMode === thm.id
                          ? 'bg-white/10 border-white/20 text-white shadow-md'
                          : 'bg-[#0F141A] border-white/6 text-[#9CA3AF] hover:border-white/12'
                      }`}
                    >
                      <div className="w-5 h-5 rounded-full border border-white/20 mb-2" style={{ backgroundColor: thm.color }} />
                      <div className="text-xs font-medium truncate">{thm.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Density Options */}
              <div className="space-y-2.5">
                <label className="text-xs font-semibold text-white block">Layout Density</label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: 'comfortable', label: 'Comfortable Density', desc: 'Bubbly, spacious padding with enhanced readability' },
                    { id: 'compact', label: 'Compact Density', desc: 'High information density for small displays & multi-split screens' },
                  ].map((den) => (
                    <div
                      key={den.id}
                      onClick={() => setDensity(den.id as any)}
                      className={`p-3.5 rounded-2xl border cursor-pointer transition-all ${
                        density === den.id
                          ? 'bg-white/10 border-white/20 text-white shadow-md'
                          : 'bg-[#0F141A] border-white/6 text-[#9CA3AF] hover:border-white/12'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-white">{den.label}</span>
                        {density === den.id && <Check size={12} className="text-[#93C5FD]" />}
                      </div>
                      <p className="text-[11px] text-[#9CA3AF] mt-1">{den.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Toggles */}
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3.5 bg-[#0F141A] border border-white/8 rounded-2xl">
                  <div className="space-y-0.5 pr-4">
                    <div className="text-xs font-semibold text-white">Show Routing Details in Status Bar</div>
                    <div className="text-[11px] text-[#9CA3AF]">Display active model tier and provider in header pills.</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowRoutingDetails(!showRoutingDetails)}
                    className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                      showRoutingDetails ? 'bg-[#93C5FD]' : 'bg-white/10'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                      showRoutingDetails ? 'right-1' : 'left-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between p-3.5 bg-[#0F141A] border border-white/8 rounded-2xl">
                  <div className="space-y-0.5 pr-4">
                    <div className="text-xs font-semibold text-white">Show Exact Cost & Latency Metrics</div>
                    <div className="text-[11px] text-[#9CA3AF]">Display exact dollar cost and millisecond latency on task cards.</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowCostAndLatency(!showCostAndLatency)}
                    className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 ${
                      showCostAndLatency ? 'bg-[#93C5FD]' : 'bg-white/10'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-zinc-900 absolute top-1 transition-transform ${
                      showCostAndLatency ? 'right-1' : 'left-1'
                    }`} />
                  </button>
                </div>
              </div>

              {/* Keyboard Shortcuts Cheat Sheet */}
              <div className="p-4 bg-[#0F141A] border border-white/8 rounded-2xl space-y-2">
                <div className="text-xs font-semibold text-white">Keyboard Shortcuts</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs font-mono text-[#9CA3AF] pt-1">
                  <div className="flex items-center justify-between bg-white/4 p-2 rounded-xl">
                    <span>New Task</span>
                    <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">⌘N</span>
                  </div>
                  <div className="flex items-center justify-between bg-white/4 p-2 rounded-xl">
                    <span>Send Prompt</span>
                    <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">Enter</span>
                  </div>
                  <div className="flex items-center justify-between bg-white/4 p-2 rounded-xl">
                    <span>Toggle Inspector</span>
                    <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">⌘B</span>
                  </div>
                  <div className="flex items-center justify-between bg-white/4 p-2 rounded-xl">
                    <span>Authorize Patch</span>
                    <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">⌘A</span>
                  </div>
                  <div className="flex items-center justify-between bg-white/4 p-2 rounded-xl">
                    <span>Stop Agent</span>
                    <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">Esc</span>
                  </div>
                  <div className="flex items-center justify-between bg-white/4 p-2 rounded-xl">
                    <span>Settings</span>
                    <span className="text-white font-bold bg-white/10 px-2 py-0.5 rounded">⌘,</span>
                  </div>
                </div>
              </div>

            </motion.div>
          )}

          {/* ================= SECTION 9: ACCOUNT & DIAGNOSTICS ================= */}
          {activeSection === 'account_diagnostics' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#121820]/95 border border-white/10 rounded-[28px] p-5 sm:p-7 space-y-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="pb-3 border-b border-white/8">
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <UserCheck size={16} className="text-[#93C5FD]" />
                  <span>Account & System Diagnostics</span>
                </h2>
                <p className="text-xs text-[#9CA3AF] mt-0.5">
                  Developer session, daemon heartbeat telemetry, and crash dump exports
                </p>
              </div>

              {/* Developer Account Info */}
              <div className="p-4 bg-[#0F141A] border border-white/8 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-white/10 border border-white/15 flex items-center justify-center font-bold text-white">
                    {currentUser[0].toUpperCase()}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white">{currentUser}</div>
                    <div className="text-[11px] text-[#9CA3AF] font-mono">Developer Tier · Authorized</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => triggerToast('Signed out of local workspace session')}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-medium transition-colors cursor-pointer shrink-0"
                >
                  <LogOut size={13} />
                  <span>Sign Out</span>
                </button>
              </div>

              {/* Connected Runtime & Health */}
              <div className="p-4 bg-[#0F141A] border border-white/8 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-white">Connected Runtime Daemon</span>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Healthy (14ms)</span>
                  </span>
                </div>
                <div className="text-xs font-mono text-[#9CA3AF] bg-black/40 p-3 rounded-xl border border-white/6">
                  {connectedRuntime} · Protocol WebSocket Secure
                </div>
              </div>

              {/* Action Buttons: Clear Cache & Export Diagnostics */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={handleClearCache}
                  className="flex items-center justify-center gap-2 p-3.5 rounded-2xl bg-white/6 hover:bg-white/10 border border-white/10 text-xs font-semibold text-white transition-colors cursor-pointer shadow-sm"
                >
                  <Trash2 size={14} className="text-[#FF7D7D]" />
                  <span>Clear Local AST Cache</span>
                </button>

                <button
                  type="button"
                  onClick={handleExportDiagnostics}
                  className="flex items-center justify-center gap-2 p-3.5 rounded-2xl bg-white text-zinc-900 hover:bg-zinc-200 border border-white/40 text-xs font-semibold transition-all cursor-pointer shadow-md"
                >
                  <Download size={14} />
                  <span>Export Diagnostic Information</span>
                </button>
              </div>

              {/* Version & Build Metadata */}
              <div className="pt-2 text-center text-[11px] font-mono text-[#6F7B77]">
                Zyntry Code Extension v2.4.1 (Build 2026.10.05) · Extension Host API v1.94
              </div>

            </motion.div>
          )}

        </div>
      </div>
    </div>
  );
};
