import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { TaskPlanStep } from '../types';
import { StatusBadge } from './StatusBadge';
import { ChevronDown, Layers } from 'lucide-react';

interface TaskPlanProps {
  steps: TaskPlanStep[];
  title?: string;
  defaultExpanded?: boolean;
}

export const TaskPlan: React.FC<TaskPlanProps> = ({
  steps,
  title = 'Execution Plan',
  defaultExpanded = true,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!steps || steps.length === 0) return null;

  const completedCount = steps.filter((s) => s.status === 'complete').length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);

  return (
    <div className="bg-gradient-to-b from-[#13171B] to-[#0F1316] border border-[rgba(255,255,255,0.1)] rounded-2xl overflow-hidden text-xs shadow-lg">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#171C20]/50 hover:bg-[#1A2025] transition-colors cursor-pointer text-left"
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
          <span className="text-[#6F7B77] font-mono text-[11px] tabular-nums">
            ({completedCount}/{steps.length} completed)
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Mini Progress Bar */}
          <div className="w-20 sm:w-28 h-1 bg-[#090B0D] rounded-sm overflow-hidden border border-[rgba(255,255,255,0.06)] hidden sm:block">
            <motion.div
              className="h-full bg-[#93C5FD]"
              initial={{ width: 0 }}
              animate={{ width: `${progressPercent}%` }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
            />
          </div>
          <span className="text-[11px] text-[#93C5FD] font-mono tabular-nums font-medium">
            {progressPercent}%
          </span>
        </div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="divide-y divide-[rgba(255,255,255,0.05)] px-4 py-2 bg-[#101417]">
              {steps.map((step, idx) => (
                <motion.div
                  key={step.id || idx}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05, duration: 0.2 }}
                  className="py-3 flex items-start justify-between gap-4 text-xs hover:bg-[rgba(255,255,255,0.02)] px-2 rounded-xl transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <span className="font-mono text-[10px] text-[#6F7B77] bg-[#0A0D0E] px-1.5 py-0.5 rounded mt-0.5 border border-[rgba(255,255,255,0.04)]">
                      0{idx + 1}
                    </span>
                    <div>
                      <div className="text-[#F2F6F4] font-medium leading-tight">
                        {step.label}
                      </div>
                      {step.detail && (
                        <div className="text-[#A3AEAA] text-[11px] mt-1 font-mono leading-relaxed">
                          {step.detail}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2.5 shrink-0 pt-0.5">
                    {step.durationMs && (
                      <span className="text-[10px] font-mono text-[#6F7B77] tabular-nums">
                        {step.durationMs}ms
                      </span>
                    )}
                    <StatusBadge stepStatus={step.status} />
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
