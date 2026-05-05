import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Ghost, 
  Folder, 
  PanelRightOpen, 
  FileText, 
  Search as SearchIcon, 
  Code, 
  Globe,
  Plus,
  Cpu,
  X,
  ChevronDown,
  Settings as SettingsIcon,
  Send,
  Check,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChat } from '../../hooks/useChat';
import { useNotebook } from '../../hooks/useNotebooks';
import { useAvailableModels } from '../../hooks/useModels';
import { convertReferencesToCompactMarkdown, createCompactReferenceLinkComponent, ReferenceType } from '../../lib/utils/source-references';

function AIMessageContent({
  content,
  onReferenceClick
}: {
  content: string
  onReferenceClick: (type: ReferenceType, id: string) => void
}) {
  // Convert references to compact markdown with numbered citations
  const markdownWithCompactRefs = convertReferencesToCompactMarkdown(content, 'References')

  // Create custom link component for compact references
  const LinkComponent = createCompactReferenceLinkComponent(onReferenceClick)

  return (
    <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none break-words prose-headings:font-semibold prose-a:text-[#8B5CF6] prose-a:break-all prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-p:mb-4 prose-p:leading-7 prose-li:mb-2 text-gray-300">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: LinkComponent,
          p: ({ children }) => <p className="mb-4">{children}</p>,
          h1: ({ children }) => <h1 className="mb-4 mt-6 text-white text-xl">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-3 mt-5 text-white text-lg">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-3 mt-4 text-white text-md">{children}</h3>,
          h4: ({ children }) => <h4 className="mb-2 mt-4 text-white">{children}</h4>,
          li: ({ children }) => <li className="mb-1 ml-4 list-disc">{children}</li>,
          ul: ({ children }) => <ul className="mb-4 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="mb-4 space-y-1 list-decimal ml-4">{children}</ol>,
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto">
              <table className="min-w-full border-collapse border border-[#333]">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-[#1A1A1A]">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-[#333]">{children}</tr>,
          th: ({ children }) => <th className="border border-[#333] px-3 py-2 text-left font-semibold">{children}</th>,
          td: ({ children }) => <td className="border border-[#333] px-3 py-2">{children}</td>,
        }}
      >
        {markdownWithCompactRefs}
      </ReactMarkdown>
    </div>
  )
}

interface ChatViewProps {
  isSidebarCollapsed: boolean;
  setIsSidebarCollapsed: (collapsed: boolean) => void;
  activeProjectId: string | null;
  activeChatId: string | null;
  setActiveChatId: (id: string | null) => void;
  selectedDocIds: string[];
  isRightPanelOpen: boolean;
  setIsRightPanelOpen: (open: boolean) => void;
}

export const ChatView: React.FC<ChatViewProps> = ({
  isSidebarCollapsed,
  setIsSidebarCollapsed,
  activeProjectId,
  activeChatId,
  setActiveChatId,
  selectedDocIds,
  isRightPanelOpen,
  setIsRightPanelOpen,
}) => {
  const { 
    messages, 
    isSending, 
    sendMessage, 
    currentSessionId,
    setCurrentSessionId 
  } = useChat(activeProjectId);

  const { data: project } = useNotebook(activeProjectId);
  const { data: availableModels = [] } = useAvailableModels();

  React.useEffect(() => {
    setCurrentSessionId(activeChatId);
  }, [activeChatId, setCurrentSessionId]);

  const [input, setInput] = useState('');
  const [isIncognito, setIsIncognito] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [interactiveUI, setInteractiveUI] = useState(true);
  const [writingStyle, setWritingStyle] = useState<'Concise' | 'Balanced' | 'Creative'>('Balanced');
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [activeTools, setActiveTools] = useState<string[]>([]);

  // Set default model to the first entry in available_models.json
  React.useEffect(() => {
    if (availableModels.length > 0 && !selectedModel) {
      setSelectedModel(availableModels[0].id);
    }
  }, [availableModels, selectedModel]);

  const handleSend = () => {
    if (!input.trim() || isSending) return;
    
    // Build context config based on selected tools and docs
    const contextConfig: any = {
      sources: {},
      notes: {}
    };
    
    selectedDocIds.forEach(id => {
      contextConfig.sources[id] = 'full content';
    });

    sendMessage(input, selectedModel || undefined, contextConfig);
    setInput('');
  };

  const toggleTool = (tool: string) => {
    setActiveTools(prev => {
      let next = prev.includes(tool) ? prev.filter(t => t !== tool) : [...prev, tool];
      if (tool === 'thinking' && next.includes('thinking')) next = next.filter(t => t !== 'deepsearch');
      else if (tool === 'deepsearch' && next.includes('deepsearch')) next = next.filter(t => t !== 'thinking');
      return next;
    });
  };

  return (
    <main className="flex-1 flex flex-col min-w-0 bg-[#0A0A0A] relative">
      {/* Top Header */}
      <header className="h-14 border-b border-[#1F1F1F] flex items-center justify-end px-4 bg-[#0A0A0A]/80 backdrop-blur-md sticky top-0 z-10">
        
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setIsIncognito(!isIncognito)}
            className={`p-2 rounded-xl transition-all ${isIncognito ? 'bg-[#8B5CF6]/20 text-[#8B5CF6]' : 'text-gray-500 hover:text-white hover:bg-[#1A1A1A]'}`}
            title="Incognito Mode"
          >
            <Ghost className="w-5 h-5" />
          </button>
          
          {activeProjectId && (
            <button 
              onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
              className={`p-2 rounded-xl transition-all ${isRightPanelOpen ? 'bg-[#8B5CF6]/20 text-[#8B5CF6]' : 'text-gray-500 hover:text-white hover:bg-[#1A1A1A]'}`}
              title="Toggle Sources"
            >
              <PanelRightOpen className="w-5 h-5" />
            </button>
          )}
        </div>
      </header>

      {/* Chat Content */}
      <div className="flex-1 overflow-y-auto px-4 py-8 custom-scrollbar">
        <div className="max-w-4xl mx-auto space-y-10">
          {/* Welcome State / Empty State */}
          {!activeChatId && !activeProjectId && messages.length === 0 && (
             <div className="flex flex-col items-center justify-center py-20 text-center space-y-8">
              <motion.div 
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="w-16 h-16 bg-white rounded-3xl flex items-center justify-center shadow-2xl shadow-purple-500/10"
              >
                <div className="w-8 h-8 bg-black rounded-lg"></div>
              </motion.div>
              <div className="space-y-3">
                <h2 className="text-2xl font-bold tracking-tight text-white italic">How can I help you today?</h2>
                <p className="text-gray-500 max-w-sm mx-auto text-xs">Select a project or start a new chat to begin your session.</p>
              </div>
            </div>
          )}

          {activeProjectId && messages.length === 0 && (
            <div className="flex flex-col gap-8 mb-12">
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-[#111] border border-[#1F1F1F] p-6 rounded-2xl flex items-center justify-between shadow-xl"
              >
                <div className="flex items-center gap-5">
                  <div className="w-12 h-12 bg-[#1A1A1A] rounded-xl flex items-center justify-center shadow-sm border border-[#333]">
                    <Folder className="w-6 h-6 text-[#8B5CF6]" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-base">Project: {project?.name || 'Loading...'}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex items-center gap-1.5 text-[10px] text-gray-400 bg-[#1A1A1A] px-2 py-0.5 rounded border border-[#333] font-bold uppercase tracking-wider">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        {project?.source_count || 0} SOURCES ACTIVE
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          )}

          {/* Messages Thread */}
          <div className="flex flex-col gap-10">
            {messages.map((msg, i) => (
              <div 
                key={msg.id || i} 
                className={`flex flex-col gap-3 ${msg.type === 'human' ? 'items-end' : 'items-center'}`}
              >
                {/* Message Content */}
                <div 
                  className={`
                    ${msg.type === 'human' 
                      ? 'max-w-[80%] bg-[#1A1A1A] text-[14px] text-gray-200 leading-relaxed whitespace-pre-wrap p-4 rounded-2xl border border-[#333]/50 shadow-lg' 
                      : 'w-full space-y-6'
                    }
                  `}
                >
                  {msg.type === 'human' ? (
                    msg.content
                  ) : (
                    <div className="max-w-3xl mx-auto text-left">
                      <div className="bg-[#111]/50 p-1 rounded-3xl">
                        <AIMessageContent 
                          content={msg.content} 
                          onReferenceClick={(type, id) => console.log('Ref click', type, id)}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isSending && (
              <div className="flex items-center gap-3 justify-center pt-4">
                 <div className="w-5 h-5 rounded-md bg-[#8B5CF6] flex items-center justify-center animate-pulse">
                    <div className="w-1.5 h-1.5 bg-black rounded-full"></div>
                 </div>
                 <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest animate-pulse">ARIA is thinking...</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM INPUT BAR */}
      <div className="p-3 bg-[#0A0A0A] border-t border-[#1F1F1F]">
        <div className="max-w-3xl mx-auto flex flex-col gap-2">
          <div className="bg-[#161616] border border-[#2A2A2A] rounded-[24px] p-1 shadow-2xl focus-within:border-[#333] transition-all flex flex-col relative">
            <div className="flex flex-col min-h-[44px]">
              <textarea 
                placeholder="Ask Aria anything..."
                className="w-full bg-transparent px-4 py-2.5 text-[14px] text-white resize-none focus:outline-none placeholder-gray-600 min-h-[44px] max-h-48"
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
              />
            </div>

            <div className="flex items-center justify-between px-2 pb-1.5 mt-0.5">
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
                        className="absolute bottom-full left-0 mb-3 w-60 bg-[#1F1F1F] border border-[#333] rounded-2xl shadow-2xl overflow-hidden z-50 py-1.5"
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
                        className="absolute bottom-full right-0 mb-3 w-48 bg-[#1F1F1F] border border-[#333] rounded-xl shadow-2xl overflow-hidden z-50 p-1"
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

                <div className="relative">
                  <button 
                    onClick={() => setShowSettings(!showSettings)}
                    className="w-8 h-8 flex items-center justify-center text-gray-500 hover:text-white hover:bg-[#2A2A2A] rounded-full transition-all"
                  >
                    <SettingsIcon className="w-4 h-4" />
                  </button>
                </div>
                
                <button 
                  onClick={handleSend}
                  disabled={isSending || !input.trim()}
                  className="w-8 h-8 bg-white text-black disabled:bg-gray-600 rounded-full flex items-center justify-center shadow-lg transition-all hover:bg-gray-200 active:scale-95 group ml-0.5"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
          <p className="text-[9px] text-gray-600 text-center uppercase tracking-widest leading-none">ARIA v1.2 // Private Session</p>
        </div>
      </div>
    </main>
  );
};
