import React from 'react';
import { motion } from 'motion/react';
import { RivetLogo } from './RivetLogo';

interface EmptyStateProps {
  onSelectPrompt?: (promptText: string) => void;
  onStartOnboarding?: () => void;
  repoName?: string;
  branch?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = () => {
  return (
    <div className="min-h-full flex flex-col items-center justify-center p-6 sm:p-10 pb-40 sm:pb-48 text-center max-w-2xl mx-auto w-full">
      {/* Icon Glyph */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        className="mb-4"
      >
        <RivetLogo size="lg" />
      </motion.div>

      {/* Main heading */}
      <h1 className="text-xl sm:text-2xl font-bold text-[#F2F6F4] tracking-tight mb-2">
        Zyntry Code Engineering Agent
      </h1>

      {/* Supporting text */}
      <p className="text-xs sm:text-sm text-[#A3AEAA] max-w-lg mb-8 leading-relaxed">
        Understand codebase relationships, decompose stages, route models adaptively, and verify deterministically before writing to disk.
      </p>
    </div>
  );
};
