import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { RoutingInfo } from '../types';
import { Cpu, ChevronDown, Zap, Coins, Clock, ShieldCheck, RefreshCw } from 'lucide-react';

interface RoutingExplanationProps {
  routing: RoutingInfo;
  defaultExpanded?: boolean;
}

export const RoutingExplanation: React.FC<RoutingExplanationProps> = ({
  routing,
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const getRoutingModeBadge = (mode: string) => {
    switch (mode) {
      case 'fast':
        return <span className="text-[#82B9FF] text-[10px] font-mono">Fast (Sub-second)</span>;
      case 'balanced':
        return <span className="text-[#93C5FD] text-[10px] font-mono">Balanced</span>;
      case 'quality':
        return <span className="text-[#F4C76A] text-[10px] font-mono">Quality (High Reasoning)</span>;
      default:
        return <span className="text-[#93C5FD] text-[10px] font-mono">Auto Router</span>;
    }
  };

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
            <Cpu size={12} />
          </div>
          <span className="font-semibold text-[#F2F6F4] text-xs">
            Model Routing: <span className="text-[#93C5FD] font-mono">{routing.model}</span>
          </span>
          <span className="text-[#6F7B77] text-[11px] hidden sm:inline">via {routing.provider}</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono tabular-nums text-[#A3AEAA]">
          <span className="flex items-center gap-1 text-[#6F7B77]">
            <Clock size={11} />
            {routing.latencyMs}ms
          </span>
          <span className="text-[#6F7B77]">·</span>
          <span className="flex items-center gap-1 text-[#F3F4F6] font-medium">
            <Coins size={11} />
            ${routing.actualCost.toFixed(4)}
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
            <div className="p-4 sm:p-5 bg-[#101417] border-t border-[rgba(255,255,255,0.06)] space-y-3.5">
              {/* Reason */}
              <div className="p-3 bg-[#0D1012] border border-[rgba(255,255,255,0.08)] rounded-xl text-[#A3AEAA] text-xs leading-relaxed shadow-xs">
                <span className="text-[#F2F6F4] font-semibold mr-1.5">Routing Decision:</span>
                {routing.reason}
              </div>

              {/* Key metrics grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 font-mono text-[11px]">
                <div className="p-3 bg-[#0D1012] border border-[rgba(255,255,255,0.08)] rounded-xl shadow-xs">
                  <div className="text-[10px] text-[#6F7B77] uppercase flex items-center gap-1.5">
                    <Zap size={11} className="text-[#82B9FF]" /> Mode
                  </div>
                  <div className="mt-1 text-[#F2F6F4] font-medium">
                    {getRoutingModeBadge(routing.routingMode)}
                  </div>
                </div>

                <div className="p-3 bg-[#0D1012] border border-[rgba(255,255,255,0.08)] rounded-xl shadow-xs">
                  <div className="text-[10px] text-[#6F7B77] uppercase flex items-center gap-1.5">
                    <Coins size={11} className="text-[#F4C76A]" /> Estimated Cost
                  </div>
                  <div className="mt-1 text-[#A3AEAA] tabular-nums font-semibold">
                    ${routing.estimatedCost.toFixed(4)}
                  </div>
                </div>

                <div className="p-3 bg-[#0D1012] border border-[rgba(255,255,255,0.08)] rounded-xl shadow-xs">
                  <div className="text-[10px] text-[#6F7B77] uppercase flex items-center gap-1.5">
                    <RefreshCw size={11} className="text-[#55E6A5]" /> Retries
                  </div>
                  <div className="mt-1 text-[#F2F6F4] tabular-nums font-semibold">
                    {routing.retryCount === 0 ? '0 (Clean pass)' : `${routing.retryCount} retried`}
                  </div>
                </div>

                <div className="p-3 bg-[#0D1012] border border-[rgba(255,255,255,0.08)] rounded-xl shadow-xs">
                  <div className="text-[10px] text-[#6F7B77] uppercase flex items-center gap-1.5">
                    <ShieldCheck size={11} className="text-[#55E6A5]" /> Fallback Status
                  </div>
                  <div className="mt-1 text-[#55E6A5] font-semibold">
                    {routing.fallbackStatus === 'nominal' ? 'Nominal' : 'Active Fallback'}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
