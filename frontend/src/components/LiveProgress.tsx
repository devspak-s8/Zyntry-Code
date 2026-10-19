import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AgentState, ToolActivityItem } from '../types';
import { Loader2, Check, X, Terminal, Cpu, SearchCheck } from 'lucide-react';

/**
 * Live execution progress rendered directly on the page (no card) while the
 * agent runs — Codex/OpenCode style: a plain animated status line followed by
 * a raw terminal feed of what the agent is doing right now.
 */

interface LiveProgressProps {
  agentState: AgentState;
  liveActivities: ToolActivityItem[];
}

const STATE_LABELS: Record<string, string> = {
  planning: 'Planning & routing stages…',
  working: 'Agent is executing…',
  verifying: 'Verification running…',
  applying_changes: 'Applying changes…',
};

export const LiveProgress: React.FC<LiveProgressProps> = ({
  agentState,
  liveActivities,
}) => {
  const label = STATE_LABELS[agentState] ?? 'Agent is working…';

  const visible = liveActivities.slice(0, 12);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 320, damping: 28 }}
      className="w-full space-y-2.5"
    >
      {/* Plain status line — no card */}
      <div className="flex items-center gap-2.5 px-1">
        <Loader2 size={13} className="animate-spin text-[#82B9FF] shrink-0" />
        <span className="text-xs font-semibold text-[#F2F6F4] tracking-tight">
          {label}
        </span>
        <span className="font-mono text-[10px] text-[#6F7B77] tabular-nums">
          {liveActivities.length} event{liveActivities.length === 1 ? '' : 's'}
        </span>
      </div>

      {/* Live feed (newest first, like a terminal), directly on the page — no fixed height, no scroll bar */}
      <div>
        {visible.length === 0 ? (
          <div className="px-1 space-y-2.5">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                animate={{ opacity: [0.3, 0.65, 0.3] }}
                transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.25 }}
                className="flex items-center gap-2.5"
              >
                <div className="w-3 h-3 rounded-full bg-white/10 shrink-0" />
                <div
                  className="h-2.5 rounded-full bg-white/8"
                  style={{ width: `${76 - i * 14}%` }}
                />
              </motion.div>
            ))}
            <p className="text-[10px] font-mono text-[#6F7B77]">
              Waiting for the first execution events…
            </p>
          </div>
        ) : (
          <div className="space-y-1 font-mono text-[11px]">
            <AnimatePresence initial={false}>
              {visible.map((act) => (
                <motion.div
                  key={act.id}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex items-center justify-between gap-3 py-1 px-1.5 text-[#A3AEAA]"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-4 flex justify-center shrink-0">
                      {act.status === 'running' && (
                        <Loader2 size={11} className="animate-spin text-[#82B9FF]" />
                      )}
                      {act.status === 'complete' && (
                        <Check size={11} className="text-[#55E6A5]" />
                      )}
                      {act.status === 'failed' && (
                        <X size={11} className="text-[#FF7D7D]" />
                      )}
                    </div>
                    <div className="w-5 h-5 rounded-md bg-[#12161A] flex items-center justify-center shrink-0">
                      {act.action === 'agent_tool_call' ? (
                        <Terminal size={11} className="text-[#A3AEAA]" />
                      ) : act.action === 'verification_failed' ? (
                        <SearchCheck size={11} className="text-[#FF7D7D]" />
                      ) : (
                        <Cpu size={11} className="text-[#6F7B77]" />
                      )}
                    </div>
                    <span className="truncate text-[#F2F6F4]">{act.name}</span>
                  </div>
                  <span className="shrink-0 text-[10px] text-[#6F7B77] tabular-nums">
                    {act.timestamp}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  );
};