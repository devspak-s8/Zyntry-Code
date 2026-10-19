import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { RivetLogo } from './RivetLogo';

interface WorkspaceSetupLoaderProps {
  onFinished: () => void;
  repoName?: string;
  branch?: string;
}

const SETUP_MESSAGES = [
  'Setting up workspace...',
  'Analyzing repository AST...',
  'Mounting virtual diff tree...',
  'Checking project constitution...',
  'Ready',
];

export const WorkspaceSetupLoader: React.FC<WorkspaceSetupLoaderProps> = ({
  onFinished,
  repoName = 'zyntry-core-engine',
  branch = 'main',
}) => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  useEffect(() => {
    const messageTimings = [
      { delay: 1400, step: 1 },
      { delay: 2800, step: 2 },
      { delay: 4200, step: 3 },
      { delay: 5600, step: 4 },
      { delay: 7000, finish: true },
    ];

    const timeouts = messageTimings.map(({ delay, step, finish }) =>
      setTimeout(() => {
        if (step !== undefined) {
          setCurrentStepIndex(step);
        }
        if (finish) {
          onFinished();
        }
      }, delay)
    );

    return () => {
      timeouts.forEach(clearTimeout);
    };
  }, [onFinished]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="fixed inset-0 z-50 bg-[#0A0E13] text-[#F2F6F4] flex flex-col items-center justify-center p-6 select-none"
      style={{ userSelect: 'none', WebkitUserSelect: 'none' }}
      onCopy={(e) => e.preventDefault()}
      onCut={(e) => e.preventDefault()}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="flex flex-col items-center text-center space-y-7 max-w-sm">
        
        {/* Minimal Logo with calm, solid breathing animation (No gradients) */}
        <motion.div
          animate={{ 
            opacity: [0.75, 1, 0.75],
            scale: [0.97, 1.03, 0.97]
          }}
          transition={{ 
            duration: 2.8, 
            repeat: Infinity,
            ease: 'easeInOut' 
          }}
        >
          <RivetLogo size="lg" />
        </motion.div>

        {/* Sequential Fading Status Text (one after the other with AnimatePresence) */}
        <div className="h-7 flex items-center justify-center">
          <AnimatePresence mode="wait">
            <motion.p
              key={SETUP_MESSAGES[currentStepIndex]}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.45, ease: 'easeInOut' }}
              className="text-sm font-mono text-[#F3F4F6] tracking-tight"
            >
              {SETUP_MESSAGES[currentStepIndex]}
            </motion.p>
          </AnimatePresence>
        </div>

        {/* Minimal Subtle Context Info */}
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#6F7B77]">
          <span>{repoName}</span>
          <span className="text-white/20">/</span>
          <span>{branch}</span>
        </div>

      </div>
    </motion.div>
  );
};
