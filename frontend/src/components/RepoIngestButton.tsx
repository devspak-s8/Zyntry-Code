import React, { useState } from 'react';
import { motion } from 'motion/react';
import { FolderInput, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../api/client';
import { openDirectoryPicker, walkRepoFiles } from '../api/repoWalk';

interface RepoIngestButtonProps {
  taskId: string;
  compact?: boolean;
}

export const RepoIngestButton: React.FC<RepoIngestButtonProps> = ({ taskId, compact = false }) => {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  const ingest = async () => {
    setBusy(true);
    setResult(null);
    try {
      const files = await openDirectoryPicker();
      const walked = await walkRepoFiles(files);
      if (walked.length === 0) {
        setResult({ ok: false, text: 'No indexable files found (skipped node_modules/.git/…)' });
        return;
      }
      const resp = await api.ingestRepo(taskId, walked);
      setResult({ ok: true, text: `Ingested ${resp.files_ingested} files` });
    } catch (err) {
      setResult({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <motion.button
        whileHover={{ scale: 1.03 }}
        whileTap={{ scale: 0.97 }}
        onClick={ingest}
        disabled={busy}
        title="Pick a folder — its files become the repo snapshot (repo_files) used for planning, the semantic index, and workspace prompts."
        className={`flex items-center gap-2 ${
          compact ? 'px-3 py-1.5' : 'px-4 py-2'
        } rounded-full bg-[#121820]/95 hover:bg-[#151D28] border border-white/10 hover:border-[#82B9FF]/40 text-[#F2F6F4] text-xs font-medium cursor-pointer disabled:opacity-50 shadow-lg backdrop-blur-xl`}
      >
        {busy ? (
          <Loader2 size={13} className="animate-spin text-[#82B9FF]" />
        ) : (
          <FolderInput size={13} className="text-[#82B9FF]" />
        )}
        <span>{busy ? 'Ingesting…' : 'Ingest repo'}</span>
      </motion.button>
      {result && (
        <span
          className={`flex items-center gap-1 text-[11px] font-mono ${
            result.ok ? 'text-[#55E6A5]' : 'text-[#F87171]'
          }`}
        >
          {result.ok ? <CheckCircle2 size={11} /> : <AlertCircle size={11} />}
          {result.text}
        </span>
      )}
    </div>
  );
};