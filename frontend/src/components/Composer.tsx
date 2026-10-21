import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { WorkspaceMode } from '../types';
import { api, getProviderConfig, ProviderConfig } from '../api/client';
import { 
  ArrowUp,
  Square, 
  Bot, 
  Code2, 
  HelpCircle, 
  Paperclip, 
  ChevronUp, 
  X, 
  Check, 
  FileCode,
  Cpu,
  Lock,
  Plus,
  Mic,
  GitBranch,
  CornerDownLeft
} from 'lucide-react';

interface ComposerProps {
  onSendMessage: (content: string, attachedFiles: string[]) => void;
  onStopAgent?: () => void;
  isRunning?: boolean;
  mode?: WorkspaceMode;
  onModeChange?: (mode: WorkspaceMode) => void;
  initialText?: string;
  selectedModel?: string;
  onModelChange?: (modelId: string) => void;
  onAddProvider?: () => void;
}

interface ModelOption {
  id: string;
  display_name: string;
  provider: string;
  costIn: number;
  costOut: number;
  available: boolean;
}

/** Does the caller's own saved provider key unlock this model's provider? */
function keyUnlocks(model: ModelOption, cfg: ProviderConfig | null): boolean {
  if (!cfg?.key) return false;
  if (model.provider === 'workers_ai') return true; // edge inference needs no key
  if (model.provider === 'openai') return cfg.provider === 'openai' || cfg.provider === 'openrouter';
  if (model.provider === 'anthropic') return cfg.provider === 'anthropic';
  return false;
}

const MODE_ITEMS: { id: WorkspaceMode; label: string; icon: React.ReactNode; desc: string }[] = [
  { 
    id: 'agent', 
    label: 'Agent', 
    icon: <Bot size={13} />, 
    desc: 'Autonomous multi-step execution with planning, tools, and verification' 
  },
  { 
    id: 'edit', 
    label: 'Edit', 
    icon: <Code2 size={13} />, 
    desc: 'Targeted file modifications with instant diff review' 
  },
  { 
    id: 'ask', 
    label: 'Ask', 
    icon: <HelpCircle size={13} />, 
    desc: 'Architecture analysis, codebase search, and technical Q&A' 
  },
];

const QUICK_BUBBLY_PROMPTS = [
  { label: 'Explain the codebase', text: 'Explain this repository architecture, entrypoints, and invariants.' },
  { label: 'Find bugs', text: 'Review the current code for bugs, edge cases, and regressions.' },
  { label: 'Add tests', text: 'Add unit tests for the core logic of this project.' },
  { label: 'Refactor', text: 'Refactor the messiest module in this project for clarity and safety.' }
];

export const Composer: React.FC<ComposerProps> = ({
  onSendMessage,
  onStopAgent,
  isRunning = false,
  mode = 'agent',
  onModeChange,
  initialText = '',
  selectedModel = 'auto',
  onModelChange,
  onAddProvider,
}) => {
  const [text, setText] = useState(initialText);
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const [showModeMenu, setShowModeMenu] = useState(false);
  const [showFileMenu, setShowFileMenu] = useState(false);
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [showQuickPrompts, setShowQuickPrompts] = useState(true);
  const [freeModels, setFreeModels] = useState<ModelOption[]>([]);
  const [premiumModels, setPremiumModels] = useState<ModelOption[]>([]);
  const [contextFiles] = useState<string[]>([]);

  // Interactive features
  const [isListening, setIsListening] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (initialText) {
      setText(initialText);
      adjustTextareaHeight();
    }
  }, [initialText]);

  // Fetch the model catalog for the model picker (free + premium sections).
  useEffect(() => {
    let alive = true;
    api.models().then((res) => {
      if (!alive) return;
      const models = (res.models as {
        id: string;
        display_name: string;
        provider: string;
        available: boolean;
        cost: { in_per_1m: number; out_per_1m: number };
      }[]) ?? [];
      const mapped: ModelOption[] = models.map((m) => ({
        id: m.id,
        display_name: m.display_name,
        provider: m.provider,
        costIn: Number(m.cost?.in_per_1m ?? 0),
        costOut: Number(m.cost?.out_per_1m ?? 0),
        available: Boolean(m.available),
      }));
      setFreeModels(mapped.filter((m) => m.costIn === 0 && m.costOut === 0));
      setPremiumModels(mapped.filter((m) => !(m.costIn === 0 && m.costOut === 0)));
    }).catch(() => { /* picker still shows Auto; retried next open */ });
    return () => { alive = false; };
  }, []);

  // Click outside to close popovers
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowModeMenu(false);
        setShowFileMenu(false);
        setShowModelMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight, 150);
      textareaRef.current.style.height = `${Math.max(32, newHeight)}px`;
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    adjustTextareaHeight();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'Escape') {
      setShowModeMenu(false);
      setShowFileMenu(false);
      setShowModelMenu(false);
    }
  };

  const handleSubmit = () => {
    if (!text.trim() || isRunning) return;
    onSendMessage(text.trim(), attachedFiles);
    setText('');
    setShowModeMenu(false);
    setShowFileMenu(false);
    setShowModelMenu(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = '32px';
    }
  };

  const handleQuickPromptClick = (promptText: string) => {
    setText(promptText);
    setTimeout(() => {
      adjustTextareaHeight();
      textareaRef.current?.focus();
    }, 20);
  };

  const toggleFile = (filePath: string) => {
    if (attachedFiles.includes(filePath)) {
      setAttachedFiles(attachedFiles.filter((f) => f !== filePath));
    } else {
      setAttachedFiles([...attachedFiles, filePath]);
    }
  };

  const removeFile = (filePath: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setAttachedFiles(attachedFiles.filter((f) => f !== filePath));
  };

  const toggleDictation = () => {
    if (!isListening) {
      setIsListening(true);
      setTimeout(() => {
        setText((prev) => {
          const addition = prev 
            ? `${prev} and verify against the test suite`
            : 'Check the core logic for concurrency issues and run dry-run verification';
          setTimeout(adjustTextareaHeight, 40);
          return addition;
        });
        setIsListening(false);
      }, 1600);
    } else {
      setIsListening(false);
    }
  };

  const activeModeItem = MODE_ITEMS.find((m) => m.id === mode) || MODE_ITEMS[0];
  const activeModelLabel = selectedModel === 'auto'
    ? 'Auto'
    : [...freeModels, ...premiumModels].find((m) => m.id === selectedModel)?.display_name || 'Custom model';
  const savedProvider = getProviderConfig();

  return (
    <div className="absolute bottom-4 sm:bottom-6 left-0 right-0 px-3.5 sm:px-6 pointer-events-none z-30 flex justify-center">
      {/* Centered Floating Capsule */}
      <div ref={containerRef} className="w-full max-w-2xl sm:max-w-3xl pointer-events-auto relative flex flex-col items-center">
        
        {/* Quick Suggestion Prompts */}
        {!text && !isRunning && showQuickPrompts && (
          <motion.div 
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            className="w-full flex items-center justify-center gap-1.5 sm:gap-2 mb-2.5 overflow-x-auto py-1 px-1 scrollbar-none"
          >
            <div className="hidden sm:flex items-center gap-1 text-[11px] font-mono text-[#9CA3AF] mr-1 shrink-0">
              <span>Quick start:</span>
            </div>
            {QUICK_BUBBLY_PROMPTS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => handleQuickPromptClick(p.text)}
                className="shrink-0 px-3 py-1 rounded-full bg-white/6 hover:bg-white/10 border border-white/10 hover:border-white/20 text-[11px] font-sans text-[#F3F4F6] hover:text-white transition-all cursor-pointer shadow-xs hover:scale-[1.02] active:scale-[0.98]"
              >
                {p.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setShowQuickPrompts(false)}
              className="text-[#9CA3AF] hover:text-white p-1 rounded-full cursor-pointer shrink-0 ml-0.5 transition-colors"
              title="Hide quick suggestions"
            >
              <X size={11} />
            </button>
          </motion.div>
        )}

        {/* 1. Floating Mode Popover */}
        <AnimatePresence>
          {showModeMenu && (
            <motion.div
              initial={{ opacity: 0, y: 12, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 450, damping: 28 }}
              className="absolute bottom-full mb-3.5 left-2 sm:left-4 w-76 sm:w-80 bg-[#141A22] border border-white/12 rounded-[24px] p-3 shadow-2xl backdrop-blur-2xl z-40 space-y-1.5"
            >
              <div className="px-3 py-1.5 flex items-center justify-between text-[10px] font-mono text-[#9CA3AF] uppercase tracking-wider border-b border-white/6 pb-2">
                <span>Execution Mode</span>
                <span className="text-[#93C5FD] lowercase font-semibold">adaptive routing</span>
              </div>
              {MODE_ITEMS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    onModeChange?.(item.id);
                    setShowModeMenu(false);
                  }}
                  className={`w-full flex items-start gap-3 px-3.5 py-2.5 rounded-[18px] text-left text-xs transition-all cursor-pointer ${
                    mode === item.id 
                      ? 'bg-white/10 text-white font-medium border border-white/12 shadow-xs' 
                      : 'text-[#9CA3AF] hover:text-white hover:bg-white/5 border border-transparent'
                  }`}
                >
                  <div className="mt-0.5 shrink-0 text-[#93C5FD]">
                    {item.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-white">{item.label}</span>
                      {mode === item.id && <Check size={13} className="text-[#93C5FD]" />}
                    </div>
                    <p className="text-[11px] text-[#9CA3AF] leading-relaxed mt-0.5 font-sans">
                      {item.desc}
                    </p>
                  </div>
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* 2. Floating Model Picker Popover */}
        <AnimatePresence>
          {showModelMenu && (
            <motion.div
              initial={{ opacity: 0, y: 12, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 450, damping: 28 }}
              className="absolute bottom-full mb-3.5 left-0 w-80 max-h-80 overflow-y-auto bg-[#141A22] border border-white/12 rounded-[24px] p-3 shadow-2xl backdrop-blur-2xl z-40 space-y-1.5"
            >
              <div className="px-3 py-1.5 flex items-center justify-between text-[10px] font-mono text-[#9CA3AF] uppercase tracking-wider border-b border-white/6 pb-2">
                <span>Free models</span>
                <span className="text-[#55E6A5] font-mono font-medium">no key needed</span>
              </div>
              <div className="space-y-1 pt-1">
                {/* Auto — smart per-stage routing */}
                <button
                  id="zyntry-model-auto"
                  type="button"
                  onClick={() => {
                    onModelChange?.('auto');
                    setShowModelMenu(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-[14px] text-left transition-all cursor-pointer ${
                    selectedModel === 'auto'
                      ? 'bg-white/10 border border-[#93C5FD]/30'
                      : 'text-[#9CA3AF] hover:text-white hover:bg-white/5 border border-transparent'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="text-xs font-sans font-semibold text-[#F3F4F6]">Auto routing</div>
                    <div className="text-[10px] text-[#6B7280] font-sans mt-0.5">
                      Zyntry picks the best free model per task stage
                    </div>
                  </div>
                  {selectedModel === 'auto' && <Check size={13} className="shrink-0 text-[#93C5FD]" />}
                </button>
                {freeModels.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      onModelChange?.(m.id);
                      setShowModelMenu(false);
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-[14px] text-left transition-all cursor-pointer ${
                      selectedModel === m.id
                        ? 'bg-white/10 border border-[#93C5FD]/30'
                        : 'text-[#9CA3AF] hover:text-white hover:bg-white/5 border border-transparent'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="text-xs font-sans font-semibold text-[#F3F4F6] truncate">{m.display_name}</div>
                      <div className="text-[10px] text-[#6B7280] font-mono mt-0.5 truncate">{m.id}</div>
                    </div>
                    {selectedModel === m.id && <Check size={13} className="shrink-0 text-[#93C5FD]" />}
                  </button>
                ))}
                {freeModels.length === 0 && (
                  <div className="px-3 py-2 text-[11px] text-[#6B7280] font-sans">
                    Free model catalog could not load — Auto routing is used.
                  </div>
                )}
              </div>

              {/* Premium / BYO-key models */}
              <div className="pt-1.5">
                <div className="px-3 pb-1 flex items-center justify-between text-[10px] font-mono text-[#9CA3AF] uppercase tracking-wider border-t border-white/6 pt-2">
                  <span>More models</span>
                  <span>{savedProvider ? 'your key' : 'key needed'}</span>
                </div>
                <div className="space-y-1">
                  {premiumModels.map((m) => {
                    const pickable = m.available || keyUnlocks(m, savedProvider);
                    if (pickable) {
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            onModelChange?.(m.id);
                            setShowModelMenu(false);
                          }}
                          className={`w-full flex items-center justify-between px-3 py-2.5 rounded-[14px] text-left transition-all cursor-pointer ${
                            selectedModel === m.id
                              ? 'bg-white/10 border border-[#93C5FD]/30'
                              : 'text-[#9CA3AF] hover:text-white hover:bg-white/5 border border-transparent'
                          }`}
                        >
                          <div className="min-w-0 flex items-center gap-2">
                            <div className="min-w-0">
                              <div className="text-xs font-sans font-semibold text-[#F3F4F6] truncate">{m.display_name}</div>
                              <div className="text-[10px] text-[#6B7280] font-mono mt-0.5 truncate">
                                {m.provider}{m.available ? '' : ' · via your key'}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[9px] font-mono text-[#6B7280] bg-white/6 border border-white/8 rounded-full px-1.5 py-0.5">
                              ${m.costIn || 0}/M
                            </span>
                            {selectedModel === m.id && <Check size={13} className="text-[#93C5FD]" />}
                          </div>
                        </button>
                      );
                    }
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => {
                          setShowModelMenu(false);
                          onAddProvider?.();
                        }}
                        className="w-full flex items-center justify-between px-3 py-2.5 rounded-[14px] text-left transition-all cursor-pointer opacity-50 hover:opacity-80 text-[#9CA3AF] hover:bg-white/5 border border-transparent"
                        title="Add a provider key to use this model"
                      >
                        <div className="min-w-0 flex items-center gap-2">
                          <Lock size={11} className="text-[#6B7280] shrink-0" />
                          <div className="min-w-0">
                            <div className="text-xs font-sans font-semibold text-[#F3F4F6] truncate">{m.display_name}</div>
                            <div className="text-[10px] text-[#6B7280] font-sans mt-0.5">Add a key to unlock</div>
                          </div>
                        </div>
                        <span className="text-[9px] font-mono text-[#6B7280] bg-white/6 border border-white/8 rounded-full px-1.5 py-0.5 shrink-0">
                          ${m.costIn || 0}/M
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Divider + Add an AI provider */}
              <div className="mx-1 my-1 border-t border-white/6" />
              <button
                id="zyntry-add-provider"
                type="button"
                onClick={() => {
                  setShowModelMenu(false);
                  onAddProvider?.();
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[14px] text-left text-xs transition-all cursor-pointer text-[#9CA3AF] hover:text-white hover:bg-white/5 border border-transparent"
              >
                <div className="w-6 h-6 rounded-lg bg-white/8 border border-white/12 flex items-center justify-center text-[#93C5FD] shrink-0">
                  <Plus size={12} />
                </div>
                <div className="min-w-0">
                  <div className="font-semibold text-[#F3F4F6]">Add an AI provider</div>
                  <div className="text-[10px] text-[#6B7280] font-sans mt-0.5">
                    Bring your own API key for premium models (GPT-5, Claude …)
                  </div>
                </div>
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* 3. Floating Context / File Picker Popover */}
        <AnimatePresence>
          {showFileMenu && (
            <motion.div
              initial={{ opacity: 0, y: 12, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 450, damping: 28 }}
              className="absolute bottom-full mb-3.5 left-8 sm:left-24 w-84 max-h-76 overflow-y-auto bg-[#141A22] border border-white/12 rounded-[24px] p-3.5 shadow-2xl backdrop-blur-2xl z-40 space-y-1.5"
            >
              <div className="px-3 py-1 flex items-center justify-between text-[10px] font-mono text-[#9CA3AF] uppercase tracking-wider border-b border-white/6 pb-2">
                <span>In-Scope Context Files</span>
                <span className="text-[#93C5FD] font-mono font-medium">{attachedFiles.length} attached</span>
              </div>
              {contextFiles.length === 0 ? (
                <div className="px-3 py-4 text-center text-[11px] text-[#6B7280] font-sans leading-relaxed">
                  No context files yet.
                  <br />
                  Zyntry explores your workspace automatically — attached files appear here.
                </div>
              ) : (
                <div className="space-y-1 pt-1">
                  {contextFiles.map((file: string) => {
                  const isSelected = attachedFiles.includes(file);
                  return (
                    <button
                      key={file}
                      type="button"
                      onClick={() => toggleFile(file)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-[14px] text-left text-xs font-mono transition-all cursor-pointer ${
                        isSelected 
                          ? 'bg-white/10 text-[#93C5FD] font-medium border border-[#93C5FD]/30' 
                          : 'text-[#9CA3AF] hover:text-white hover:bg-white/5 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <FileCode size={13} className={isSelected ? 'text-[#93C5FD]' : 'text-[#6F7B77]'} />
                        <span className="truncate">{file}</span>
                      </div>
                      {isSelected && <Check size={13} className="shrink-0 text-[#93C5FD]" />}
                    </button>
                  );
                  })}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* 4. The Main Composer Capsule (Unified Dark Obsidian Palette) */}
        <div className="w-full bg-[#121821]/95 hover:bg-[#141C26] focus-within:bg-[#151E28] border border-white/12 hover:border-white/20 focus-within:border-[#93C5FD]/40 rounded-[28px] sm:rounded-[34px] p-3 sm:p-4 space-y-3 shadow-2xl backdrop-blur-2xl transition-all">
          
          {/* Active Attached Files Chips */}
          {attachedFiles.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 px-2 pt-0.5">
              {attachedFiles.map((file) => (
                <span
                  key={file}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/6 hover:bg-white/10 border border-[#93C5FD]/25 text-[11px] font-mono text-[#93C5FD] transition-colors shadow-xs"
                >
                  <FileCode size={11} className="text-[#93C5FD]" />
                  <span>{file.split('/').pop()}</span>
                  <button
                    type="button"
                    onClick={(e) => removeFile(file, e)}
                    className="text-[#9CA3AF] hover:text-white p-0.5 rounded-full cursor-pointer ml-0.5 transition-colors"
                    title={`Remove ${file}`}
                  >
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Main Input Row */}
          <div className="flex items-end gap-2 sm:gap-3 px-1.5">
            <textarea
              ref={textareaRef}
              rows={1}
              value={text}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder={isListening ? "Listening to voice input…" : "Describe what you want Zyntry Code to execute (Enter to run)…"}
              className="bg-transparent flex-1 min-w-0 text-xs sm:text-[13px] md:text-sm text-[#F3F4F6] placeholder-[#9CA3AF] focus:outline-none resize-none py-1.5 font-sans leading-relaxed tracking-normal max-h-36 overflow-y-auto caret-[#93C5FD]"
              style={{ minHeight: '32px', height: '32px' }}
            />

            {/* Clear Input Button */}
            {text.trim().length > 0 && (
              <button
                type="button"
                onClick={() => {
                  setText('');
                  if (textareaRef.current) textareaRef.current.style.height = '32px';
                }}
                className="text-[#9CA3AF] hover:text-white p-1.5 rounded-full hover:bg-white/8 transition-colors cursor-pointer shrink-0 mb-1"
                title="Clear input"
              >
                <X size={14} />
              </button>
            )}

            {/* Dictation / Voice Button */}
            <button
              type="button"
              onClick={toggleDictation}
              className={`p-2 rounded-full transition-all cursor-pointer shrink-0 mb-0.5 ${
                isListening 
                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse' 
                  : 'text-[#9CA3AF] hover:text-[#F3F4F6] hover:bg-white/8'
              }`}
              title={isListening ? "Stop listening" : "Dictate prompt via voice"}
            >
              <Mic size={15} />
            </button>

            {/* Send or Stop Action Button */}
            {isRunning ? (
              <motion.button
                type="button"
                whileTap={{ scale: 0.94 }}
                onClick={onStopAgent}
                className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#2A161A] text-[#FF7D7D] border border-[#FF7D7D]/40 text-xs font-semibold cursor-pointer shrink-0 hover:bg-[#341B20] transition-colors shadow-md mb-0.5"
              >
                <Square size={11} className="fill-current" />
                <span>Stop</span>
              </motion.button>
            ) : (
              <motion.button
                type="button"
                whileHover={{ scale: 1.06 }}
                whileTap={{ scale: 0.92 }}
                onClick={handleSubmit}
                disabled={!text.trim()}
                className={`w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center transition-all cursor-pointer shrink-0 mb-0.5 ${
                  text.trim()
                    ? 'bg-white text-zinc-950 hover:bg-zinc-200 shadow-md border border-white/40'
                    : 'bg-white/[0.08] text-white/30 border border-white/8 cursor-not-allowed opacity-40'
                }`}
                title="Send prompt (Enter)"
              >
                <ArrowUp size={16} strokeWidth={2.6} />
              </motion.button>
            )}
          </div>

          {/* Integrated Actions Bar: Matching Normal App Palette */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2.5 border-t border-white/6 text-xs">
            
            {/* Left Action Pills */}
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
              
              {/* Action 1: Mode Selector */}
              <button
                type="button"
                onClick={() => {
                  setShowModeMenu(!showModeMenu);
                  setShowFileMenu(false);
                  setShowModelMenu(false);
                }}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/6 hover:bg-white/10 border border-white/10 text-[11px] font-medium text-[#F3F4F6] cursor-pointer transition-all shadow-xs"
                title="Change Execution Mode"
              >
                <span className="text-[#93C5FD]">{activeModeItem.icon}</span>
                <span>{activeModeItem.label}</span>
                <ChevronUp size={12} className={`text-[#9CA3AF] transition-transform ${showModeMenu ? 'rotate-180' : ''}`} />
              </button>

              {/* Action 2: Context / File Attachment Pill */}
              <button
                type="button"
                onClick={() => {
                  setShowFileMenu(!showFileMenu);
                  setShowModeMenu(false);
                  setShowModelMenu(false);
                }}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border text-[11px] font-mono cursor-pointer transition-all shadow-xs ${
                  attachedFiles.length > 0 
                    ? 'bg-white/6 border-[#93C5FD]/30 text-[#93C5FD] hover:bg-white/10' 
                    : 'bg-transparent border-white/8 text-[#9CA3AF] hover:text-[#F3F4F6] hover:border-white/15'
                }`}
                title="Manage Workspace Context Files"
              >
                <Paperclip size={12} />
                <span>
                  {attachedFiles.length === 1 
                    ? attachedFiles[0].split('/').pop() 
                    : `${attachedFiles.length} files`}
                </span>
              </button>

              {/* Action 3: Model Selector */}
              <button
                type="button"
                onClick={() => {
                  setShowModelMenu(!showModelMenu);
                  setShowModeMenu(false);
                  setShowFileMenu(false);
                }}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/6 hover:bg-white/10 border border-white/10 text-[11px] font-medium text-[#F3F4F6] cursor-pointer transition-all shadow-xs"
                title="Choose a model"
              >
                <Cpu size={12} className="text-[#93C5FD]" />
                <span className="max-w-32 truncate">{activeModelLabel}</span>
                <ChevronUp size={12} className={`text-[#9CA3AF] transition-transform ${showModelMenu ? 'rotate-180' : ''}`} />
              </button>

            </div>

            {/* Right Context Badge: Branch Status & Shortcut hint */}
            <div className="hidden sm:flex items-center gap-2.5 text-[10px] font-mono text-[#9CA3AF]">
              <span className="text-[10px] text-[#6F7B77] flex items-center gap-1">
                <span>Enter</span>
                <CornerDownLeft size={10} className="text-[#6F7B77]" />
                <span>to execute</span>
              </span>
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/4 border border-white/6 text-[#F3F4F6]">
                <GitBranch size={10} className="text-[#93C5FD]" />
                <span>main</span>
              </div>
            </div>

          </div>

        </div>
      </div>
    </div>
  );
};
