import React from 'react';
import { motion } from 'motion/react';
import { DiffFile, TaskPlanStep } from '../types';
import {
  AlertCircle,
  Check,
  X,
  FileCode,
  ShieldCheck,
  Loader2,
  ListChecks,
} from 'lucide-react';

/**
 * Codex-style inline approval prompt.
 *
 * Rendered at the input side (in place of the composer) instead of a modal:
 * the question appears anchored to the bottom of the chat, right where the
 * developer is typing, with Approve / Reject actions inline.
 */

export type ApprovalVariant = 'pre-execution' | 'apply-changes';

interface InlineApprovalProps {
  isOpen: boolean;
  variant: ApprovalVariant;
  files: DiffFile[];
  planSteps?: TaskPlanStep[];
  isSubmitting?: boolean;
  onApprove: () => void;
  onReject: () => void;
  onDismiss?: () => void;
}

export const InlineApproval: React.FC<InlineApprovalProps> = ({
  isOpen,
  variant,
  files,
  planSteps = [],
  isSubmitting = false,
  onApprove,
  onReject,
  onDismiss,
}) => {
  if (!isOpen) return null;

  const totalAdded = files.reduce((acc, f) => acc + f.addedCount, 0);
  const totalRemoved = files.reduce((acc, f) => acc + f.removedCount, 0);
  const isPreExecution = variant === 'pre-execution';

  return (
    <div className="absolute bottom-4 sm:bottom-6 left-0 right-0 px-3.5 sm:px-6 pointer-events-none z-30 flex justify-center">
      <motion.div
        role="dialog"
        aria-modal="false"
        aria-labelledby="inline-approval-title"
        initial={{ opacity: 0, y: 16, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 16, scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 420, damping: 30 }}
        className="pointer-events-auto w-full max-w-2xl sm:max-w-3xl bg-[#121821]/95 border border-[#55E6A5]/30 rounded-[24px] sm:rounded-[28px] p-4 sm:p-5 space-y-3 shadow-2xl backdrop-blur-2xl glow-card"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#1A4536] to-[#122C23] border border-[#2D9E70] flex items-center justify-center text-[#55E6A5] shrink-0 shadow-xs">
              <ShieldCheck size={15} />
            </div>
            <div>
              <h2
                id="inline-approval-title"
                className="text-xs sm:text-[13px] font-bold text-[#F2F6F4] tracking-tight"
              >
                {isPreExecution
                  ? 'High-risk task needs your approval'
                  : 'Apply changes to workspace?'}
              </h2>
              <p className="text-[11px] text-[#A3AEAA] mt-0.5">
                {isPreExecution
                  ? 'Review the plan before execution starts'
                  : 'Zyntry Code will write the proposed changes to your local files'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            disabled={isSubmitting}
            className="text-[#6F7B77] hover:text-[#F2F6F4] p-1.5 rounded-lg hover:bg-white/6 transition-colors cursor-pointer shrink-0 disabled:opacity-40"
            title="Dismiss"
          >
            <X size={14} />
          </button>
        </div>

        {/* Plan summary (pre-execution) */}
        {isPreExecution && planSteps.length > 0 && (
          <div className="flex items-start gap-2 p-3 bg-white/[0.04] border border-white/8 rounded-xl">
            <ListChecks size={13} className="text-[#82B9FF] shrink-0 mt-0.5" />
            <p className="text-[11px] text-[#A3AEAA] leading-relaxed">
              {planSteps.length} stage{planSteps.length === 1 ? '' : 's'} planned:
              <span className="text-[#F2F6F4]">
                {' '}
                {planSteps.map((s) => s.label).join(' → ')}
              </span>
            </p>
          </div>
        )}

        {/* Files affected */}
        {files.length > 0 && (
          <div className="p-3.5 bg-[#0D1012] border border-white/8 rounded-2xl space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-[#6F7B77] pb-1.5 border-b border-white/6">
              <span>Target files ({files.length})</span>
              <div className="flex items-center gap-2">
                <span className="text-[#55E6A5] font-semibold">+{totalAdded}</span>
                <span className="text-[#FF7D7D] font-semibold">-{totalRemoved}</span>
              </div>
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
              {files.slice(0, 6).map((file) => (
                <div
                  key={file.path}
                  className="flex items-center justify-between font-mono text-[11px] py-1 px-1.5 rounded-md hover:bg-white/4"
                >
                  <div className="flex items-center gap-2 text-[#F2F6F4] truncate">
                    <FileCode size={12} className="text-[#82B9FF] shrink-0" />
                    <span className="truncate">{file.path}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 text-[10px]">
                    {file.status === 'created' && (
                      <span className="text-[#55E6A5] bg-[#15382C] px-1.5 py-0.5 rounded">new</span>
                    )}
                    <span className="text-[#55E6A5]">+{file.addedCount}</span>
                    <span className="text-[#FF7D7D]">-{file.removedCount}</span>
                  </div>
                </div>
              ))}
              {files.length > 6 && (
                <p className="text-[10px] font-mono text-[#6F7B77] px-1.5 pt-0.5">
                  +{files.length - 6} more file{files.length - 6 === 1 ? '' : 's'}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Safety notice (apply-changes) */}
        {!isPreExecution && (
          <div className="flex items-start gap-2 p-2.5 bg-[#141A1E] rounded-xl border border-white/8 text-[#A3AEAA]">
            <AlertCircle size={13} className="text-[#F4C76A] shrink-0 mt-0.5" />
            <span className="text-[10.5px] leading-relaxed">
              A git stash checkpoint is created automatically before modification.
            </span>
          </div>
        )}

        {/* Inline actions */}
        <div className="flex items-center gap-2 pt-1">
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={onApprove}
            disabled={isSubmitting}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#173D30] to-[#1F4E3E] hover:from-[#1F4E3E] hover:to-[#26624E] text-[#55E6A5] border border-[#2D9E70] rounded-xl text-xs font-semibold transition-all cursor-pointer shadow-lg glow-accent disabled:opacity-60"
          >
            {isSubmitting ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Check size={13} />
            )}
            <span>
              {isSubmitting
                ? 'Working…'
                : isPreExecution
                ? 'Approve & Execute'
                : 'Authorize & Apply'}
            </span>
          </motion.button>

          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={onReject}
            disabled={isSubmitting}
            className="flex items-center justify-center gap-1.5 px-4 py-2.5 bg-[#2A161A] hover:bg-[#341B20] text-[#FF7D7D] border border-[#FF7D7D]/35 rounded-xl text-xs font-semibold transition-all cursor-pointer shadow-md disabled:opacity-60"
          >
            <X size={13} />
            <span>{isPreExecution ? 'Reject Task' : 'Reject Changes'}</span>
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
};