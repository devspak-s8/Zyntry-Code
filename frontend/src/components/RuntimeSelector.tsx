import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Terminal, ChevronDown, Check } from 'lucide-react';

interface RuntimeSelectorProps {
  runtime: string;
  onChange: (runtime: string) => void;
}

const RUNTIMES = [
  { id: 'node22', label: 'Node v22.14 LTS', desc: 'Default local node toolchain' },
  { id: 'bun12', label: 'Bun v1.2.4', desc: 'Fast native TypeScript engine' },
  { id: 'deno21', label: 'Deno v2.1.9', desc: 'Secure sandbox runtime' },
  { id: 'docker', label: 'Docker Sandbox', desc: 'Isolated container environment' },
];

export const RuntimeSelector: React.FC<RuntimeSelectorProps> = ({ runtime, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeRuntime = RUNTIMES.find((r) => r.label === runtime) || RUNTIMES[0];

  return (
    <div className="relative" ref={containerRef}>
      <motion.button
        type="button"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 bg-[#12161A] hover:bg-[#182025] border border-[rgba(255,255,255,0.1)] rounded-xl text-xs text-[#A3AEAA] hover:text-[#F2F6F4] transition-colors cursor-pointer shadow-xs"
        title="Active runtime environment"
      >
        <Terminal size={12} className="text-[#6F7B77]" />
        <span className="font-mono text-[11px] truncate max-w-[120px] font-medium">{activeRuntime.label}</span>
        <ChevronDown size={11} className={`text-[#6F7B77] transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            className="absolute left-0 mt-2 w-60 bg-[#161C20] border border-[rgba(255,255,255,0.16)] rounded-2xl shadow-2xl p-1.5 z-50 glow-card"
          >
            <div className="px-3 py-1.5 text-[10px] uppercase font-mono tracking-wider text-[#6F7B77] border-b border-[rgba(255,255,255,0.06)]">
              Execution Runtime
            </div>
            <div className="space-y-0.5 mt-1">
              {RUNTIMES.map((r) => {
                const isSelected = r.label === runtime;
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => {
                      onChange(r.label);
                      setIsOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 flex items-start gap-2.5 rounded-xl hover:bg-[#1D2428] transition-colors cursor-pointer"
                  >
                    <div className="mt-0.5 w-4 flex justify-center">
                      {isSelected && <Check size={13} className="text-[#55E6A5]" />}
                    </div>
                    <div className="flex-1">
                      <div className={`text-xs font-mono font-medium ${isSelected ? 'text-[#F2F6F4]' : 'text-[#A3AEAA]'}`}>
                        {r.label}
                      </div>
                      <div className="text-[10px] text-[#6F7B77] mt-0.5">{r.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
