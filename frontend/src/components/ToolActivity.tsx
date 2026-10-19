import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ToolActivityItem } from '../types';
import { Terminal, Check, Loader2, X, ChevronDown, FileCode, Search, CheckSquare, GitBranch } from 'lucide-react';

interface ToolActivityProps {
  activities: ToolActivityItem[];
  defaultExpanded?: boolean;
}

export const ToolActivity: React.FC<ToolActivityProps> = ({ activities, defaultExpanded = false }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  if (!activities || activities.length === 0) return null;

  const getToolIcon = (name: string) => {
    if (name.includes('Reading') || name.includes('view_file')) {
      return <FileCode size={13} className="text-[#82B9FF]" />;
    }
    if (name.includes('Searching') || name.includes('search')) {
      return <Search size={13} className="text-[#A3AEAA]" />;
    }
    if (name.includes('Running tests') || name.includes('checks') || name.includes('typecheck')) {
      return <CheckSquare size={13} className="text-[#55E6A5]" />;
    }
    if (name.includes('diff') || name.includes('git')) {
      return <GitBranch size={13} className="text-[#F4C76A]" />;
    }
    return <Terminal size={13} className="text-[#A3AEAA]" />;
  };

  const completedCount = activities.filter((a) => a.status === 'complete').length;

  return (
    <div className="bg-gradient-to-b from-[#111518] to-[#0D1012] border border-[rgba(255,255,255,0.08)] rounded-2xl overflow-hidden text-xs shadow-md">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-[#161C20]/50 transition-colors text-left cursor-pointer"
      >
        <div className="flex items-center gap-2.5">
          <motion.div
            animate={{ rotate: isExpanded ? 0 : -90 }}
            transition={{ type: 'spring', stiffness: 350, damping: 25 }}
            className="text-[#6F7B77]"
          >
            <ChevronDown size={13} />
          </motion.div>
          <div className="w-5 h-5 rounded-md bg-[#161C20] flex items-center justify-center text-[#6F7B77]">
            <Terminal size={12} />
          </div>
          <span className="font-mono text-[11px] text-[#A3AEAA]">
            Tool activity ({completedCount}/{activities.length} completed)
          </span>
        </div>
        <div className="text-[10px] font-mono text-[#93C5FD]">
          {isExpanded ? 'Collapse' : 'Expand'}
        </div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-4 py-3 space-y-2 border-t border-[rgba(255,255,255,0.06)] bg-[#090C0E]/70 font-mono text-[11px]">
              {activities.map((act) => (
                <div
                  key={act.id}
                  className="flex items-center justify-between gap-3 py-1.5 px-2 rounded-xl hover:bg-[#13171A] transition-colors text-[#A3AEAA]"
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <div className="w-4 flex justify-center shrink-0">
                      {act.status === 'running' && (
                        <Loader2 size={12} className="animate-spin text-[#82B9FF]" />
                      )}
                      {act.status === 'complete' && (
                        <Check size={12} className="text-[#55E6A5]" />
                      )}
                      {act.status === 'failed' && (
                        <X size={12} className="text-[#FF7D7D]" />
                      )}
                    </div>
                    <div className="w-5 h-5 rounded-md bg-[#12161A] flex items-center justify-center shrink-0">
                      {getToolIcon(act.name)}
                    </div>
                    <span className="truncate text-[#F2F6F4]">{act.name}</span>
                    {act.target && (
                      <span className="text-[#6F7B77] truncate text-[10px] bg-[#0A0D0E] px-1.5 py-0.5 rounded">
                        ({act.target})
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2.5 shrink-0 text-[#6F7B77] text-[10px]">
                    {act.durationMs && (
                      <span className="tabular-nums">{act.durationMs}ms</span>
                    )}
                    <span>{act.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
