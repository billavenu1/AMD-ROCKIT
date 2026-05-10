import React, { useEffect, useMemo, useState } from 'react';
import { ExternalLink, RefreshCw, Workflow, ShieldAlert } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

const FEEDBACK_URL = 'https://forms.gle/Cza63xPCqrJAjCHD6';

export const ElyraView: React.FC = () => {
  const [frameKey, setFrameKey] = useState(0);
  const [hasFrameError, setHasFrameError] = useState(false);
  const [showWarning, setShowWarning] = useState(true);

  const elyraUrl = useMemo(() => {
    const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
    return env?.VITE_ELYRA_BASE_URL || '/elyra/lab';
  }, []);

  // Auto-dismiss warning after 3 seconds
  useEffect(() => {
    const timer = setTimeout(() => setShowWarning(false), 3000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <main className="flex-1 min-w-0 bg-[#0A0A0A] text-gray-300 flex flex-col overflow-hidden">
      <header className="h-14 border-b border-[#1F1F1F] flex items-center justify-between px-4 bg-[#0A0A0A]/80 backdrop-blur-md">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-[#1A1A1A] border border-[#333] flex items-center justify-center">
            <Workflow className="w-4 h-4 text-[#8B5CF6]" />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-white leading-none">Elyra</h1>
            <p className="text-[10px] text-gray-500 mt-1 truncate">{elyraUrl}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400/80 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-lg">
            View Only
          </span>
          <button
            onClick={() => {
              setHasFrameError(false);
              setFrameKey((key) => key + 1);
            }}
            className="w-8 h-8 rounded-lg text-gray-500 hover:text-white hover:bg-[#1A1A1A] flex items-center justify-center transition-colors"
            title="Reload Elyra"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => window.open(elyraUrl, '_blank', 'noopener,noreferrer')}
            className="w-8 h-8 rounded-lg text-gray-500 hover:text-white hover:bg-[#1A1A1A] flex items-center justify-center transition-colors"
            title="Open Elyra in a new tab"
          >
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </header>

      <section className="relative flex-1 bg-[#050505]">
        {/* 3-Second View-Only Warning Popup */}
        <AnimatePresence>
          {showWarning && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.4 } }}
              className="absolute inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
            >
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="bg-[#121212] border border-[#8B5CF6]/40 p-8 rounded-2xl text-center shadow-[0_0_40px_rgba(139,92,246,0.25)] max-w-md"
              >
                <div className="mx-auto mb-4 w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 flex items-center justify-center">
                  <ShieldAlert className="w-7 h-7 text-amber-400" />
                </div>
                <h2 className="text-xl font-bold text-white mb-2">⚠️ View-Only Mode</h2>
                <p className="text-gray-400 text-sm leading-relaxed mb-4">
                  This Elyra environment is restricted to prevent changes.
                  <br />
                  File editing, code execution, and terminal access are disabled.
                </p>
                <div className="border-t border-[#222] pt-4 mt-4">
                  <p className="text-gray-500 text-xs mb-2">We'd love your feedback after exploring!</p>
                  <a
                    href={FEEDBACK_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-[#A78BFA] hover:text-white transition-colors"
                  >
                    Leave a Review →
                  </a>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {hasFrameError && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#050505]">
            <div className="max-w-sm text-center">
              <div className="mx-auto mb-4 w-12 h-12 rounded-xl bg-[#1A1A1A] border border-[#333] flex items-center justify-center">
                <Workflow className="w-5 h-5 text-gray-500" />
              </div>
              <h2 className="text-sm font-bold text-white">Elyra is not reachable</h2>
              <p className="mt-2 text-xs text-gray-500 leading-5">
                Start the Elyra Docker service and reload this panel.
              </p>
            </div>
          </div>
        )}
        <iframe
          key={frameKey}
          title="Elyra JupyterLab"
          src={elyraUrl}
          className="h-full w-full border-0 bg-white"
          sandbox="allow-downloads allow-forms allow-modals allow-popups allow-same-origin allow-scripts"
          allow="clipboard-read; clipboard-write"
          onError={() => setHasFrameError(true)}
        />
      </section>
    </main>
  );
};
