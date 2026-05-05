import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Plus,
  Cpu,
  X,
  ChevronDown,
  Settings as SettingsIcon,
  Send,
  Check,
  FileText,
  Search as SearchIcon,
  Globe,
} from 'lucide-react';
import { FullScreen } from '@openuidev/react-ui';
import { useQueryClient } from '@tanstack/react-query';
import {
  openAIMessageFormat,
  openAIReadableStreamAdapter,
  useThread,
  useThreadList,
  type Message,
  type UserMessage,
} from "@openuidev/react-headless";
import { openuiLibrary, openuiPromptOptions } from "@openuidev/react-ui/genui-lib";
import { useAvailableModels } from '../../hooks/useModels';

interface GenUIChatViewProps {
  activeChatId: string | null;
  setActiveChatId: (id: string | null) => void;
}

const systemPrompt = openuiLibrary.prompt(openuiPromptOptions);

function normalizeStoredMessages(history: any[]): Message[] {
  return openAIMessageFormat.fromApi(history.map((message: any) => {
    const role = message.role === 'human' || message.role === 'user'
      ? 'user'
      : message.role === 'ai' || message.role === 'assistant'
        ? 'assistant'
        : message.role;

    return {
      role,
      content: message.content,
    };
  }));
}

function titleFromFirstMessage(message: UserMessage) {
  if (typeof message.content === 'string') {
    return message.content.slice(0, 30) || 'New Chat';
  }

  const firstTextPart = message.content?.find((part) => part.type === 'text');
  return firstTextPart?.text?.slice(0, 30) || 'New Chat';
}

function GenUIThreadBridge({ activeChatId }: { activeChatId: string | null }) {
  const selectedThreadId = useThreadList((state) => state.selectedThreadId);
  const selectThread = useThreadList((state) => state.selectThread);
  const switchToNewThread = useThreadList((state) => state.switchToNewThread);
  const isRunning = useThread((state) => state.isRunning);

  useEffect(() => {
    if (isRunning) return;

    if (activeChatId) {
      if (selectedThreadId !== activeChatId) {
        selectThread(activeChatId);
      }
      return;
    }

    if (selectedThreadId) {
      switchToNewThread();
    }
  }, [activeChatId, isRunning, selectedThreadId, selectThread, switchToNewThread]);

  return null;
}

export function GenUIChatView({ activeChatId, setActiveChatId }: GenUIChatViewProps) {
  const queryClient = useQueryClient();
  const currentChatIdRef = useRef<string | null>(activeChatId);
  const { data: availableModels = [] } = useAvailableModels();

  // Model selector state
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [activeTools, setActiveTools] = useState<string[]>([]);

  // Set default model to first in available_models.json
  useEffect(() => {
    if (availableModels.length > 0 && !selectedModel) {
      setSelectedModel(availableModels[0].id);
    }
  }, [availableModels, selectedModel]);

  useEffect(() => {
    currentChatIdRef.current = activeChatId;
  }, [activeChatId]);

  const handleThreadIdChange = useCallback((id: string) => {
    if (id && id !== currentChatIdRef.current) {
      currentChatIdRef.current = id;
      setActiveChatId(id);
    }
  }, [setActiveChatId]);

  const createThread = useCallback(async (firstMessage: UserMessage) => {
    const response = await fetch('/api/genui/sessions', { method: 'POST' });
    if (!response.ok) {
      throw new Error('Failed to create GenUI session');
    }

    const session = await response.json();
    currentChatIdRef.current = session.id;
    setActiveChatId(session.id);
    queryClient.invalidateQueries({ queryKey: ['genuiSessions'] });

    return {
      id: session.id,
      title: session.title || titleFromFirstMessage(firstMessage),
      createdAt: session.created || new Date().toISOString(),
    };
  }, [queryClient, setActiveChatId]);

  const loadThread = useCallback(async (threadId: string) => {
    const response = await fetch(`/api/genui/sessions/${encodeURIComponent(threadId)}`);
    if (!response.ok) {
      throw new Error('Failed to load GenUI session history');
    }

    const history = await response.json();
    return normalizeStoredMessages(history);
  }, []);

  const toggleTool = (tool: string) => {
    setActiveTools(prev => {
      let next = prev.includes(tool) ? prev.filter(t => t !== tool) : [...prev, tool];
      if (tool === 'thinking' && next.includes('thinking')) next = next.filter(t => t !== 'deepsearch');
      else if (tool === 'deepsearch' && next.includes('deepsearch')) next = next.filter(t => t !== 'thinking');
      return next;
    });
  };

  return (
    <div className="flex-1 flex flex-col bg-[#0A0A0A] h-full overflow-hidden genui-chat-view">
      <div className="flex-1 overflow-hidden">
        <FullScreen
          createThread={createThread}
          loadThread={loadThread}
          componentLibrary={openuiLibrary}
          streamProtocol={openAIReadableStreamAdapter()}
          processMessage={async ({ threadId, messages, abortController }) => {
            try {
              const response = await fetch('/api/genui/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  threadId: threadId || currentChatIdRef.current,
                  messages: openAIMessageFormat.toApi(messages),
                  systemPrompt: systemPrompt,
                  model: selectedModel || undefined,
                }),
                signal: abortController.signal,
              });

              if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error("Chat API error:", errorData);
                alert(`Chat error: ${errorData.detail || errorData.error || 'Failed to send message'}`);
                throw new Error(errorData.detail || errorData.error || 'Failed to send message');
              }

              // Extract thread ID from header to sync URL and state for new sessions
              const serverThreadId = response.headers.get('X-Thread-Id');
              if (serverThreadId && serverThreadId !== activeChatId) {
                console.info("Syncing new thread ID:", serverThreadId);
                handleThreadIdChange(serverThreadId);
              }

              if (response.body) {
                const [streamForOpenUI, streamForInvalidation] = response.body.tee();
                const reader = streamForInvalidation.getReader();

                void (async () => {
                  try {
                    while (!(await reader.read()).done) {
                      // Drain the monitoring stream so we can refresh the sidebar when persistence completes.
                    }
                  } finally {
                    queryClient.invalidateQueries({ queryKey: ['genuiSessions'] });
                  }
                })();

                return new Response(streamForOpenUI, {
                  status: response.status,
                  statusText: response.statusText,
                  headers: response.headers,
                });
              }

              queryClient.invalidateQueries({ queryKey: ['genuiSessions'] });
              return response;
            } catch (err: any) {
              console.error("processMessage caught error:", err);
              alert(`Chat error: ${err.message}`);
              throw err;
            }
          }}
          threadHeader={<GenUIThreadBridge activeChatId={activeChatId} />}
          agentName="Aria GenUI"
        />
      </div>

      {/* MODEL SELECTOR BAR - overlaid at bottom */}
      <div className="genui-model-bar">
        <div className="max-w-[780px] mx-auto flex items-center justify-between px-2 py-1">
          <div className="flex items-center gap-1.5 overflow-hidden">
            <div className="relative flex-shrink-0">
              <button 
                onClick={() => setShowPlusMenu(!showPlusMenu)}
                className={`w-8 h-8 flex items-center justify-center rounded-full transition-all ${showPlusMenu ? 'bg-[#2A2A2A] text-white' : 'text-gray-500 hover:bg-[#2A2A2A] hover:text-white'}`}
              >
                <Plus className={`w-4.5 h-4.5 transition-transform ${showPlusMenu ? 'rotate-45' : ''}`} />
              </button>
              
              <AnimatePresence>
                {showPlusMenu && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 10 }}
                    className="absolute bottom-full left-0 mb-3 w-60 bg-[#1F1F1F] border border-[#333] rounded-2xl shadow-2xl overflow-hidden z-[60] py-1.5"
                  >
                    {[
                      { id: 'docs', label: 'Upload photos & files', icon: FileText, shortcut: 'Ctrl+U' },
                      { id: 'thinking', label: 'Thinking', icon: Cpu, isTool: true },
                      { id: 'deepsearch', label: 'Deep search', icon: SearchIcon, isTool: true },
                      { id: 'web', label: 'Web search', icon: Globe, isTool: true },
                    ].map((item) => (
                      <button 
                        key={item.id}
                        onClick={() => {
                          if (item.isTool) toggleTool(item.id);
                          setShowPlusMenu(false);
                        }}
                        className={`w-full flex items-center justify-between px-3.5 py-2 text-[12px] hover:bg-[#2A2A2A] transition-colors group ${activeTools.includes(item.id) ? 'bg-[#2A2A2A]/40' : ''}`}
                      >
                        <div className="flex items-center gap-3">
                          <item.icon className={`w-3.5 h-3.5 ${activeTools.includes(item.id) ? 'text-[#8B5CF6]' : 'text-gray-400 group-hover:text-gray-200'}`} />
                          <span className={activeTools.includes(item.id) ? 'text-white font-medium' : 'text-gray-300'}>{item.label}</span>
                        </div>
                        {activeTools.includes(item.id) && <Check className="w-3.5 h-3.5 text-[#8B5CF6]" />}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5">
              <AnimatePresence>
                {activeTools.map(toolId => {
                  const tool = [
                    { id: 'thinking', label: 'Thinking', icon: Cpu, color: 'text-[#8B5CF6]' },
                    { id: 'deepsearch', label: 'Deep search', icon: SearchIcon, color: 'text-emerald-500' },
                    { id: 'web', label: 'Search', icon: Globe, color: 'text-blue-500' }
                  ].find(t => t.id === toolId);
                  if (!tool) return null;
                  return (
                    <motion.div 
                      key={tool.id}
                      layout
                      initial={{ scale: 0.9, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.9, opacity: 0 }}
                      className="flex items-center gap-1.5 bg-[#1F1F1F] border border-[#333] px-2.5 py-1.5 rounded-full text-[10px] font-medium text-gray-300 flex-shrink-0 cursor-default"
                    >
                      <tool.icon className={`w-3 h-3 ${tool.color}`} />
                      <span className="max-w-[70px] truncate">{tool.label}</span>
                      <button onClick={() => toggleTool(tool.id)} className="hover:text-white transition-colors">
                        <X className="w-3 h-3 text-gray-600" />
                      </button>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            <div className="relative">
              <button 
                onClick={() => setShowModelMenu(!showModelMenu)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-[#2A2A2A] rounded-xl transition-colors"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-[#8B5CF6]" />
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                  {availableModels.find(m => m.id === selectedModel)?.name || selectedModel || 'Select Model'}
                </span>
                <ChevronDown className={`w-3 h-3 text-gray-500 transition-transform ${showModelMenu ? 'rotate-180' : ''}`} />
              </button>
              
              <AnimatePresence>
                {showModelMenu && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 10 }}
                    className="absolute bottom-full right-0 mb-3 w-48 bg-[#1F1F1F] border border-[#333] rounded-xl shadow-2xl overflow-hidden z-[60] p-1"
                  >
                    {availableModels.map((m) => (
                      <button 
                        key={m.id}
                        onClick={() => { setSelectedModel(m.id); setShowModelMenu(false); }}
                        className="w-full flex items-center justify-between px-3 py-1.5 text-[11px] hover:bg-[#2A2A2A] text-gray-400 hover:text-white rounded-lg transition-all text-left"
                      >
                        <span>{m.name}</span>
                        {selectedModel === m.id && <Check className="w-3 h-3 text-[#8B5CF6]" />}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button 
              className="w-8 h-8 flex items-center justify-center text-gray-500 hover:text-white hover:bg-[#2A2A2A] rounded-full transition-all"
            >
              <SettingsIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
        <p className="text-[9px] text-gray-600 text-center uppercase tracking-widest leading-none pb-1">ARIA v1.2 // General Session</p>
      </div>
    </div>
  );
}
