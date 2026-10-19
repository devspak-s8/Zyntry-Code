import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { EvidencePackData, BlastRadiusRisk } from '../types';
import { 
  FileCheck2, 
  ChevronDown, 
  ShieldAlert, 
  CheckCircle2, 
  Cpu, 
  Coins, 
  FileCode, 
  Bug, 
  Scale, 
  AlertTriangle,
  Info
} from 'lucide-react';

interface EvidencePackProps {
  data: EvidencePackData;
  blastRadius?: BlastRadiusRisk;
  defaultExpanded?: boolean;
}

export const EvidencePack: React.FC<EvidencePackProps> = ({
  data,
  blastRadius,
  defaultExpanded = true,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [activeSubTab, setActiveSubTab] = useState<'overview' | 'blast_radius' | 'tests' | 'models'>('overview');

  const budgetUtilization = Math.min(100, Math.round((data.totalCost / data.taskBudget) * 100));

  return (
    <div className="bg-[#10161E] border border-white/12 rounded-2xl overflow-hidden text-xs shadow-xl">
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 sm:px-5 py-3.5 bg-[#141C26] hover:bg-[#182330] transition-colors cursor-pointer text-left border-b border-white/8"
      >
        <div className="flex items-center gap-2.5">
          <motion.div
            animate={{ rotate: isExpanded ? 0 : -90 }}
            transition={{ type: 'spring', stiffness: 350, damping: 25 }}
            className="text-[#6F7B77]"
          >
            <ChevronDown size={14} />
          </motion.div>
          <div className="w-5 h-5 rounded-lg bg-[#55E6A5]/15 border border-[#55E6A5]/30 flex items-center justify-center text-[#55E6A5]">
            <FileCheck2 size={13} />
          </div>
          <div>
            <div className="font-bold text-[#F3F4F6] text-xs sm:text-[13px] tracking-tight flex items-center gap-2">
              <span>Evidence Pack</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#55E6A5]/10 text-[#55E6A5] border border-[#55E6A5]/20 font-medium">
                Verified Proof
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-[11px] font-mono text-[#9CA3AF] tabular-nums hidden sm:flex items-center gap-1.5">
            <Coins size={12} className="text-[#93C5FD]" />
            <span className="text-white font-semibold">${data.totalCost.toFixed(4)}</span>
            <span className="text-[#6F7B77]">({budgetUtilization}% of budget)</span>
          </div>

          <span className="text-[10px] font-mono bg-white/5 border border-white/10 px-2 py-0.5 rounded text-[#93C5FD]">
            {data.attemptsCount} attempt
          </span>
        </div>
      </button>

      {/* Body */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="p-4 sm:p-5 space-y-4 bg-[#0E131A]"
          >
            {/* Nav pills for evidence sub-sections */}
            <div className="flex items-center gap-1.5 border-b border-white/8 pb-3 text-xs">
              <button
                type="button"
                onClick={() => setActiveSubTab('overview')}
                className={`px-3 py-1.5 rounded-xl font-medium transition-colors cursor-pointer ${
                  activeSubTab === 'overview'
                    ? 'bg-white/15 text-white border border-white/20'
                    : 'text-[#9CA3AF] hover:text-white hover:bg-white/5'
                }`}
              >
                Summary & Root Cause
              </button>
              <button
                type="button"
                onClick={() => setActiveSubTab('blast_radius')}
                className={`px-3 py-1.5 rounded-xl font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                  activeSubTab === 'blast_radius'
                    ? 'bg-white/15 text-white border border-white/20'
                    : 'text-[#9CA3AF] hover:text-white hover:bg-white/5'
                }`}
              >
                <span>Risk & Blast Radius</span>
                {blastRadius && (
                  <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 font-mono">
                    {blastRadius.level}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={() => setActiveSubTab('tests')}
                className={`px-3 py-1.5 rounded-xl font-medium transition-colors cursor-pointer ${
                  activeSubTab === 'tests'
                    ? 'bg-white/15 text-white border border-white/20'
                    : 'text-[#9CA3AF] hover:text-white hover:bg-white/5'
                }`}
              >
                Verifications ({data.testsPerformed.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveSubTab('models')}
                className={`px-3 py-1.5 rounded-xl font-medium transition-colors cursor-pointer ${
                  activeSubTab === 'models'
                    ? 'bg-white/15 text-white border border-white/20'
                    : 'text-[#9CA3AF] hover:text-white hover:bg-white/5'
                }`}
              >
                Models & Spend
              </button>
            </div>

            {/* TAB 1: OVERVIEW & ROOT CAUSE */}
            {activeSubTab === 'overview' && (
              <div className="space-y-3.5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* What Changed */}
                  <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/8 space-y-1.5">
                    <div className="text-[10px] font-mono text-[#93C5FD] uppercase tracking-wider font-semibold">
                      What Changed
                    </div>
                    <div className="text-[#F3F4F6] text-xs leading-relaxed font-sans">
                      {data.whatChanged}
                    </div>
                  </div>

                  {/* Why Changed */}
                  <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/8 space-y-1.5">
                    <div className="text-[10px] font-mono text-[#93C5FD] uppercase tracking-wider font-semibold">
                      Why It Changed
                    </div>
                    <div className="text-[#F3F4F6] text-xs leading-relaxed font-sans">
                      {data.whyChanged}
                    </div>
                  </div>
                </div>

                {/* Root Cause & Reproduce-Before-Fix */}
                {data.rootCause && (
                  <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/8 space-y-2">
                    <div className="flex items-center gap-2 text-xs font-semibold text-white">
                      <Bug size={13} className="text-amber-400" />
                      <span>Root Cause Analysis</span>
                    </div>
                    <div className="text-xs text-[#A3AEAA] font-mono leading-relaxed">
                      {data.rootCause}
                    </div>

                    {data.reproductionStep && (
                      <div className="pt-2 border-t border-white/6 flex items-center justify-between text-[11px] font-mono">
                        <div className="flex items-center gap-2 text-[#A3AEAA]">
                          <span className="text-[#6F7B77]">Reproduction:</span>
                          <span>{data.reproductionStep}</span>
                        </div>
                        {data.reproductionVerified && (
                          <span className="inline-flex items-center gap-1 text-[#55E6A5] font-medium shrink-0">
                            <CheckCircle2 size={12} />
                            <span>Reproduction Clean</span>
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Affected Files List */}
                <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/8 space-y-2">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-[#9CA3AF] font-mono uppercase tracking-wider text-[10px]">
                      Affected Files ({data.affectedFiles.length})
                    </span>
                    <span className="text-[10px] font-mono text-[#6F7B77]">AST Scoped</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {data.affectedFiles.map((file) => (
                      <span
                        key={file}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-black/40 border border-white/10 font-mono text-[11px] text-[#93C5FD]"
                      >
                        <FileCode size={11} />
                        <span>{file}</span>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Remaining Risk & Constitution Status */}
                <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]">
                  <div className="flex items-center gap-2 text-[#A3AEAA]">
                    <Info size={13} className="text-[#93C5FD] shrink-0" />
                    <span>Risk: {data.remainingRisk}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[#55E6A5] font-mono font-medium shrink-0">
                    <Scale size={12} />
                    <span>Project Constitution Satisfied</span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: BLAST RADIUS & RISK ANALYSIS */}
            {activeSubTab === 'blast_radius' && blastRadius && (
              <div className="space-y-3.5">
                <div className="p-4 rounded-xl bg-white/[0.03] border border-white/8 flex items-center justify-between gap-4">
                  <div>
                    <div className="text-xs font-semibold text-white flex items-center gap-2">
                      <ShieldAlert size={14} className="text-amber-400" />
                      <span>Blast Radius Score: {blastRadius.score}/100</span>
                    </div>
                    <p className="text-[11px] text-[#9CA3AF] mt-1 leading-snug">
                      Pre-execution risk triage evaluated sensitive boundaries before code mutation was initiated.
                    </p>
                  </div>
                  <div className="shrink-0 px-3 py-1 rounded-full text-xs font-mono font-bold uppercase bg-amber-500/15 text-amber-300 border border-amber-500/30">
                    {blastRadius.level} Risk
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-[10px] font-mono text-[#6F7B77] uppercase tracking-wider px-1">
                    Evaluated Subsystems
                  </div>
                  <div className="divide-y divide-white/6 rounded-xl bg-black/30 border border-white/8 overflow-hidden">
                    {blastRadius.affectedSubsystems.map((sub, i) => (
                      <div key={i} className="p-3 flex items-start justify-between gap-3 text-xs">
                        <div className="space-y-0.5">
                          <div className="font-medium text-white flex items-center gap-2">
                            <span>{sub.name}</span>
                            {sub.sensitive && (
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                Sensitive Area
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-[#9CA3AF] font-mono">
                            {sub.impact}
                          </div>
                        </div>
                        <span className="text-[10px] font-mono text-[#55E6A5] shrink-0 pt-0.5">
                          Guarded
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-white/[0.02] border border-white/6 text-[11px] text-[#9CA3AF] space-y-1">
                  <div className="font-medium text-white">Execution Safeguards Triggered:</div>
                  <ul className="list-disc pl-4 space-y-0.5 text-[10px]">
                    <li>Stronger reasoning model assigned for architecture decomposition.</li>
                    <li>Dedicated concurrency regression test suite required before disk write.</li>
                    <li>Human authorization enforced prior to working tree mutation.</li>
                  </ul>
                </div>
              </div>
            )}

            {/* TAB 3: DETERMINISTIC TESTS */}
            {activeSubTab === 'tests' && (
              <div className="space-y-2.5">
                <div className="text-[11px] text-[#9CA3AF]">
                  Deterministic verification suites executed against proposed patch:
                </div>
                <div className="divide-y divide-white/6 rounded-xl bg-black/30 border border-white/8 overflow-hidden">
                  {data.testsPerformed.map((test, idx) => (
                    <div key={idx} className="p-3 flex items-center justify-between gap-3 text-xs">
                      <div className="flex items-center gap-2.5">
                        <div className="w-4.5 h-4.5 rounded bg-[#55E6A5]/15 border border-[#55E6A5]/30 flex items-center justify-center text-[#55E6A5] shrink-0">
                          <CheckCircle2 size={12} />
                        </div>
                        <div>
                          <div className="font-medium text-white">{test.name}</div>
                          <div className="text-[11px] text-[#9CA3AF] font-mono">{test.detail}</div>
                        </div>
                      </div>
                      <span className="font-mono text-[10px] text-[#6F7B77] tabular-nums shrink-0">
                        {test.durationMs}ms
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 4: MODELS USED & SPEND */}
            {activeSubTab === 'models' && (
              <div className="space-y-3.5">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/8">
                    <div className="text-[10px] font-mono text-[#6F7B77]">Total Cost</div>
                    <div className="text-sm font-bold text-[#93C5FD] font-mono mt-1">
                      ${data.totalCost.toFixed(4)}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/8">
                    <div className="text-[10px] font-mono text-[#6F7B77]">Task Budget Cap</div>
                    <div className="text-sm font-bold text-white font-mono mt-1">
                      ${data.taskBudget.toFixed(4)}
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-white/[0.03] border border-white/8 col-span-2 sm:col-span-1">
                    <div className="text-[10px] font-mono text-[#6F7B77]">Budget Utilized</div>
                    <div className="text-sm font-bold text-[#55E6A5] font-mono mt-1">
                      {budgetUtilization}%
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-[10px] font-mono text-[#6F7B77] uppercase tracking-wider px-1">
                    Adaptive Intelligence Allocation
                  </div>
                  <div className="divide-y divide-white/6 rounded-xl bg-black/30 border border-white/8 overflow-hidden">
                    {data.modelsUsed.map((m, idx) => (
                      <div key={idx} className="p-3 flex items-center justify-between gap-3 text-xs">
                        <div className="flex items-center gap-2.5">
                          <Cpu size={13} className="text-[#93C5FD]" />
                          <div>
                            <div className="font-medium text-white">{m.stage}</div>
                            <div className="text-[11px] text-[#93C5FD] font-mono">{m.model}</div>
                          </div>
                        </div>
                        <div className="text-right font-mono text-[10px]">
                          <div className="text-white">${m.cost.toFixed(4)}</div>
                          <div className="text-[#6F7B77]">{m.tokensUsed} tokens</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
