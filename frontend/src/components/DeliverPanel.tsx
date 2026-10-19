import React, { useState } from 'react';
import { motion } from 'motion/react';
import { X, GitPullRequest, Loader2, CheckCircle2, AlertCircle, ShieldAlert } from 'lucide-react';
import { api, BackendToolRequest } from '../api/client';

interface DeliverPanelProps {
  isOpen: boolean;
  workspaceId?: string;
  title: string;
  onClose: () => void;
}

export const DeliverPanel: React.FC<DeliverPanelProps> = ({
  isOpen,
  workspaceId,
  title,
  onClose,
}) => {
  const [requests, setRequests] = useState<BackendToolRequest[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  if (!isOpen) return null;

  const deliver = async () => {
    if (!workspaceId) return;
    setBusy(true);
    setMessage(null);
    try {
      const resp = await api.deliver(workspaceId, title || 'Zyntry Code changes');
      setRequests(resp.tool_requests);
      setMessage({
        ok: true,
        text: 'Delivery queued: commit (immediate), push + PR awaiting approval.',
      });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };

  const refresh = async () => {
    if (!workspaceId) return;
    try {
      const resp = await api.getToolRequests(workspaceId);
      setRequests(resp.tool_requests.filter((r) => r.tool !== 'fs.write'));
    } catch {
      /* keep current list */
    }
  };

  const approve = async (requestId: string) => {
    if (!workspaceId) return;
    setBusy(true);
    try {
      await api.approveToolRequest(workspaceId, requestId);
      await refresh();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : String(err) });
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
            <div className="w-9 h-9 rounded-2xl bg-[#55E6A5]/15 border border-[#55E6A5]/30 flex items-center justify-center text-[#55E6A5]">
              <GitPullRequest size={17} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-[#F2F6F4]">Deliver changes</h2>
              <p className="text-[11px] text-[#A3AEAA]">
                Commit → push → pull request (push/PR require your approval)
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-[#6F7B77] hover:text-[#F2F6F4]">
            <X size={16} />
          </button>
        </div>

        {!workspaceId ? (
          <div className="text-[12px] text-[#F87171] bg-[#2A150F] border border-[#F87171]/30 rounded-lg px-3 py-2 font-mono">
            No workspace attached to this task — create one first (Workspace button).
          </div>
        ) : (
          <>
            <button
              onClick={deliver}
              disabled={busy}
              className="w-full py-2.5 rounded-full bg-white text-zinc-900 text-xs font-bold hover:bg-zinc-200 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
            >
              {busy ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <GitPullRequest size={13} />
              )}
              Queue delivery (commit + push + PR)
            </button>

            {message && (
              <div
                className={`flex items-start gap-1.5 text-[11px] font-mono rounded-lg px-3 py-2 border ${
                  message.ok
                    ? 'text-[#55E6A5] bg-[#0E2A1C] border-[#55E6A5]/25'
                    : 'text-[#F87171] bg-[#2A150F] border-[#F87171]/30'
                }`}
              >
                {message.ok ? <CheckCircle2 size={12} className="mt-0.5" /> : <AlertCircle size={12} className="mt-0.5" />}
                {message.text}
              </div>
            )}

            {requests.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] font-mono text-[#6F7B77] uppercase tracking-wider">
                  Delivery steps
                </div>
                {requests.map((req) => (
                  <div
                    key={req.id}
                    className="flex items-center justify-between gap-2 p-3 rounded-xl bg-black/30 border border-white/8"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[11px] font-mono text-[#93C5FD] whitespace-nowrap">
                        {req.tool}
                      </span>
                      <span className="text-[11px] font-mono text-[#A3AEAA] truncate">
                        {req.tool === 'github.pr' ? String(req.params.title ?? '') : String(req.params.remote ?? '')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {req.status === 'awaiting_approval' ? (
                        <>
                          <span className="flex items-center gap-1 text-[10px] font-mono text-amber-300">
                            <ShieldAlert size={11} /> needs approval
                          </span>
                          <button
                            onClick={() => approve(req.id)}
                            disabled={busy}
                            className="px-3 py-1 rounded-full bg-[#55E6A5]/15 border border-[#55E6A5]/40 text-[#55E6A5] text-[10px] font-bold hover:bg-[#55E6A5]/25 cursor-pointer disabled:opacity-50"
                          >
                            Approve
                          </button>
                        </>
                      ) : (
                        <span
                          className={`text-[10px] font-mono px-2 py-1 rounded-full border ${
                            req.status === 'succeeded'
                              ? 'text-[#55E6A5] border-[#55E6A5]/30 bg-[#55E6A5]/10'
                              : req.status === 'failed'
                              ? 'text-[#F87171] border-[#F87171]/30 bg-[#F87171]/10'
                              : 'text-[#93C5FD] border-[#93C5FD]/30 bg-[#93C5FD]/10'
                          }`}
                        >
                          {req.status}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </motion.div>
    </div>
  );
};