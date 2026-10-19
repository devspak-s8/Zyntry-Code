import React from 'react';
import { AgentState, CheckStatus, StepStatus } from '../types';
import { 
  Circle, 
  Loader2, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ArrowUpRight, 
  ShieldAlert,
  Clock
} from 'lucide-react';

interface StatusBadgeProps {
  state?: AgentState;
  checkStatus?: CheckStatus;
  stepStatus?: StepStatus;
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  state,
  checkStatus,
  stepStatus,
  label,
  size = 'sm',
}) => {
  const iconSize = size === 'sm' ? 12 : 13;

  if (state) {
    switch (state) {
      case 'idle':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#A3AEAA]">
            <Circle size={iconSize} className="text-[#6F7B77]" />
            <span>{label || 'Idle'}</span>
          </span>
        );
      case 'planning':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#82B9FF]">
            <Loader2 size={iconSize} className="animate-spin text-[#82B9FF]" />
            <span>{label || 'Planning'}</span>
          </span>
        );
      case 'working':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#82B9FF]">
            <Loader2 size={iconSize} className="animate-spin text-[#82B9FF]" />
            <span>{label || 'Working'}</span>
          </span>
        );
      case 'awaiting_approval':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#F4C76A] font-medium">
            <AlertTriangle size={iconSize} className="text-[#F4C76A]" />
            <span>{label || 'Awaiting approval'}</span>
          </span>
        );
      case 'applying_changes':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#55E6A5] font-medium">
            <Loader2 size={iconSize} className="animate-spin text-[#55E6A5]" />
            <span>{label || 'Applying changes'}</span>
          </span>
        );
      case 'verifying':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#82B9FF]">
            <Loader2 size={iconSize} className="animate-spin text-[#82B9FF]" />
            <span>{label || 'Verifying'}</span>
          </span>
        );
      case 'complete':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#55E6A5] font-medium">
            <CheckCircle2 size={iconSize} className="text-[#55E6A5]" />
            <span>{label || 'Complete'}</span>
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#FF7D7D] font-medium">
            <XCircle size={iconSize} className="text-[#FF7D7D]" />
            <span>{label || 'Failed'}</span>
          </span>
        );
      case 'escalated':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#F4C76A] font-medium">
            <ArrowUpRight size={iconSize} className="text-[#F4C76A]" />
            <span>{label || 'Escalated'}</span>
          </span>
        );
    }
  }

  if (checkStatus) {
    switch (checkStatus) {
      case 'passed':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#55E6A5]">
            <CheckCircle2 size={iconSize} />
            <span>Passed</span>
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#FF7D7D] font-medium">
            <XCircle size={iconSize} />
            <span>Failed</span>
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#82B9FF]">
            <Loader2 size={iconSize} className="animate-spin" />
            <span>Running</span>
          </span>
        );
      case 'skipped':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#6F7B77]">
            <Clock size={iconSize} />
            <span>Skipped</span>
          </span>
        );
    }
  }

  if (stepStatus) {
    switch (stepStatus) {
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#6F7B77]">
            <Circle size={iconSize} className="text-[#6F7B77]" />
            <span>Pending</span>
          </span>
        );
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#82B9FF]">
            <Loader2 size={iconSize} className="animate-spin" />
            <span>Running</span>
          </span>
        );
      case 'complete':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#55E6A5]">
            <CheckCircle2 size={iconSize} />
            <span>Complete</span>
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs text-[#FF7D7D]">
            <XCircle size={iconSize} />
            <span>Failed</span>
          </span>
        );
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-[#A3AEAA]">
      <ShieldAlert size={iconSize} />
      <span>{label || 'Unknown'}</span>
    </span>
  );
};
