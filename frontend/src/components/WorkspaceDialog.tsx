import React, { useState } from 'react';
import { motion } from 'motion/react';
import { X, Server, Loader2 } from 'lucide-react';
import { api, BackendWorkspace } from '../api/client';

interface WorkspaceDialogProps {
  isOpen: boolean;
  taskId?: string;
  onClose: () => void;
  onCreated: (workspace: BackendWorkspace) => void;
}

const COMMAND_PRESETS = [
  { key: 'test', cmd: 'pytest' },
  { key: 'lint', cmd: 'ruff check .' },
  { key: 'type_check', cmd: 'mypy .' },
  { key: 'build', cmd: 'npm run build' },
];

export const WorkspaceDialog: React.FC<WorkspaceDialogProps> = ({
  isOpen,
  taskId,
  onClose,
  onCreated,
}) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [branch, setBranch] = useState('');
  const [provider, setProvider] = useState<'remote' | 'local'>('remote');
  const [timeoutSeconds, setTimeoutSeconds] = useState(600);
  const [commands, setCommands] = useState<Record<string, { cmd: string; dangerous?: boolean }>>({
    test: { cmd: 'pytest' },
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const toggleCommand = (key: string, presetCmd: string) => {
    setCommands((prev) => {
      const next = { ...prev };
      if (key in next) delete next[key];
      else next[key] = { cmd: presetCmd };
      return next;
    });
  };

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const ws = await api.createWorkspace({
        task_id: taskId || undefined,
        repo_url: repoUrl || undefined,
        branch: branch || undefined,
        provider,
        commands,
        timeout_seconds: timeoutSeconds,
      });
      onCreated(ws);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-lg rounded-3xl border border-white/10 bg-[#121820]/95 backdrop-blur-xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-[#93C5FD]/15 border border-[#93C5FD]/30 flex items-center justify-center text-[#93C5FD]">
              <Server size={17} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#F2F6F4]">Execution Workspace</h2>
              <p className="text-[11px] text-[#A3AEAA]">
                The runner (remote worker or local extension) operates here
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-[#6F7B77] hover:text-[#F2F6F4]">
            <X size={16} />
          </button>
        </div>

        {taskId && (
          <div className="text-[11px] font-mono text-[#6F7B77]">
            Attached to task: <span className="text-[#93C5FD]">{taskId.slice(0, 8)}</span>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="text-[11px] font-mono text-[#6F7B77] uppercase tracking-wider block mb-1">
              Repo URL (optional)
            </label>
            <input
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/org/repo.git"
              className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#82B9FF]"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-mono text-[#6F7B77] uppercase tracking-wider block mb-1">
                Branch
              </label>
              <input
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="main"
                className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#82B9FF]"
              />
            </div>
            <div>
              <label className="text-[11px] font-mono text-[#6F7B77] uppercase tracking-wider block mb-1">
                Runner
              </label>
              <div className="flex gap-1.5 p-1 bg-[#141B24] border border-white/12 rounded-full">
                {(['remote', 'local'] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => setProvider(p)}
                    className={`flex-1 py-1.5 rounded-full text-[11px] font-semibold cursor-pointer ${
                      provider === p ? 'bg-white text-zinc-950' : 'text-[#9CA3AF] hover:text-white'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="text-[11px] font-mono text-[#6F7B77] uppercase tracking-wider block mb-2">
              Verification commands (toggles)
            </label>
            <div className="flex flex-wrap gap-2">
              {COMMAND_PRESETS.map((preset) => (
                <button
                  key={preset.key}
                  onClick={() => toggleCommand(preset.key, preset.cmd)}
                  className={`px-3 py-1.5 rounded-full text-[11px] font-medium cursor-pointer border transition-all ${
                    preset.key in commands
                      ? 'bg-[#55E6A5]/10 border-[#55E6A5]/40 text-[#55E6A5]'
                      : 'bg-white/[0.04] border-white/10 text-[#A3AEAA] hover:text-white'
                  }`}
                >
                  {preset.key} {preset.key in commands ? '✓' : ''}
                </button>
              ))}
            </div>
            {Object.entries(commands).map(([key, spec]) => (
              <div key={key} className="flex items-center gap-2 mt-2">
                <span className="text-[11px] font-mono text-[#93C5FD] w-20">{key}</span>
                <input
                  value={spec.cmd}
                  onChange={(e) =>
                    setCommands((prev) => ({ ...prev, [key]: { ...spec, cmd: e.target.value } }))
                  }
                  className="flex-1 bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#82B9FF]"
                />
              </div>
            ))}
          </div>

          <div>
            <label className="text-[11px] font-mono text-[#6F7B77] uppercase tracking-wider block mb-1">
              Command timeout (seconds)
            </label>
            <input
              type="number"
              value={timeoutSeconds}
              onChange={(e) => setTimeoutSeconds(Number(e.target.value) || 600)}
              min={10}
              max={7200}
              className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#82B9FF]"
            />
          </div>
        </div>

        {error && (
          <div className="text-[11px] font-mono text-[#F87171] bg-[#2A150F] border border-[#F87171]/30 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-full border border-white/10 text-[#A3AEAA] text-xs font-semibold hover:text-white cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={create}
            disabled={busy}
            className="flex-1 py-2.5 rounded-full bg-white text-zinc-900 text-xs font-bold hover:bg-zinc-200 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
          >
            {busy && <Loader2 size={13} className="animate-spin" />}
            Create workspace
          </button>
        </div>
      </motion.div>
    </div>
  );
};