import React, { useState } from 'react';
import { motion } from 'motion/react';
import { ConstitutionRule, EngineeringMemoryItem, RuntimeIncidentSignal } from '../types';
import { 
  MOCK_CONSTITUTION_RULES, 
  MOCK_ENGINEERING_MEMORY, 
  MOCK_INCIDENT_SIGNALS 
} from '../data/mockData';
import { 
  Scale, 
  ShieldCheck, 
  BrainCircuit, 
  Radio, 
  CheckCircle2, 
  FileCode, 
  Lock
} from 'lucide-react';

export const ConstitutionView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'rules' | 'memory' | 'incidents'>('rules');
  const [rules] = useState<ConstitutionRule[]>(MOCK_CONSTITUTION_RULES);
  const [memories] = useState<EngineeringMemoryItem[]>(MOCK_ENGINEERING_MEMORY);
  const [incidents] = useState<RuntimeIncidentSignal[]>(MOCK_INCIDENT_SIGNALS);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="px-6 sm:px-10 md:px-16 lg:px-20 xl:px-24 py-8 sm:py-10 space-y-8 sm:space-y-10 w-full pb-28"
    >
      {/* Title & Mode Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-white/8">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center text-[#55E6A5] shadow-inner">
              <Scale size={18} />
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-[#F2F6F4] tracking-tight flex items-center gap-2.5">
                <span>Project Constitution & Guardrails</span>
                <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#55E6A5]/10 text-[#55E6A5] border border-[#55E6A5]/25 font-medium">
                  5/5 Verified
                </span>
              </h2>
            </div>
          </div>
          <p className="text-xs sm:text-[13px] text-[#A3AEAA] max-w-2xl leading-relaxed">
            Architectural invariants, engineering memory, security boundaries, and runtime incident telemetry guarded before code changes touch the disk.
          </p>
        </div>

        {/* Bubbly Tab Switcher Pill */}
        <div className="flex items-center gap-1.5 p-1.5 bg-[#141B24] border border-white/12 rounded-full self-start md:self-center shadow-lg">
          <button
            type="button"
            onClick={() => setActiveTab('rules')}
            className={`px-4 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'rules'
                ? 'bg-white text-zinc-950 shadow-md font-bold'
                : 'text-[#9CA3AF] hover:text-white'
            }`}
          >
            Engineering Rules
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('memory')}
            className={`px-4 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'memory'
                ? 'bg-white text-zinc-950 shadow-md font-bold'
                : 'text-[#9CA3AF] hover:text-white'
            }`}
          >
            Engineering Memory
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('incidents')}
            className={`px-4 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer ${
              activeTab === 'incidents'
                ? 'bg-white text-zinc-950 shadow-md font-bold'
                : 'text-[#9CA3AF] hover:text-white'
            }`}
          >
            Incident Signals
          </button>
        </div>
      </div>

      {/* TAB 1: RULES & ARCHITECTURE GUARD */}
      {activeTab === 'rules' && (
        <div className="space-y-7">
          {/* Card Overview */}
          <div className="p-6 sm:p-7 rounded-[28px] sm:rounded-[32px] bg-[#121821]/95 hover:bg-[#141C27] border border-white/10 hover:border-white/16 shadow-2xl backdrop-blur-xl transition-all space-y-3.5">
            <div className="flex items-center justify-between border-b border-white/6 pb-3.5">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-xl bg-[#55E6A5]/15 border border-[#55E6A5]/30 flex items-center justify-center text-[#55E6A5]">
                  <ShieldCheck size={14} />
                </div>
                <span className="font-bold text-white text-xs sm:text-sm tracking-tight">
                  Architecture Guard & Invariant Policy
                </span>
              </div>
              <span className="text-[10px] font-mono text-[#55E6A5] bg-[#55E6A5]/10 px-2.5 py-0.5 rounded-full">
                100% Passing
              </span>
            </div>
            <p className="text-xs sm:text-[13px] text-[#A3AEAA] leading-relaxed font-sans">
              Zyntry Code checks every generated patch against team-defined rules to detect broken module boundaries, circular dependencies, leaking secrets, or direct database query violations before writing to disk.
            </p>
          </div>

          {/* Rules List - Bubbly Cards */}
          <div className="space-y-3.5">
            <div className="text-[10px] font-mono text-[#6F7B77] uppercase tracking-wider px-1">
              Active Team Constitution Rules ({rules.length})
            </div>

            <div className="grid grid-cols-1 gap-3.5">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="p-5 rounded-[24px] bg-[#121821]/90 hover:bg-[#141C27] border border-white/8 hover:border-white/16 transition-all flex flex-col sm:flex-row sm:items-start justify-between gap-4 text-xs shadow-md"
                >
                  <div className="flex items-start gap-3.5">
                    <div className="mt-0.5 w-6 h-6 rounded-xl bg-[#55E6A5]/15 border border-[#55E6A5]/30 flex items-center justify-center text-[#55E6A5] shrink-0">
                      <CheckCircle2 size={13} />
                    </div>
                    <div className="space-y-1.5">
                      <div className="font-semibold text-white text-xs sm:text-[13px] flex items-center gap-2.5 flex-wrap">
                        <span>{rule.rule}</span>
                        <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-white/6 border border-white/10 text-[#93C5FD] uppercase">
                          {rule.category}
                        </span>
                      </div>
                      <div className="text-[11px] text-[#A3AEAA] font-mono leading-relaxed">
                        {rule.detail}
                      </div>
                    </div>
                  </div>

                  <span className="text-[10px] font-mono text-[#55E6A5] shrink-0 self-start sm:self-center bg-[#55E6A5]/10 px-2.5 py-1 rounded-full border border-[#55E6A5]/20 font-medium">
                    Enforced
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: ENGINEERING MEMORY */}
      {activeTab === 'memory' && (
        <div className="space-y-7">
          <div className="p-6 sm:p-7 rounded-[28px] sm:rounded-[32px] bg-[#121821]/95 hover:bg-[#141C27] border border-white/10 hover:border-white/16 shadow-2xl backdrop-blur-xl transition-all space-y-3.5">
            <div className="flex items-center justify-between border-b border-white/6 pb-3.5">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-xl bg-[#93C5FD]/15 border border-[#93C5FD]/30 flex items-center justify-center text-[#93C5FD]">
                  <BrainCircuit size={14} />
                </div>
                <span className="font-bold text-white text-xs sm:text-sm tracking-tight">
                  Engineering Memory Subsystem
                </span>
              </div>
              <span className="text-[10px] font-mono text-[#6F7B77]">Persisted Invariants</span>
            </div>
            <p className="text-xs sm:text-[13px] text-[#A3AEAA] leading-relaxed font-sans">
              Zyntry Code remembers important technical decisions rather than raw conversation text. Constraints, trade-offs, and architecture decisions are preserved across sessions.
            </p>
          </div>

          <div className="space-y-3.5">
            <div className="text-[10px] font-mono text-[#6F7B77] uppercase tracking-wider px-1">
              Recorded Architectural Decisions ({memories.length})
            </div>

            <div className="grid grid-cols-1 gap-4">
              {memories.map((mem) => (
                <div
                  key={mem.id}
                  className="p-5 sm:p-6 rounded-[26px] bg-[#121821]/90 hover:bg-[#141C27] border border-white/8 hover:border-white/16 space-y-3 transition-all shadow-md"
                >
                  <div className="flex items-center justify-between">
                    <div className="font-bold text-white text-xs sm:text-sm flex items-center gap-2">
                      <Lock size={12} className="text-[#93C5FD]" />
                      <span>{mem.title}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] font-mono text-[#6F7B77]">
                      <span>{mem.subsystem}</span>
                      <span>·</span>
                      <span>{mem.date}</span>
                    </div>
                  </div>

                  <div className="p-3.5 bg-black/40 border border-white/8 rounded-2xl font-mono text-[11px] text-[#F3F4F6] leading-relaxed">
                    Decision: {mem.decision}
                  </div>

                  <div className="text-[11px] text-[#A3AEAA] font-mono">
                    Context: {mem.context}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: RUNTIME INCIDENT SIGNALS */}
      {activeTab === 'incidents' && (
        <div className="space-y-7">
          <div className="p-6 sm:p-7 rounded-[28px] sm:rounded-[32px] bg-[#121821]/95 hover:bg-[#141C27] border border-white/10 hover:border-white/16 shadow-2xl backdrop-blur-xl transition-all space-y-3.5">
            <div className="flex items-center justify-between border-b border-white/6 pb-3.5">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-xl bg-[#93C5FD]/15 border border-[#93C5FD]/30 flex items-center justify-center text-[#93C5FD]">
                  <Radio size={14} />
                </div>
                <span className="font-bold text-white text-xs sm:text-sm tracking-tight">
                  Runtime Telemetry & Incident Debugging
                </span>
              </div>
              <span className="text-[10px] font-mono text-amber-400 bg-amber-400/10 px-2.5 py-0.5 rounded-full border border-amber-400/20 font-medium">
                Connected
              </span>
            </div>
            <p className="text-xs sm:text-[13px] text-[#A3AEAA] leading-relaxed font-sans">
              Connect logs, Sentry, CI failures, deployment events, and OpenTelemetry. Say &quot;fix the production error&quot; and Zyntry Code correlates the incident with the relevant code and deployment.
            </p>
          </div>

          <div className="space-y-3.5">
            <div className="text-[10px] font-mono text-[#6F7B77] uppercase tracking-wider px-1">
              Live Incident Signals ({incidents.length})
            </div>

            <div className="grid grid-cols-1 gap-4">
              {incidents.map((inc) => (
                <div
                  key={inc.id}
                  className="p-5 sm:p-6 rounded-[26px] bg-[#121821]/90 hover:bg-[#141C27] border border-white/8 hover:border-white/16 space-y-3 transition-all shadow-md"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="font-bold text-white text-xs sm:text-sm flex items-center gap-2.5">
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/30">
                        {inc.source}
                      </span>
                      <span>{inc.title}</span>
                    </div>
                    <span className="text-[10px] font-mono text-[#6F7B77]">
                      {inc.timestamp}
                    </span>
                  </div>

                  <div className="p-3.5 bg-black/40 border border-white/8 rounded-2xl font-mono text-[11px] text-[#FF7D7D] leading-relaxed">
                    {inc.stackSummary}
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-mono pt-1 text-[#6F7B77]">
                    <div className="flex items-center gap-1.5 text-[#93C5FD]">
                      <FileCode size={12} />
                      <span>{inc.correlatedFile}</span>
                    </div>
                    {inc.traceId && (
                      <span className="text-[10px] text-[#6F7B77] truncate max-w-[200px]">
                        Trace: {inc.traceId}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
};
