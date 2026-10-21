import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { KeyRound, X, Check, Trash2 } from 'lucide-react';
import { getProviderConfig, setProviderConfig, providerHeaders } from '../api/client';

interface ProviderOption {
  id: string;
  label: string;
  desc: string;
}

const PROVIDERS: ProviderOption[] = [
  { id: 'openai', label: 'OpenAI', desc: 'Unlocks GPT-5, GPT-4.1, o3-mini and more' },
  { id: 'openrouter', label: 'OpenRouter', desc: 'Hundreds of models, one key' },
  { id: 'anthropic', label: 'Anthropic', desc: 'Unlocks Claude Sonnet & more' },
];

interface ProviderModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * "Add an AI provider" modal. Accepts the caller's own provider API key,
 * stored only in this browser's localStorage and attached to task requests
 * as HTTPS headers. Nothing is saved server-side.
 */
export const ProviderModal: React.FC<ProviderModalProps> = ({ isOpen, onClose }) => {
  const [provider, setProvider] = useState<string>('openai');
  const [key, setKey] = useState('');
  const [base, setBase] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const cfg = getProviderConfig();
    setProvider(cfg?.provider ?? 'openai');
    setKey(cfg?.key ?? '');
    const presetBase = cfg?.provider === 'openrouter' ? 'https://openrouter.ai/api/v1' : (cfg?.base ?? '');
    setBase(presetBase);
    setSaved(false);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleProviderChange = (id: string) => {
    setProvider(id);
    setBase(id === 'openrouter' ? 'https://openrouter.ai/api/v1' : '');
  };

  const handleSave = () => {
    const trimmedKey = key.trim();
    if (!trimmedKey) return;
    const isCustomBase = base.trim() && provider === 'openai';
    setProviderConfig({
      provider,
      key: trimmedKey,
      ...(isCustomBase ? { base: base.trim() } : {}),
    });
    setSaved(true);
    onClose();
  };

  const handleRemove = () => {
    setProviderConfig(null);
    setKey('');
    setSaved(false);
    onClose();
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
        onClick={() => onClose()}
      >
        <motion.div
          initial={{ opacity: 0, y: 14, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 10, scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 420, damping: 30 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-sm bg-[#121820] border border-white/12 rounded-3xl p-5 shadow-2xl space-y-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-white/8 border border-white/12 flex items-center justify-center text-[#93C5FD]">
                <KeyRound size={14} />
              </div>
              <div>
                <div className="text-sm font-semibold text-[#F2F6F4]">Add an AI provider</div>
                <div className="text-[11px] text-[#9CA3AF]">Use your own key for premium models</div>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="text-[#6B7280] hover:text-[#F2F6F4] transition-colors cursor-pointer"
              title="Close"
            >
              <X size={16} />
            </button>
          </div>

          <div className="space-y-1.5">
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#9CA3AF]">Provider</span>
            <div className="grid grid-cols-3 gap-1.5">
              {PROVIDERS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  title={p.desc}
                  onClick={() => handleProviderChange(p.id)}
                  className={`py-2 rounded-xl text-[11px] font-medium border transition-all cursor-pointer ${
                    provider === p.id
                      ? 'bg-white/10 text-[#F3F4F6] border-[#93C5FD]/40'
                      : 'bg-transparent text-[#9CA3AF] border-white/8 hover:text-[#F2F6F4] hover:bg-white/5'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="text-[11px] text-[#6B7280] px-0.5">
              {PROVIDERS.find((p) => p.id === provider)?.desc}
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="zyntry-provider-key" className="text-[10px] font-mono uppercase tracking-wider text-[#9CA3AF]">
              API key
            </label>
            <input
              id="zyntry-provider-key"
              type="password"
              value={key}
              autoFocus
              onChange={(e) => { setKey(e.target.value); setSaved(false); }}
              placeholder={provider === 'anthropic' ? 'sk-ant-…' : 'sk-…'}
              className="w-full bg-black/30 border border-white/10 rounded-xl px-3.5 py-2.5 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#93C5FD]/50"
            />
          </div>

          {provider === 'openai' && (
            <div className="space-y-1.5">
              <label htmlFor="zyntry-provider-base" className="text-[10px] font-mono uppercase tracking-wider text-[#9CA3AF]">
                Base URL <span className="text-[#6B7280] normal-case font-sans">(optional — any OpenAI-compatible endpoint)</span>
              </label>
              <input
                id="zyntry-provider-base"
                value={base}
                onChange={(e) => { setBase(e.target.value); setSaved(false); }}
                placeholder="https://api.openai.com/v1 (default)"
                className="w-full bg-black/30 border border-white/10 rounded-xl px-3.5 py-2.5 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#93C5FD]/50"
              />
            </div>
          )}

          <div className="text-[11px] text-[#6B7280] leading-relaxed">
            Your key stays on this device and is sent only with your task requests over HTTPS.
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={handleSave}
              disabled={!key.trim()}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                key.trim()
                  ? 'bg-white text-zinc-950 hover:bg-zinc-200'
                  : 'bg-white/[0.08] text-white/30 cursor-not-allowed'
              }`}
            >
              <Check size={13} />
              {saved && key.trim() ? 'Saved' : 'Save provider'}
            </button>
            {getProviderConfig() && (
              <button
                type="button"
                onClick={handleRemove}
                className="px-3.5 py-2.5 rounded-full border border-rose-500/30 text-[#FF7D7D] text-xs font-semibold bg-[#2A161A]/60 hover:bg-[#341B20] transition-colors cursor-pointer"
                title="Remove the saved provider key"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};
