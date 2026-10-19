import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { VerificationCheck } from '../types';
import { StatusBadge } from './StatusBadge';
import { 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  ArrowUpRight, 
  ChevronDown, 
  FileCode, 
  Lightbulb, 
  Shield
} from 'lucide-react';

interface VerificationPanelProps {
  checks: VerificationCheck[];
  onRetry?: () => void;
  onEscalate?: () => void;
  defaultExpanded?: boolean;
}

export const VerificationPanel: React.FC<VerificationPanelProps> = ({
  checks,
  onRetry,
  onEscalate,
  defaultExpanded = true,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!checks || checks.length === 0) return null;

  const passedCount = checks.filter((c) => c.status === 'passed').length;
  const failedCheck = checks.find((c) => c.status === 'failed');
  const isAllPassed = passedCount === checks.length;

  return (
    <div className={`border rounded-[24px] sm:rounded-[28px] overflow-hidden text-xs shadow-2xl backdrop-blur-xl transition-all ${
      failedCheck 
        ? 'bg-[#160E12] border-[#FF7D7D]/35' 
        : 'bg-[#121820]/95 border-white/10'
    }`}>
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 sm:px-5 py-3.5 bg-[#141C25] hover:bg-[#18222D] transition-colors cursor-pointer text-left"
      >
        <div className="flex items-center gap-2.5">
          <motion.div
            animate={{ rotate: isExpanded ? 0 : -90 }}
            transition={{ type: 'spring', stiffness: 350, damping: 25 }}
            className="text-[#6F7B77]"
          >
            <ChevronDown size={14} />
          </motion.div>
          <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
            failedCheck 
              ? 'bg-[#2A1518] text-[#FF7D7D] border border-[#FF7D7D]/40' 
              : 'bg-white/10 text-white border-white/15'
          }`}>
            {failedCheck ? <AlertTriangle size={12} /> : <Shield size={12} />}
          </div>
          <span className="font-semibold text-[#F2F6F4] text-xs">Verification Suite</span>
          <span className="text-[#6F7B77] font-mono text-[11px] tabular-nums">
            ({passedCount}/{checks.length} passed)
          </span>
        </div>

        <div>
          {failedCheck ? (
            <span className="text-[#FF7D7D] font-mono text-[11px] font-semibold flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#2A1518] border border-[#FF7D7D]/30">
              Checks Failed
            </span>
          ) : isAllPassed ? (
            <span className="text-[#93C5FD] font-mono text-[11px] flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/6 border border-white/10 font-medium">
              <CheckCircle2 size={11} /> All Checks Verified
            </span>
          ) : (
            <span className="text-[#82B9FF] font-mono text-[11px] px-3 py-1 rounded-full bg-white/6 border border-white/10">
              Running Checks...
            </span>
          )}
        </div>
      </button>

      {/* Expanded view */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="p-4 sm:p-5 space-y-4 bg-[#0F141A]">
              {/* Checks list */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {checks.map((check) => (
                  <motion.div
                    key={check.id}
                    whileHover={{ y: -1 }}
                    className="p-3.5 bg-[#121820] border border-white/8 hover:border-white/16 rounded-2xl flex items-center justify-between gap-3 shadow-xs transition-all"
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <span className="text-[#F2F6F4] font-medium truncate text-xs">{check.name}</span>
                      {check.command && (
                        <span className="font-mono text-[10px] text-[#6F7B77] truncate bg-black/40 px-2 py-0.5 rounded-md">
                          `{check.command}`
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {check.durationMs && (
                        <span className="font-mono text-[10px] text-[#6F7B77] tabular-nums">
                          {check.durationMs}ms
                        </span>
                      )}
                      <StatusBadge checkStatus={check.status} />
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* If failed, show failure details & action buttons */}
              {failedCheck && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="p-4 sm:p-5 bg-[#1C1216] border border-[#FF7D7D]/35 rounded-[22px] space-y-3.5 shadow-lg"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-[#33161A] flex items-center justify-center text-[#FF7D7D] shrink-0 mt-0.5">
                      <AlertTriangle size={13} />
                    </div>
                    <div className="flex-1 space-y-1.5">
                      <div className="text-[#FF7D7D] font-semibold text-xs">
                        Verification Failure in {failedCheck.name}
                      </div>
                      {failedCheck.summary && (
                        <div className="font-mono text-[11px] text-[#F2F6F4] bg-[#0E0B0D] p-3.5 rounded-xl border border-[#FF7D7D]/20 leading-relaxed">
                          {failedCheck.summary}
                        </div>
                      )}
                    </div>
                  </div>

                  {failedCheck.file && (
                    <div className="flex items-center gap-2 text-[11px] text-[#A3AEAA] font-mono pl-7">
                      <FileCode size={12} className="text-[#6F7B77]" />
                      <span>Relevant file:</span>
                      <span className="text-[#F2F6F4] bg-[#110E10] px-2 py-0.5 rounded-lg border border-[rgba(255,255,255,0.08)]">
                        {failedCheck.file}
                      </span>
                    </div>
                  )}

                  {failedCheck.suggestion && (
                    <div className="flex items-start gap-2 text-[11px] text-[#A3AEAA] pl-7">
                      <Lightbulb size={13} className="text-[#F4C76A] shrink-0 mt-0.5" />
                      <span>
                        <strong className="text-[#F2F6F4]">Suggested next action:</strong>{' '}
                        {failedCheck.suggestion}
                      </span>
                    </div>
                  )}

                  {/* Action buttons */}
                  <div className="pt-2 pl-7 flex flex-wrap items-center gap-2.5">
                    <motion.button
                      type="button"
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={onRetry}
                      className="flex items-center gap-1.5 px-3.5 py-2 bg-[#171C20] hover:bg-[#1F252B] text-[#F2F6F4] border border-[rgba(255,255,255,0.16)] rounded-xl text-xs font-medium transition-all cursor-pointer shadow-md"
                    >
                      <RefreshCw size={12} className="text-[#82B9FF]" />
                      <span>Retry verification</span>
                    </motion.button>

                    <motion.button
                      type="button"
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={onEscalate}
                      className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-[#173D30] to-[#1F4E3E] hover:from-[#1F4E3E] hover:to-[#26624E] text-[#55E6A5] border border-[#2D9E70] rounded-xl text-xs font-semibold transition-all cursor-pointer shadow-lg glow-accent"
                    >
                      <ArrowUpRight size={13} className="text-[#55E6A5]" />
                      <span>Escalate to stronger model</span>
                    </motion.button>
                  </div>
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
