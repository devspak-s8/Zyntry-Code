import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ExecutionStageItem } from '../types';
import { 
  Check, 
  Loader2, 
  Clock, 
  X, 
  ChevronDown, 
  GitBranch, 
  ArrowRight, 
  Cpu, 
  ShieldCheck,
  Layers
} from 'lucide-react';

interface ExecutionVisibilityProps {
  stages: ExecutionStageItem[];
  title?: string;
  defaultExpanded?: boolean;
  taskBudget?: number;
  totalCost?: number;
  executionMode?: 'auto' | 'custom';
}

export const ExecutionVisibility: React.FC<ExecutionVisibilityProps> = ({
  stages,
  title = 'Engineering Execution Loop',
  defaultExpanded = true,
  taskBudget = 0.20,
  totalCost = 0.0165,
  executionMode = 'auto',
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [selectedHandoff, setSelectedHandoff] = useState<ExecutionStageItem | null>(null);

  if (!stages || stages.length === 0) return null;

  const completedStages = stages.filter((s) => s.status === 'complete').length;
  const isAnyRunning = stages.some((s) => s.status === 'running');

  return (
    <div className="bg-[#10151B] border border-white/10 rounded-2xl overflow-hidden text-xs shadow-md">
      {/* Header Bar */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#131A22] hover:bg-[#16202B] transition-colors cursor-pointer text-left border-b border-white/6"
      >
        <div className="flex items-center gap-2.5">
          <motion.div
            animate={{ rotate: isExpanded ? 0 : -90 }}
            transition={{ type: 'spring', stiffness: 350, damping: 25 }}
            className="text-[#6F7B77]"
          >
            <ChevronDown size={14} />
          </motion.div>
          <div className="w-5 h-5 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center text-white">
            <Layers size={12} />
          </div>
          <span className="font-semibold text-[#F2F6F4] text-xs">{title}</span>
          <span className="font-mono text-[10px] text-[#93C5FD] bg-[#93C5FD]/10 border border-[#93C5FD]/20 px-2 py-0.5 rounded-full uppercase">
            {executionMode} mode
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-[11px] font-mono text-[#9CA3AF] tabular-nums hidden sm:flex items-center gap-1.5">
            <span>Spend:</span>
            <span className="text-[#93C5FD] font-semibold">${totalCost.toFixed(4)}</span>
            <span className="text-[#6F7B77]">/ ${taskBudget.toFixed(2)} cap</span>
          </div>

          <span className="text-[11px] text-[#A3AEAA] font-mono tabular-nums">
            {completedStages}/{stages.length} stages
          </span>
        </div>
      </button>

      {/* Expanded Stages List */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="divide-y divide-white/5 bg-[#0D1217]"
          >
            {/* The Execution Steps */}
            <div className="p-3.5 space-y-2">
              {stages.map((stage) => {
                const isComplete = stage.status === 'complete';
                const isRunning = stage.status === 'running';
                const isWaiting = stage.status === 'waiting';
                const isFailed = stage.status === 'failed';

                return (
                  <div
                    key={stage.id}
                    className="p-2.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-white/5 transition-all text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="flex items-start sm:items-center gap-3">
                      {/* Status Icon */}
                      <div className="mt-0.5 sm:mt-0 shrink-0">
                        {isComplete && (
                          <div className="w-4.5 h-4.5 rounded-md bg-[#55E6A5]/15 border border-[#55E6A5]/30 flex items-center justify-center text-[#55E6A5]">
                            <Check size={11} strokeWidth={2.5} />
                          </div>
                        )}
                        {isRunning && (
                          <div className="w-4.5 h-4.5 rounded-md bg-[#93C5FD]/15 border border-[#93C5FD]/30 flex items-center justify-center text-[#93C5FD]">
                            <Loader2 size={11} className="animate-spin" />
                          </div>
                        )}
                        {isWaiting && (
                          <div className="w-4.5 h-4.5 rounded-md bg-white/5 border border-white/10 flex items-center justify-center text-[#6F7B77]">
                            <Clock size={11} />
                          </div>
                        )}
                        {isFailed && (
                          <div className="w-4.5 h-4.5 rounded-md bg-[#FF7D7D]/15 border border-[#FF7D7D]/30 flex items-center justify-center text-[#FF7D7D]">
                            <X size={11} strokeWidth={2.5} />
                          </div>
                        )}
                      </div>

                      {/* Label & Details */}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${isComplete ? 'text-[#F2F6F4]' : isRunning ? 'text-[#93C5FD] font-semibold' : 'text-[#A3AEAA]'}`}>
                            {stage.name}
                          </span>
                          {stage.parallelBranch && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                              <GitBranch size={9} />
                              <span>{stage.parallelBranch}</span>
                            </span>
                          )}
                        </div>

                        {stage.detail && (
                          <div className="text-[11px] text-[#A3AEAA] font-mono mt-0.5 leading-snug">
                            {stage.detail}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right side: Model routing & handoff metadata */}
                    <div className="flex items-center gap-2 self-end sm:self-center shrink-0 text-[11px] font-mono">
                      {stage.modelAssigned && (
                        <span className="text-[#A3AEAA] bg-white/5 border border-white/10 px-2 py-0.5 rounded text-[10px] flex items-center gap-1">
                          <Cpu size={10} className="text-[#93C5FD]" />
                          <span>{stage.modelAssigned}</span>
                        </span>
                      )}

                      {stage.durationMs && (
                        <span className="text-[#6F7B77] text-[10px] tabular-nums">
                          {stage.durationMs}ms
                        </span>
                      )}

                      {stage.handoffSummary && (
                        <button
                          type="button"
                          onClick={() => setSelectedHandoff(stage)}
                          className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-[#93C5FD] border border-white/10 text-[10px] cursor-pointer transition-colors"
                        >
                          Handoff
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Loop Flow Diagram Indicator */}
            <div className="px-4 py-2.5 bg-[#090C0E] border-t border-white/5 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-[#6F7B77]">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[#93C5FD] font-semibold">Loop:</span>
                <span>UNDERSTAND</span>
                <ArrowRight size={10} />
                <span>DECOMPOSE</span>
                <ArrowRight size={10} />
                <span>PLAN</span>
                <ArrowRight size={10} />
                <span>ASSIGN</span>
                <ArrowRight size={10} />
                <span>EXECUTE</span>
                <ArrowRight size={10} />
                <span>VERIFY</span>
                <ArrowRight size={10} />
                <span>PROVE</span>
              </div>
              <div className="flex items-center gap-1 text-[#55E6A5]">
                <ShieldCheck size={11} />
                <span>Escalation guard ready</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Intelligent Handoff Modal */}
      {selectedHandoff && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[#121820] border border-white/15 rounded-2xl p-5 space-y-3.5 shadow-2xl text-xs">
            <div className="flex items-center justify-between border-b border-white/8 pb-2.5">
              <div className="flex items-center gap-2">
                <Cpu size={14} className="text-[#93C5FD]" />
                <span className="font-semibold text-white">Intelligent Model Handoff</span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedHandoff(null)}
                className="text-[#9CA3AF] hover:text-white p-1 rounded-md hover:bg-white/10"
              >
                <X size={14} />
              </button>
            </div>

            <div className="space-y-2">
              <div className="text-[11px] text-[#9CA3AF]">
                Origin Stage: <span className="text-white font-medium">{selectedHandoff.name}</span>
              </div>
              <div className="text-[11px] text-[#9CA3AF]">
                Model: <span className="text-[#93C5FD] font-mono">{selectedHandoff.modelAssigned}</span>
              </div>
              <div className="p-3 bg-black/40 border border-white/10 rounded-xl font-mono text-[11px] text-[#F2F6F4] leading-relaxed">
                {selectedHandoff.handoffSummary}
              </div>
              <p className="text-[10px] text-[#6F7B77] leading-relaxed">
                Structured handoff contains the task spec, symbol scope, applied patches, and test results rather than an unfiltered conversational dump.
              </p>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => setSelectedHandoff(null)}
                className="px-3.5 py-1.5 bg-white/10 hover:bg-white/15 text-white rounded-xl text-xs font-medium cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
