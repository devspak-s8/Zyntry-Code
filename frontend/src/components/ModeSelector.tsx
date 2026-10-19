import React from 'react';
import { motion } from 'motion/react';
import { WorkspaceMode } from '../types';
import { HelpCircle, Edit3, Bot } from 'lucide-react';

interface ModeSelectorProps {
  mode: WorkspaceMode;
  onChange: (mode: WorkspaceMode) => void;
  disabled?: boolean;
}

export const ModeSelector: React.FC<ModeSelectorProps> = ({ mode, onChange, disabled }) => {
  const options: { id: WorkspaceMode; label: string; icon: React.ReactNode; tooltip: string }[] = [
    {
      id: 'ask',
      label: 'Ask',
      icon: <HelpCircle size={13} />,
      tooltip: 'Exploration & reasoning without modifying files',
    },
    {
      id: 'edit',
      label: 'Edit',
      icon: <Edit3 size={13} />,
      tooltip: 'Direct single-file targeted edits with instant diff',
    },
    {
      id: 'agent',
      label: 'Agent',
      icon: <Bot size={13} />,
      tooltip: 'Autonomous planning, tool execution, multi-file diffs & verification',
    },
  ];

  return (
    <div 
      role="group" 
      aria-label="Workspace mode"
      className="flex items-center p-1 bg-[#090C0E] border border-[rgba(255,255,255,0.08)] rounded-xl text-xs font-medium shadow-inner"
    >
      {options.map((opt) => {
        const isActive = mode === opt.id;
        return (
          <motion.button
            key={opt.id}
            type="button"
            whileHover={!isActive ? { scale: 1.02 } : {}}
            whileTap={{ scale: 0.96 }}
            onClick={() => !disabled && onChange(opt.id)}
            disabled={disabled}
            title={opt.tooltip}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all whitespace-nowrap cursor-pointer ${
              isActive
                ? 'bg-[#182026] text-[#F2F6F4] shadow-md border border-[rgba(255,255,255,0.14)] font-semibold'
                : 'text-[#A3AEAA] hover:text-[#F2F6F4] hover:bg-[#12161A] border border-transparent'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <span className={isActive ? 'text-[#55E6A5]' : 'text-[#6F7B77]'}>{opt.icon}</span>
            <span>{opt.label}</span>
          </motion.button>
        );
      })}
    </div>
  );
};
