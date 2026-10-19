import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { DiffFile } from '../types';
import { 
  FileCode, 
  Copy, 
  Check, 
  ExternalLink, 
  CheckCircle2, 
  XCircle, 
  Files
} from 'lucide-react';

interface DiffReviewProps {
  files: DiffFile[];
  onApplyChanges: () => void;
  onRejectChanges: () => void;
  isApplied?: boolean;
}

export const DiffReview: React.FC<DiffReviewProps> = ({
  files,
  onApplyChanges,
  onRejectChanges,
  isApplied = false,
}) => {
  const [selectedFileIndex, setSelectedFileIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const [openedFileNotice, setOpenedFileNotice] = useState<string | null>(null);

  if (!files || files.length === 0) {
    return (
      <div className="p-8 text-center bg-[#111518] border border-[rgba(255,255,255,0.08)] rounded-2xl text-[#6F7B77] text-xs">
        No active diffs proposed for this task.
      </div>
    );
  }

  const activeFile = files[selectedFileIndex] || files[0];
  const totalAdded = files.reduce((acc, f) => acc + f.addedCount, 0);
  const totalRemoved = files.reduce((acc, f) => acc + f.removedCount, 0);

  const handleCopyDiff = () => {
    let fullDiff = '';
    files.forEach((f) => {
      fullDiff += `--- a/${f.path}\n+++ b/${f.path}\n`;
      f.hunks.forEach((h) => {
        fullDiff += `@@ -${h.oldStart},${h.oldLines} +${h.newStart},${h.newLines} @@\n`;
        h.lines.forEach((l) => {
          const prefix = l.type === 'add' ? '+' : l.type === 'remove' ? '-' : ' ';
          fullDiff += `${prefix}${l.text}\n`;
        });
      });
      fullDiff += '\n';
    });

    navigator.clipboard.writeText(fullDiff);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleOpenFile = (path: string) => {
    setOpenedFileNotice(`Active editor focused on ${path}`);
    setTimeout(() => setOpenedFileNotice(null), 3000);
  };

  return (
    <div className="bg-[#121820]/95 border border-white/10 rounded-[24px] sm:rounded-[28px] overflow-hidden text-xs flex flex-col shadow-2xl backdrop-blur-xl">
      {/* Top Header */}
      <div className="px-4 sm:px-5 py-3.5 bg-[#141C25] border-b border-white/8 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-semibold text-[#F2F6F4]">
            <div className="w-5 h-5 rounded-full bg-white/10 border border-white/15 flex items-center justify-center text-white">
              <Files size={12} />
            </div>
            <span>Proposed Changes</span>
          </div>

          <div className="flex items-center gap-2 font-mono text-[11px] tabular-nums text-[#A3AEAA]">
            <span>{files.length} {files.length === 1 ? 'file' : 'files'}</span>
            <span>·</span>
            <span className="text-emerald-400 font-semibold">+{totalAdded}</span>
            <span className="text-[#FF7D7D] font-semibold">-{totalRemoved}</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {openedFileNotice && (
            <motion.span
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-[11px] font-mono text-[#93C5FD] bg-white/10 px-2.5 py-1 rounded-full border border-white/10"
            >
              {openedFileNotice}
            </motion.span>
          )}

          <motion.button
            type="button"
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={handleCopyDiff}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/6 hover:bg-white/10 text-[#A3AEAA] hover:text-[#F2F6F4] border border-white/10 rounded-full text-xs transition-colors cursor-pointer shadow-xs"
            title="Copy patch to clipboard"
          >
            {copied ? <Check size={12} className="text-[#93C5FD]" /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy diff'}</span>
          </motion.button>

          <motion.button
            type="button"
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => handleOpenFile(activeFile.path)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/6 hover:bg-white/10 text-[#A3AEAA] hover:text-[#F2F6F4] border border-white/10 rounded-full text-xs transition-colors cursor-pointer shadow-xs"
            title="Open file in editor"
          >
            <ExternalLink size={12} />
            <span>Open file</span>
          </motion.button>

          {!isApplied ? (
            <>
              <motion.button
                type="button"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                onClick={onRejectChanges}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2A161A] hover:bg-[#341B20] text-[#FF7D7D] border border-[#FF7D7D]/35 rounded-full text-xs transition-colors cursor-pointer shadow-xs"
              >
                <XCircle size={12} />
                <span>Reject</span>
              </motion.button>

              <motion.button
                type="button"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                onClick={onApplyChanges}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-white text-zinc-900 hover:bg-zinc-200 border border-white/30 rounded-full text-xs font-semibold transition-all cursor-pointer shadow-md active:scale-95"
              >
                <CheckCircle2 size={13} />
                <span>Apply changes</span>
              </motion.button>
            </>
          ) : (
            <span className="flex items-center gap-1.5 px-4 py-1.5 bg-white/10 text-white/90 border border-white/15 rounded-full text-xs font-semibold shadow-xs">
              <CheckCircle2 size={13} className="text-[#93C5FD]" />
              <span>Applied to workspace</span>
            </span>
          )}
        </div>
      </div>

      {/* File selector tabs across the top */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#0F141A] border-b border-white/6 overflow-x-auto">
        <span className="text-[10px] font-mono text-[#6F7B77] uppercase tracking-wider px-1 shrink-0">
          Files:
        </span>
        {files.map((file, idx) => {
          const isSelected = idx === selectedFileIndex;
          return (
            <button
              key={file.path}
              type="button"
              onClick={() => setSelectedFileIndex(idx)}
              className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono transition-all shrink-0 cursor-pointer ${
                isSelected
                  ? 'bg-white/10 text-[#F2F6F4] font-medium border border-white/15 shadow-sm'
                  : 'text-[#A3AEAA] hover:text-[#F2F6F4] hover:bg-white/5 border border-transparent'
              }`}
            >
              <FileCode size={12} className={isSelected ? 'text-[#93C5FD]' : 'text-[#6F7B77]'} />
              <span>{file.path.split('/').pop()}</span>
              <div className="flex items-center gap-1 text-[10px] tabular-nums font-mono">
                <span className="text-emerald-400 font-semibold">+{file.addedCount}</span>
                <span className="text-[#FF7D7D] font-semibold">-{file.removedCount}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Unified diff code viewer */}
      <div className="w-full overflow-x-auto bg-[#0C1014] font-mono text-[11px] leading-relaxed">
        {/* File path sub-bar */}
        <div className="px-4 py-2 bg-[#10151B] border-b border-white/6 text-[#A3AEAA] text-[11px] flex items-center justify-between">
          <span className="text-[#F2F6F4] font-medium">{activeFile.path}</span>
          <span className="text-[#6F7B77] text-[10px] uppercase font-semibold">
            {activeFile.status === 'created' ? 'New file' : 'Modified'}
          </span>
        </div>

        <div className="py-3">
          {activeFile.hunks.map((hunk, hIdx) => (
            <div key={hIdx} className="mb-3">
              {/* Hunk Header */}
              <div className="px-4 py-1 text-[#93C5FD]/80 bg-[#141A22] text-[10px] border-y border-white/6 font-mono">
                @@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines} @@
              </div>

              {/* Diff Lines */}
              {hunk.lines.map((line, lIdx) => {
                const isAdd = line.type === 'add';
                const isRemove = line.type === 'remove';

                return (
                  <div
                    key={lIdx}
                    className={`flex items-start px-3 py-1 transition-colors ${
                      isAdd
                        ? 'bg-emerald-500/10 text-emerald-300'
                        : isRemove
                        ? 'bg-rose-500/10 text-rose-300'
                        : 'text-[#A3AEAA] hover:bg-white/3'
                    }`}
                  >
                    {/* Line Numbers */}
                    <span className="w-9 shrink-0 text-right pr-2 select-none text-[#6F7B77] text-[10px] tabular-nums">
                      {line.oldLineNumber || ''}
                    </span>
                    <span className="w-9 shrink-0 text-right pr-3 select-none text-[#6F7B77] text-[10px] tabular-nums">
                      {line.newLineNumber || ''}
                    </span>

                    {/* Prefix */}
                    <span className="w-4 shrink-0 select-none font-semibold">
                      {isAdd ? '+' : isRemove ? '-' : ' '}
                    </span>

                    {/* Line Text */}
                    <span className="flex-1 whitespace-pre break-all font-mono">
                      {line.text}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
