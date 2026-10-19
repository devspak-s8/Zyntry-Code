import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { PlugZap, X } from 'lucide-react';
import {
  getBackendConfig,
  isBackendConfigured,
  setBackendConfig,
  api,
} from '../api/client';

/**
 * Floating backend-connection control. The backend URL is pre-wired by default
 * (http://localhost:8787, or VITE_BACKEND_URL); this badge shows the live
 * connection state and lets you change URL/token (persisted in localStorage).
 */
export const BackendBadge: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState(getBackendConfig().backendUrl);
  const [token, setToken] = useState(getBackendConfig().apiToken);
  const [status, setStatus] = useState<'unknown' | 'ok' | 'error' | 'connecting'>('unknown');
  const [message, setMessage] = useState('');

  const connected = isBackendConfigured();

  const check = async (): Promise<boolean> => {
    setStatus('connecting');
    setMessage('Contacting backend…');
    try {
      const health = await api.health();
      setStatus('ok');
      setMessage(
        `Connected — providers: ${(health.providers.configured || []).join(', ') || 'none configured'}`
      );
      return true;
    } catch (err) {
      setStatus('error');
      setMessage(`Backend unreachable: ${err instanceof Error ? err.message : String(err)}`);
      return false;
    }
  };

  // Auto health-check on mount so the badge reflects reality immediately.
  useEffect(() => {
    if (connected) check();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = async () => {
    setBackendConfig({ backendUrl: url.trim(), apiToken: token.trim() });
    if (!url.trim()) {
      setStatus('unknown');
      setMessage('Enter a backend URL to connect');
      return;
    }
    const ok = await check();
    if (ok) setOpen(false);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-80 rounded-2xl border border-white/10 bg-[#121820]/95 backdrop-blur-xl p-4 shadow-2xl space-y-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#F2F6F4]">Connect Zyntry backend</span>
            <button onClick={() => setOpen(false)} className="text-[#6F7B77] hover:text-[#F2F6F4]">
              <X size={14} />
            </button>
          </div>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://localhost:8787"
            className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#82B9FF]"
          />
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="API token (optional)"
            type="password"
            className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-[#F2F6F4] outline-none focus:border-[#82B9FF]"
          />
          {message && <div className="text-[11px] text-[#A3AEAA]">{message}</div>}
          <button
            onClick={connect}
            className="w-full py-2 rounded-full bg-white text-zinc-900 text-xs font-semibold hover:bg-zinc-200"
          >
            Connect
          </button>
        </motion.div>
      )}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen((v) => !v)}
        title={connected ? 'Backend connection' : 'Backend not connected — click to connect'}
        className={`flex items-center gap-2 px-3.5 py-2 rounded-full border text-xs font-semibold shadow-lg backdrop-blur-xl cursor-pointer ${
          connected
            ? status === 'ok'
              ? 'bg-[#0E2A1C] border-[#55E6A5]/40 text-[#55E6A5]'
              : 'bg-[#2A150F] border-[#F87171]/40 text-[#F87171]'
            : 'bg-[#121820]/95 border-white/10 text-[#F2F6F4]'
        }`}
      >
        <PlugZap size={13} />
        {connected ? 'Connected' : 'Not connected'}
      </motion.button>
    </div>
  );
};